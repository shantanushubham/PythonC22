// Command netbanking runs the mock netbanking service.
package main

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"airpay/netbanking/internal/app"
	"airpay/netbanking/internal/config"
	"airpay/netbanking/internal/repository"
)

func main() {
	logger := slog.New(slog.NewTextHandler(os.Stdout, nil))
	if err := run(logger); err != nil {
		logger.Error("netbanking stopped", "error", err)
		os.Exit(1)
	}
}

func run(logger *slog.Logger) error {
	cfg, err := config.Load(os.LookupEnv)
	if err != nil {
		return err
	}

	payments, err := repository.OpenSQLitePaymentRepository(cfg.DBPath)
	if err != nil {
		return err
	}
	defer payments.Close()

	handler, err := app.NewHandler(cfg, app.Dependencies{Payments: payments, Logger: logger})
	if err != nil {
		return err
	}

	server := &http.Server{
		Addr:              ":" + cfg.Port,
		Handler:           handler,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       10 * time.Second,
		WriteTimeout:      15 * time.Second,
		IdleTimeout:       60 * time.Second,
	}

	// Stop on Ctrl+C or SIGTERM, but let requests in flight finish first.
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	serverErr := make(chan error, 1)
	go func() {
		logger.Info("netbanking listening", "addr", server.Addr, "base_url", cfg.BaseURL,
			"db", cfg.DBPath, "payment_ttl", cfg.PaymentTTL.String(), "down_banks", cfg.DownBanks)
		serverErr <- server.ListenAndServe()
	}()

	select {
	case err := <-serverErr:
		if errors.Is(err, http.ErrServerClosed) {
			return nil
		}
		return err
	case <-ctx.Done():
		logger.Info("shutting down")
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		return server.Shutdown(shutdownCtx)
	}
}
