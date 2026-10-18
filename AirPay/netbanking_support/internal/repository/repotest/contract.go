// Package repotest is the contract every PaymentRepository must satisfy.
//
// Run it from the test of each implementation. If an implementation passes, the
// services can use it in place of any other (Liskov Substitution).
package repotest

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"testing"
	"time"

	"airpay/netbanking/internal/model"
	"airpay/netbanking/internal/repository"
)

// Factory returns a new, empty repository.
type Factory func(t *testing.T) repository.PaymentRepository

var created = time.Date(2026, 10, 18, 12, 0, 0, 123456000, time.UTC)

func sample(id, key string) repository.StoredPayment {
	return repository.StoredPayment{
		Payment: model.Payment{
			TransactionID: id,
			Status:        model.StatusPending,
			Amount:        150050,
			Currency:      "INR",
			BankCode:      "HDFC",
			BankName:      "HDFC Bank",
			ReturnURL:     "https://shop.example.com/return?cart=9",
			Reference:     "order_1001",
			CreatedAt:     created,
			ExpiresAt:     created.Add(15 * time.Minute),
		},
		Fingerprint:    "fp-" + id,
		IdempotencyKey: key,
	}
}

// Run executes the contract.
func Run(t *testing.T, newRepo Factory) {
	ctx := context.Background()

	t.Run("a payment is read back exactly as it was saved", func(t *testing.T) {
		repo := newRepo(t)
		want := sample("nb_1", "key-1")
		if err := repo.Create(ctx, want); err != nil {
			t.Fatalf("Create: %v", err)
		}

		got, err := repo.Get(ctx, "nb_1")
		if err != nil {
			t.Fatalf("Get: %v", err)
		}
		assertSame(t, got.Payment, want.Payment)
		if got.Fingerprint != want.Fingerprint || got.IdempotencyKey != want.IdempotencyKey {
			t.Errorf("got fingerprint %q key %q, want %q %q",
				got.Fingerprint, got.IdempotencyKey, want.Fingerprint, want.IdempotencyKey)
		}
	})

	t.Run("a payment can be found by its idempotency key", func(t *testing.T) {
		repo := newRepo(t)
		mustCreate(t, repo, sample("nb_1", "key-1"))

		got, err := repo.GetByIdempotencyKey(ctx, "key-1")
		if err != nil || got.Payment.TransactionID != "nb_1" {
			t.Fatalf("got %+v, %v", got.Payment, err)
		}
	})

	t.Run("unknown ids and keys are ErrNotFound", func(t *testing.T) {
		repo := newRepo(t)

		if _, err := repo.Get(ctx, "nb_missing"); !errors.Is(err, repository.ErrNotFound) {
			t.Errorf("Get: got %v, want ErrNotFound", err)
		}
		if _, err := repo.GetByIdempotencyKey(ctx, "missing"); !errors.Is(err, repository.ErrNotFound) {
			t.Errorf("GetByIdempotencyKey: got %v, want ErrNotFound", err)
		}
	})

	t.Run("a duplicate idempotency key is rejected and not stored", func(t *testing.T) {
		repo := newRepo(t)
		mustCreate(t, repo, sample("nb_a", "same"))

		err := repo.Create(ctx, sample("nb_b", "same"))

		if !errors.Is(err, repository.ErrDuplicateIdempotencyKey) {
			t.Fatalf("got %v, want ErrDuplicateIdempotencyKey", err)
		}
		if _, err := repo.Get(ctx, "nb_b"); !errors.Is(err, repository.ErrNotFound) {
			t.Errorf("rejected payment was stored: %v", err)
		}
		winner, _ := repo.GetByIdempotencyKey(ctx, "same")
		if winner.Payment.TransactionID != "nb_a" {
			t.Errorf("key now points at %s, want nb_a", winner.Payment.TransactionID)
		}
	})

	t.Run("a duplicate transaction id is rejected", func(t *testing.T) {
		repo := newRepo(t)
		mustCreate(t, repo, sample("nb_dup", ""))

		err := repo.Create(ctx, sample("nb_dup", ""))

		if !errors.Is(err, repository.ErrDuplicatePayment) {
			t.Fatalf("got %v, want ErrDuplicatePayment", err)
		}
	})

	t.Run("payments without a key never collide", func(t *testing.T) {
		repo := newRepo(t)
		mustCreate(t, repo, sample("nb_x", ""))
		mustCreate(t, repo, sample("nb_y", ""))

		for _, id := range []string{"nb_x", "nb_y"} {
			if _, err := repo.Get(ctx, id); err != nil {
				t.Errorf("Get(%s): %v", id, err)
			}
		}
	})

	t.Run("Complete moves a pending payment to a final state", func(t *testing.T) {
		repo := newRepo(t)
		mustCreate(t, repo, sample("nb_1", ""))
		at := created.Add(time.Minute)

		done, err := repo.Complete(ctx, "nb_1", model.Completion{
			Status: model.StatusSuccess, BankReference: "HDFC000000000001", At: at,
		})
		if err != nil {
			t.Fatalf("Complete: %v", err)
		}
		if done.Status != model.StatusSuccess || done.BankReference != "HDFC000000000001" {
			t.Errorf("returned %+v", done)
		}
		if done.CompletedAt == nil || !done.CompletedAt.Equal(at) {
			t.Errorf("CompletedAt = %v, want %v", done.CompletedAt, at)
		}

		stored, _ := repo.Get(ctx, "nb_1")
		if stored.Payment.Status != model.StatusSuccess || stored.Payment.BankReference != "HDFC000000000001" {
			t.Errorf("stored %+v", stored.Payment)
		}
	})

	t.Run("Complete records a failure reason", func(t *testing.T) {
		repo := newRepo(t)
		mustCreate(t, repo, sample("nb_1", ""))

		done, err := repo.Complete(ctx, "nb_1", model.Completion{
			Status: model.StatusFailed, FailureReason: "Insufficient funds", At: created,
		})
		if err != nil || done.FailureReason != "Insufficient funds" || done.BankReference != "" {
			t.Fatalf("got %+v, %v", done, err)
		}
	})

	t.Run("a final payment cannot change again", func(t *testing.T) {
		repo := newRepo(t)
		mustCreate(t, repo, sample("nb_1", ""))
		if _, err := repo.Complete(ctx, "nb_1", model.Completion{Status: model.StatusSuccess, At: created}); err != nil {
			t.Fatal(err)
		}

		_, err := repo.Complete(ctx, "nb_1", model.Completion{Status: model.StatusCancelled, At: created})

		if !errors.Is(err, repository.ErrNotPending) {
			t.Fatalf("got %v, want ErrNotPending", err)
		}
		stored, _ := repo.Get(ctx, "nb_1")
		if stored.Payment.Status != model.StatusSuccess {
			t.Errorf("status changed to %s", stored.Payment.Status)
		}
	})

	t.Run("Complete of an unknown payment is ErrNotFound", func(t *testing.T) {
		repo := newRepo(t)

		_, err := repo.Complete(ctx, "nb_missing", model.Completion{Status: model.StatusSuccess, At: created})

		if !errors.Is(err, repository.ErrNotFound) {
			t.Fatalf("got %v, want ErrNotFound", err)
		}
	})

	t.Run("of many concurrent Creates with one key exactly one wins", func(t *testing.T) {
		repo := newRepo(t)
		wins := race(20, func(i int) error {
			return repo.Create(ctx, sample(fmt.Sprintf("nb_race_%d", i), "race-key"))
		}, repository.ErrDuplicateIdempotencyKey)

		if wins != 1 {
			t.Fatalf("%d Creates succeeded, want exactly 1", wins)
		}
	})

	t.Run("of many concurrent Completes exactly one wins", func(t *testing.T) {
		repo := newRepo(t)
		mustCreate(t, repo, sample("nb_1", ""))

		wins := race(20, func(i int) error {
			_, err := repo.Complete(ctx, "nb_1", model.Completion{
				Status: model.StatusSuccess, BankReference: fmt.Sprintf("REF%d", i), At: created,
			})
			return err
		}, repository.ErrNotPending)

		if wins != 1 {
			t.Fatalf("%d Completes succeeded, want exactly 1", wins)
		}
	})
}

