package repository

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	_ "modernc.org/sqlite" // registers the "sqlite" driver; pure Go, no cgo

	"airpay/netbanking/internal/model"
)

const schema = `
CREATE TABLE IF NOT EXISTS payments (
	transaction_id  TEXT PRIMARY KEY,
	idempotency_key TEXT UNIQUE,
	fingerprint     TEXT NOT NULL,
	status          TEXT NOT NULL,
	amount_paise    INTEGER NOT NULL,
	currency        TEXT NOT NULL,
	bank_code       TEXT NOT NULL,
	bank_name       TEXT NOT NULL,
	return_url      TEXT NOT NULL,
	reference       TEXT,
	bank_reference  TEXT,
	failure_reason  TEXT,
	created_at      TEXT NOT NULL,
	expires_at      TEXT NOT NULL,
	completed_at    TEXT
)`

const selectColumns = `transaction_id, idempotency_key, fingerprint, status, amount_paise,
	currency, bank_code, bank_name, return_url, reference, bank_reference, failure_reason,
	created_at, expires_at, completed_at`

// SQLitePaymentRepository keeps payments in a SQLite file, so they survive restarts.
//
// A unique index on idempotency_key makes "one payment per key" atomic, and the
// Complete query only touches rows that are still PENDING, which makes finishing a
// payment atomic. No customer credentials are ever stored.
type SQLitePaymentRepository struct {
	db *sql.DB
}

var _ PaymentRepository = (*SQLitePaymentRepository)(nil)

// OpenSQLitePaymentRepository opens (and creates) the database file at path.
func OpenSQLitePaymentRepository(path string) (*SQLitePaymentRepository, error) {
	if dir := filepath.Dir(path); dir != "." {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return nil, fmt.Errorf("create database directory: %w", err)
		}
	}

	// busy_timeout makes a writer wait for the lock instead of failing at once.
	// WAL lets readers and a writer work at the same time.
	dsn := "file:" + path + "?_pragma=busy_timeout(10000)&_pragma=journal_mode(WAL)&_pragma=synchronous(NORMAL)"
	db, err := sql.Open("sqlite", dsn)
	if err != nil {
		return nil, fmt.Errorf("open database: %w", err)
	}
	if _, err := db.Exec(schema); err != nil {
		db.Close()
		return nil, fmt.Errorf("create schema: %w", err)
	}
	return &SQLitePaymentRepository{db: db}, nil
}

// Close releases the database.
func (r *SQLitePaymentRepository) Close() error { return r.db.Close() }

func (r *SQLitePaymentRepository) Create(ctx context.Context, sp StoredPayment) error {
	p := sp.Payment
	_, err := r.db.ExecContext(ctx,
		`INSERT INTO payments (`+selectColumns+`) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`,
		p.TransactionID,
		nullString(sp.IdempotencyKey),
		sp.Fingerprint,
		string(p.Status),
		int64(p.Amount),
		p.Currency,
		p.BankCode,
		p.BankName,
		p.ReturnURL,
		nullString(p.Reference),
		nullString(p.BankReference),
		nullString(p.FailureReason),
		formatTime(p.CreatedAt),
		formatTime(p.ExpiresAt),
		nullTime(p.CompletedAt),
	)
	if err == nil {
		return nil
	}
	if strings.Contains(err.Error(), "UNIQUE constraint failed") {
		if strings.Contains(err.Error(), "idempotency_key") {
			return ErrDuplicateIdempotencyKey
		}
		return ErrDuplicatePayment
	}
	return fmt.Errorf("insert payment: %w", err)
}

func (r *SQLitePaymentRepository) Get(ctx context.Context, transactionID string) (StoredPayment, error) {
	return r.fetch(ctx, "transaction_id = ?", transactionID)
}

func (r *SQLitePaymentRepository) GetByIdempotencyKey(ctx context.Context, key string) (StoredPayment, error) {
	return r.fetch(ctx, "idempotency_key = ?", key)
}

func (r *SQLitePaymentRepository) Complete(
	ctx context.Context,
	transactionID string,
	c model.Completion,
) (model.Payment, error) {
	result, err := r.db.ExecContext(ctx,
		`UPDATE payments
		    SET status = ?, failure_reason = ?, bank_reference = ?, completed_at = ?
		  WHERE transaction_id = ? AND status = ?`,
		string(c.Status),
		nullString(c.FailureReason),
		nullString(c.BankReference),
		formatTime(c.At),
		transactionID,
		string(model.StatusPending),
	)
	if err != nil {
		return model.Payment{}, fmt.Errorf("complete payment: %w", err)
	}

	changed, err := result.RowsAffected()
	if err != nil {
		return model.Payment{}, fmt.Errorf("complete payment: %w", err)
	}

	stored, getErr := r.Get(ctx, transactionID)
	if getErr != nil {
		return model.Payment{}, getErr
	}
	if changed == 0 {
		return model.Payment{}, ErrNotPending
	}
	return stored.Payment, nil
}

func (r *SQLitePaymentRepository) fetch(ctx context.Context, where string, arg string) (StoredPayment, error) {
	row := r.db.QueryRowContext(ctx, `SELECT `+selectColumns+` FROM payments WHERE `+where, arg)

	var (
		sp                                                        StoredPayment
		p                                                         model.Payment
		key, reference, bankReference, failureReason, completedAt sql.NullString
		status, createdAt, expiresAt                              string
		amount                                                    int64
	)
	err := row.Scan(
		&p.TransactionID, &key, &sp.Fingerprint, &status, &amount,
		&p.Currency, &p.BankCode, &p.BankName, &p.ReturnURL, &reference, &bankReference,
		&failureReason, &createdAt, &expiresAt, &completedAt,
	)
	if errors.Is(err, sql.ErrNoRows) {
		return StoredPayment{}, ErrNotFound
	}
	if err != nil {
		return StoredPayment{}, fmt.Errorf("read payment: %w", err)
	}

	p.Status = model.PaymentStatus(status)
	p.Amount = model.Amount(amount)
	p.Reference = reference.String
	p.BankReference = bankReference.String
	p.FailureReason = failureReason.String
	if p.CreatedAt, err = parseTime(createdAt); err != nil {
		return StoredPayment{}, err
	}
	if p.ExpiresAt, err = parseTime(expiresAt); err != nil {
		return StoredPayment{}, err
	}
	if completedAt.Valid {
		t, err := parseTime(completedAt.String)
		if err != nil {
			return StoredPayment{}, err
		}
		p.CompletedAt = &t
	}

	sp.Payment = p
	sp.IdempotencyKey = key.String
	return sp, nil
}

func nullString(s string) sql.NullString {
	return sql.NullString{String: s, Valid: s != ""}
}

func nullTime(t *time.Time) sql.NullString {
	if t == nil {
		return sql.NullString{}
	}
	return sql.NullString{String: formatTime(*t), Valid: true}
}

func formatTime(t time.Time) string { return t.UTC().Format(time.RFC3339Nano) }

func parseTime(s string) (time.Time, error) {
	t, err := time.Parse(time.RFC3339Nano, s)
	if err != nil {
		return time.Time{}, fmt.Errorf("read stored time %q: %w", s, err)
	}
	return t, nil
}
