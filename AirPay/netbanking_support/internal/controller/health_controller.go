package controller

import (
	"net/http"

	"airpay/netbanking/internal/service"
)

// HealthController answers liveness checks.
type HealthController struct {
	banks *service.BankService
}

func NewHealthController(banks *service.BankService) *HealthController {
	return &HealthController{banks: banks}
}

// Check handles GET /health.
func (c *HealthController) Check(w http.ResponseWriter, _ *http.Request) error {
	codes := []string{}
	for _, bank := range c.banks.List(nil) {
		codes = append(codes, bank.Code)
	}
	writeJSON(w, http.StatusOK, healthView{Status: "ok", Service: "netbanking-support", Banks: codes})
	return nil
}
