package repository

import (
	"sort"
	"strings"

	"airpay/netbanking/internal/model"
)

// BankRepository lists the banks customers can pay from.
type BankRepository interface {
	// List returns every bank, ordered by name.
	List() []model.Bank
	// Find returns the bank with this code, if there is one.
	Find(code string) (model.Bank, bool)
}

// StaticBankRepository serves a fixed list of major Indian banks.
//
// Codes are the four-letter IFSC prefixes. Banks named in `down` are reported as DOWN,
// which lets a caller exercise the "bank unavailable" path.
type StaticBankRepository struct {
	banks  []model.Bank
	byCode map[string]model.Bank
}

var _ BankRepository = (*StaticBankRepository)(nil)

// DefaultBanks is the catalogue the mock supports.
func DefaultBanks() []model.Bank {
	return []model.Bank{
		{Code: "SBIN", Name: "State Bank of India", Accent: "#22409a"},
		{Code: "HDFC", Name: "HDFC Bank", Accent: "#004c8f"},
		{Code: "ICIC", Name: "ICICI Bank", Accent: "#b02a30"},
		{Code: "UTIB", Name: "Axis Bank", Accent: "#97144d"},
		{Code: "KKBK", Name: "Kotak Mahindra Bank", Accent: "#d9262c"},
		{Code: "PUNB", Name: "Punjab National Bank", Accent: "#a6192e"},
		{Code: "BARB", Name: "Bank of Baroda", Accent: "#e4600d"},
		{Code: "YESB", Name: "Yes Bank", Accent: "#0066b3"},
		{Code: "INDB", Name: "IndusInd Bank", Accent: "#98272a"},
		{Code: "CNRB", Name: "Canara Bank", Accent: "#0075c9"},
		{Code: "UBIN", Name: "Union Bank of India", Accent: "#d12027"},
		{Code: "IDFB", Name: "IDFC FIRST Bank", Accent: "#9c1d26"},
		{Code: "FDRL", Name: "Federal Bank", Accent: "#0072bc"},
		{Code: "BKID", Name: "Bank of India", Accent: "#0d4da1"},
		{Code: "IBKL", Name: "IDBI Bank", Accent: "#00836c"},
		{Code: "CBIN", Name: "Central Bank of India", Accent: "#d71920"},
	}
}

// NewStaticBankRepository builds the repository. Codes in `down` are marked DOWN.
func NewStaticBankRepository(banks []model.Bank, down []string) *StaticBankRepository {
	downSet := make(map[string]bool, len(down))
	for _, code := range down {
		downSet[strings.ToUpper(strings.TrimSpace(code))] = true
	}

	repo := &StaticBankRepository{byCode: make(map[string]model.Bank, len(banks))}
	for _, bank := range banks {
		bank.Status = model.BankUp
		if downSet[bank.Code] {
			bank.Status = model.BankDown
		}
		repo.banks = append(repo.banks, bank)
		repo.byCode[bank.Code] = bank
	}
	sort.Slice(repo.banks, func(i, j int) bool { return repo.banks[i].Name < repo.banks[j].Name })
	return repo
}

func (r *StaticBankRepository) List() []model.Bank {
	return append([]model.Bank(nil), r.banks...)
}

func (r *StaticBankRepository) Find(code string) (model.Bank, bool) {
	bank, ok := r.byCode[code]
	return bank, ok
}
