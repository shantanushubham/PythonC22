package repository_test

import (
	"sort"
	"testing"

	"airpay/netbanking/internal/model"
	"airpay/netbanking/internal/repository"
)

func TestDefaultBanksCoverTheMajorIndianBanks(t *testing.T) {
	repo := repository.NewStaticBankRepository(repository.DefaultBanks(), nil)

	for _, code := range []string{"SBIN", "HDFC", "ICIC", "UTIB", "KKBK", "PUNB", "BARB", "YESB"} {
		bank, ok := repo.Find(code)
		if !ok {
			t.Errorf("%s is missing", code)
			continue
		}
		if bank.Status != model.BankUp || bank.Name == "" || bank.Accent == "" {
			t.Errorf("%s is incomplete: %+v", code, bank)
		}
	}
}

func TestBankCodesAreUniqueAndFourLetters(t *testing.T) {
	seen := map[string]bool{}
	for _, bank := range repository.DefaultBanks() {
		if len(bank.Code) != 4 {
			t.Errorf("%s is not four letters", bank.Code)
		}
		if seen[bank.Code] {
			t.Errorf("%s is listed twice", bank.Code)
		}
		seen[bank.Code] = true
	}
}

func TestListIsOrderedByName(t *testing.T) {
	banks := repository.NewStaticBankRepository(repository.DefaultBanks(), nil).List()

	if !sort.SliceIsSorted(banks, func(i, j int) bool { return banks[i].Name < banks[j].Name }) {
		t.Errorf("banks are not ordered by name: %v", banks)
	}
}

func TestBanksNamedAsDownAreReportedDown(t *testing.T) {
	repo := repository.NewStaticBankRepository(repository.DefaultBanks(), []string{" bkid ", "sbin"})

	for code, want := range map[string]model.BankStatus{
		"BKID": model.BankDown, "SBIN": model.BankDown, "HDFC": model.BankUp,
	} {
		bank, _ := repo.Find(code)
		if bank.Status != want {
			t.Errorf("%s is %s, want %s", code, bank.Status, want)
		}
	}
}

func TestUnknownBankIsNotFound(t *testing.T) {
	repo := repository.NewStaticBankRepository(repository.DefaultBanks(), nil)

	if _, ok := repo.Find("NOPE"); ok {
		t.Error("found a bank that does not exist")
	}
}

func TestListReturnsACopy(t *testing.T) {
	repo := repository.NewStaticBankRepository(repository.DefaultBanks(), nil)

	repo.List()[0].Name = "Tampered"

	if repo.List()[0].Name == "Tampered" {
		t.Error("the caller changed the repository's data")
	}
}
