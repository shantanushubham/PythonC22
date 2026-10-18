package testutil_test

import (
	"testing"

	"airpay/netbanking/internal/repository"
	"airpay/netbanking/internal/repository/repotest"
	"airpay/netbanking/internal/testutil"
)

// The in-memory fake is a second implementation of the repository contract. Passing the
// same checks as SQLite is what makes it a valid stand-in in the service tests.
func TestMemoryPaymentRepositoryFollowsTheContract(t *testing.T) {
	repotest.Run(t, func(t *testing.T) repository.PaymentRepository {
		return testutil.NewMemoryPaymentRepository()
	})
}
