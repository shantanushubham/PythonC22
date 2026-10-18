package controller

import (
	"bytes"
	"embed"
	"errors"
	"fmt"
	"html/template"
	"log/slog"
	"net/http"
	"net/url"
	"strings"

	"airpay/netbanking/internal/apperror"
	"airpay/netbanking/internal/model"
	"airpay/netbanking/internal/service"
)

//go:embed templates/pages.html
var templateFS embed.FS

const (
	defaultAccent = "#37474f"
	maxFormBytes  = 64 << 10
)

// BankPageController serves the mock bank's pages, the ones a customer sees after the
// merchant redirects them. Pages are rendered with html/template, which escapes every
// value for the place it is written.
type BankPageController struct {
	logger  *slog.Logger
	session *service.BankSessionService
	banks   *service.BankService
	pages   *template.Template
}

func NewBankPageController(
	logger *slog.Logger,
	session *service.BankSessionService,
	banks *service.BankService,
) (*BankPageController, error) {
	pages, err := template.ParseFS(templateFS, "templates/pages.html")
	if err != nil {
		return nil, fmt.Errorf("parse bank page templates: %w", err)
	}
	return &BankPageController{logger: logger, session: session, banks: banks, pages: pages}, nil
}

type loginPage struct {
	Accent        string
	BankName      string
	TransactionID string
	Amount        string
	Reference     string
	Message       string
}

type closedPage struct {
	Accent    string
	BankName  string
	Title     string
	Detail    string
	ReturnURL string
}

type errorPage struct {
	Accent  string
	Title   string
	Message string
}

// ShowLogin handles GET /bank/{transaction_id}: the bank's login page.
func (c *BankPageController) ShowLogin(w http.ResponseWriter, r *http.Request) error {
	payment, err := c.session.Open(r.Context(), r.PathValue("transaction_id"))
	if err != nil {
		return err
	}
	if payment.Status.Final() {
		return c.renderClosed(w, payment)
	}
	return c.renderLogin(w, payment, "")
}

// SubmitLogin handles POST /bank/{transaction_id}/login: the customer pressed Pay or
// Cancel. When the payment ends, the customer is sent back to the merchant.
func (c *BankPageController) SubmitLogin(w http.ResponseWriter, r *http.Request) error {
	r.Body = http.MaxBytesReader(w, r.Body, maxFormBytes)
	if err := r.ParseForm(); err != nil {
		var tooLarge *http.MaxBytesError
		if errors.As(err, &tooLarge) {
			return apperror.TooLarge("The form is too large.")
		}
		return apperror.BadRequest("The form could not be read.")
	}

	id := r.PathValue("transaction_id")

	if r.PostForm.Get("action") == "cancel" {
		payment, err := c.session.Cancel(r.Context(), id)
		if err != nil {
			return err
		}
		return c.sendBack(w, r, payment)
	}

	// Only the form body is read, so credentials can never arrive in the URL.
	result, err := c.session.Login(r.Context(), id, r.PostForm.Get("customer_id"), r.PostForm.Get("password"))
	if err != nil {
		return err
	}
	if result.RetryMessage != "" {
		return c.renderLogin(w, result.Payment, result.RetryMessage)
	}
	return c.sendBack(w, r, result.Payment)
}

// sendBack redirects the customer to the merchant's return URL with the outcome.
func (c *BankPageController) sendBack(w http.ResponseWriter, r *http.Request, payment model.Payment) error {
	http.Redirect(w, r, returnLocation(payment), http.StatusSeeOther)
	return nil
}

func (c *BankPageController) renderLogin(w http.ResponseWriter, payment model.Payment, message string) error {
	return c.render(w, http.StatusOK, "login", loginPage{
		Accent:        c.accent(payment.BankCode),
		BankName:      payment.BankName,
		TransactionID: payment.TransactionID,
		Amount:        formatRupees(payment.Amount),
		Reference:     payment.Reference,
		Message:       message,
	})
}

