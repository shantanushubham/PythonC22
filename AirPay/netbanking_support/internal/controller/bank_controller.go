package controller

import (
	"net/http"
	"strings"

	"airpay/netbanking/internal/apperror"
	"airpay/netbanking/internal/model"
	"airpay/netbanking/internal/service"
)

// BankController serves the list of supported banks.
type BankController struct {
	banks *service.BankService
}

func NewBankController(banks *service.BankService) *BankController {
	return &BankController{banks: banks}
}

// List handles GET /api/v1/banks, with an optional ?status=UP or ?status=DOWN filter.
func (c *BankController) List(w http.ResponseWriter, r *http.Request) error {
	var filter *model.BankStatus
	if raw := r.URL.Query().Get("status"); raw != "" {
		status := model.BankStatus(strings.ToUpper(raw))
		if status != model.BankUp && status != model.BankDown {
			return apperror.Validation(apperror.Field("status", "status must be UP or DOWN"))
		}
		filter = &status
	}

	items := []bankListItem{}
	for _, bank := range c.banks.List(filter) {
		items = append(items, bankListItem{Code: bank.Code, Name: bank.Name, Status: string(bank.Status)})
	}
	writeSuccess(w, http.StatusOK, bankListView{Banks: items})
	return nil
}
