package repository_test

import (
	"context"
	"errors"
	"path/filepath"
	"testing"

	"airpay/netbanking/internal/model"
	"airpay/netbanking/internal/repository"
	"airpay/netbanking/internal/repository/repotest"
)

func openSQLite(t *testing.T, path string) *repository.SQLitePaymentRepository {
	t.Helper()
	repo, err := repository.OpenSQLitePaymentRepository(path)
	if err != nil {
		t.Fatalf("open: %v", err)
	}
	t.Cleanup(func() { repo.Close() })
	return repo
}

func TestSQLitePaymentRepositoryFollowsTheContract(t *testing.T) {
	repotest.Run(t, func(t *testing.T) repository.PaymentRepository {
		return openSQLite(t, filepath.Join(t.TempDir(), "contract.db"))
	})
}

func TestSQLitePaymentsSurviveReopeningTheFile(t *testing.T) {
	path := filepath.Join(t.TempDir(), "payments.db")
	ctx := context.Background()
	first := openSQLite(t, path)
	stored := repository.StoredPayment{
		Payment: model.Payment{
			TransactionID: "nb_1", Status: model.StatusPending, Amount: 100, Currency: "INR",
			BankCode: "HDFC", BankName: "HDFC Bank", ReturnURL: "https://shop.example.com/r",
		},
		Fingerprint:    "fp",
		IdempotencyKey: "key",
	}
	if err := first.Create(ctx, stored); err != nil {
		t.Fatal(err)
	}
	first.Close()

	reopened := openSQLite(t, path)

	if _, err := reopened.Get(ctx, "nb_1"); err != nil {
		t.Errorf("Get after reopen: %v", err)
	}
	if _, err := reopened.GetByIdempotencyKey(ctx, "key"); err != nil {
		t.Errorf("GetByIdempotencyKey after reopen: %v", err)
	}
}

func TestSQLiteConnectionsSharingAFileAgree(t *testing.T) {
	path := filepath.Join(t.TempDir(), "shared.db")
	ctx := context.Background()
	first, second := openSQLite(t, path), openSQLite(t, path)
	base := repository.StoredPayment{
		Payment:        model.Payment{TransactionID: "nb_a", Status: model.StatusPending, Currency: "INR"},
		IdempotencyKey: "same",
	}
	if err := first.Create(ctx, base); err != nil {
		t.Fatal(err)
	}

	other := base
	other.Payment.TransactionID = "nb_b"
	if err := second.Create(ctx, other); !errors.Is(err, repository.ErrDuplicateIdempotencyKey) {
		t.Fatalf("got %v, want ErrDuplicateIdempotencyKey", err)
	}
}