func (c *BankPageController) renderClosed(w http.ResponseWriter, payment model.Payment) error {
	title, detail := closedText(payment)
	return c.render(w, http.StatusOK, "closed", closedPage{
		Accent:    c.accent(payment.BankCode),
		BankName:  payment.BankName,
		Title:     title,
		Detail:    detail,
		ReturnURL: returnLocation(payment),
	})
}

// render builds the whole page before sending any of it, so a template error never
// leaves the customer with half a page.
func (c *BankPageController) render(w http.ResponseWriter, status int, name string, data any) error {
	var page bytes.Buffer
	if err := c.pages.ExecuteTemplate(&page, name, data); err != nil {
		return fmt.Errorf("render %s page: %w", name, err)
	}
	w.WriteHeader(status)
	_, _ = page.WriteTo(w)
	return nil
}

func (c *BankPageController) accent(bankCode string) string {
	if bank, ok := c.banks.Find(bankCode); ok && bank.Accent != "" {
		return bank.Accent
	}
	return defaultAccent
}

// page adapts a HandlerFunc to http.Handler. It sets the headers every bank page needs
// and shows errors as an HTML page instead of JSON.
func (c *BankPageController) page(fn HandlerFunc) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		headers := w.Header()
		headers.Set("Content-Type", "text/html; charset=utf-8")
		headers.Set("Cache-Control", "no-store")
		headers.Set("Referrer-Policy", "no-referrer")
		headers.Set("X-Frame-Options", "DENY") // a bank page must not be framed (clickjacking)
		// No scripts at all. The page needs only its own inline style.
		headers.Set("Content-Security-Policy",
			"default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'")

		if err := fn(w, r); err != nil {
			c.renderError(w, r, err)
		}
	})
}

func (c *BankPageController) renderError(w http.ResponseWriter, r *http.Request, err error) {
	var appErr *apperror.Error
	if !errors.As(err, &appErr) {
		c.logger.Error("unhandled error", "method", r.Method, "path", r.URL.Path, "error", err)
		appErr = &apperror.Error{Status: http.StatusInternalServerError, Message: "Something went wrong. Please try again."}
	}

	title := "Something went wrong"
	if appErr.Status == http.StatusNotFound {
		title = "Payment not found"
	}
	if renderErr := c.render(w, appErr.Status, "error", errorPage{
		Accent: defaultAccent, Title: title, Message: appErr.Message,
	}); renderErr != nil {
		http.Error(w, "Something went wrong.", http.StatusInternalServerError)
	}
}

// returnLocation is the merchant's return URL with the outcome added to its query.
// The merchant must not trust these values. It should call GET /api/v1/payments/{id}.
func returnLocation(payment model.Payment) string {
	u, err := url.Parse(payment.ReturnURL)
	if err != nil {
		return payment.ReturnURL
	}
	query := u.Query()
	query.Set("transaction_id", payment.TransactionID)
	query.Set("status", string(payment.Status))
	if payment.Reference != "" {
		query.Set("reference", payment.Reference)
	}
	u.RawQuery = query.Encode()
	return u.String()
}

func closedText(p model.Payment) (title, detail string) {
	switch p.Status {
	case model.StatusSuccess:
		return "Payment successful",
			fmt.Sprintf("\u20b9%s was paid. Bank reference: %s.", formatRupees(p.Amount), p.BankReference)
	case model.StatusFailed:
		return "Payment failed", p.FailureReason + "."
	case model.StatusCancelled:
		return "Payment cancelled", "This payment was cancelled."
	case model.StatusExpired:
		return "Session expired", "This payment session has expired. Return to the merchant and start again."
	default:
		return "Payment closed", "This payment can no longer be completed."
	}
}

// formatRupees writes an amount with Indian digit grouping: 1,50,000.00.
func formatRupees(a model.Amount) string {
	whole, fraction, _ := strings.Cut(a.String(), ".")
	if len(whole) > 3 {
		head, last3 := whole[:len(whole)-3], whole[len(whole)-3:]
		var groups []string
		for len(head) > 2 {
			groups = append([]string{head[len(head)-2:]}, groups...)
			head = head[:len(head)-2]
		}
		groups = append([]string{head}, groups...)
		whole = strings.Join(groups, ",") + "," + last3
	}
	return whole + "." + fraction
}
