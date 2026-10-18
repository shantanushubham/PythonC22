// Package app is the composition root: the one place that chooses concrete classes and
// connects them.
//
// Everything else depends on small interfaces. To change the database, the bank
// scenarios or the clock, change what is passed in here. Tests do exactly that.
package app

import (
	"fmt"
	"log/slog"
	"net/http"

	"airpay/netbanking/internal/config"
	"airpay/netbanking/internal/controller"
	"airpay/netbanking/internal/middleware"
	"airpay/netbanking/internal/repository"
	"airpay/netbanking/internal/service"
)

// maxRequestBody is the largest request body the service reads.
const maxRequestBody = 1 << 20

// Dependencies are the parts that can be swapped. Payments is required. Anything left
// nil gets the production default.
type Dependencies struct {
	Payments repository.PaymentRepository
	Banks    repository.BankRepository
	Clock    service.Clock
	IDs      service.IDGenerator
	Rules    []service.AuthorizationRule
	Logger   *slog.Logger
}

// NewHandler wires everything together and returns the HTTP handler.
func NewHandler(cfg config.Config, deps Dependencies) (http.Handler, error) {
	controllers, err := NewControllers(cfg, deps)
	if err != nil {
		return nil, err
	}

	return middleware.Chain(
		controller.NewRouter(controllers.Routes()),
		middleware.Recover(controllers.Logger),
		middleware.RequestLog(controllers.Logger),
		middleware.SecureHeaders(),
		middleware.MaxBody(maxRequestBody),
	), nil
}

// NewControllers builds the services and the controllers that use them.
func NewControllers(cfg config.Config, deps Dependencies) (controller.Controllers, error) {
	if deps.Payments == nil {
		return controller.Controllers{}, fmt.Errorf("a payment repository is required")
	}
	if deps.Banks == nil {
		deps.Banks = repository.NewStaticBankRepository(repository.DefaultBanks(), cfg.DownBanks)
	}
	if deps.Clock == nil {
		deps.Clock = service.SystemClock{}
	}
	if deps.IDs == nil {
		deps.IDs = service.RandomIDs{}
	}
	if deps.Rules == nil {
		deps.Rules = service.DefaultAuthorizationRules()
	}
	if deps.Logger == nil {
		deps.Logger = slog.Default()
	}

	banks := service.NewBankService(deps.Banks)
	query := service.NewPaymentQueryService(deps.Payments, deps.Clock)
	payments := service.NewPaymentService(deps.Payments, banks, query, deps.Clock, deps.IDs, cfg.PaymentTTL)
	auth := service.NewBankAuthorizationService(deps.Rules)
	session := service.NewBankSessionService(query, deps.Payments, auth, deps.Clock, deps.IDs)

	pages, err := controller.NewBankPageController(deps.Logger, session, banks)
	if err != nil {
		return controller.Controllers{}, err
	}

	return controller.Controllers{
		Logger:    deps.Logger,
		Health:    controller.NewHealthController(banks),
		Banks:     controller.NewBankController(banks),
		Payments:  controller.NewPaymentController(payments, query, cfg.BaseURL),
		BankPages: pages,
		OpenAPI:   controller.NewOpenAPIController(),
	}, nil
}
