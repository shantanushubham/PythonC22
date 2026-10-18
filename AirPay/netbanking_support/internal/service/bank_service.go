package service

import (
	"airpay/netbanking/internal/model"
	"airpay/netbanking/internal/repository"
)

// BankService answers questions about the supported banks.
type BankService struct {
	banks repository.BankRepository
}

func NewBankService(banks repository.BankRepository) *BankService {
	return &BankService{banks: banks}
}

// List returns the banks, optionally only those with the given status.
func (s *BankService) List(status *model.BankStatus) []model.Bank {
	all := s.banks.List()
	if status == nil {
		return all
	}
	var filtered []model.Bank
	for _, bank := range all {
		if bank.Status == *status {
			filtered = append(filtered, bank)
		}
	}
	return filtered
}

// Find returns the bank with this code, if it is supported.
func (s *BankService) Find(code string) (model.Bank, bool) {
	return s.banks.Find(code)
}