// race runs fn n times at once and counts the calls that returned nil. Any other error
// than `expected` fails the test by panicking, which the caller's goroutine reports.
func race(n int, fn func(i int) error, expected error) int {
	var (
		wg   sync.WaitGroup
		mu   sync.Mutex
		wins int
		bad  []error
	)
	start := make(chan struct{})
	for i := 0; i < n; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			<-start
			err := fn(i)
			mu.Lock()
			defer mu.Unlock()
			switch {
			case err == nil:
				wins++
			case !errors.Is(err, expected):
				bad = append(bad, err)
			}
		}(i)
	}
	close(start)
	wg.Wait()
	if len(bad) > 0 {
		panic(fmt.Sprintf("unexpected errors during race: %v", bad))
	}
	return wins
}

func mustCreate(t *testing.T, repo repository.PaymentRepository, sp repository.StoredPayment) {
	t.Helper()
	if err := repo.Create(context.Background(), sp); err != nil {
		t.Fatalf("Create(%s): %v", sp.Payment.TransactionID, err)
	}
}

func assertSame(t *testing.T, got, want model.Payment) {
	t.Helper()
	if got.TransactionID != want.TransactionID || got.Status != want.Status ||
		got.Amount != want.Amount || got.Currency != want.Currency ||
		got.BankCode != want.BankCode || got.BankName != want.BankName ||
		got.ReturnURL != want.ReturnURL || got.Reference != want.Reference ||
		got.BankReference != want.BankReference || got.FailureReason != want.FailureReason {
		t.Errorf("payment differs:\n got  %+v\n want %+v", got, want)
	}
	if !got.CreatedAt.Equal(want.CreatedAt) || !got.ExpiresAt.Equal(want.ExpiresAt) {
		t.Errorf("times differ: got %v / %v, want %v / %v",
			got.CreatedAt, got.ExpiresAt, want.CreatedAt, want.ExpiresAt)
	}
	if (got.CompletedAt == nil) != (want.CompletedAt == nil) {
		t.Errorf("CompletedAt: got %v, want %v", got.CompletedAt, want.CompletedAt)
	}
}
