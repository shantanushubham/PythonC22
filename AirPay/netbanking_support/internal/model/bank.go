package model

// BankStatus says whether a bank can take payments right now.
type BankStatus string

const (
	BankUp   BankStatus = "UP"
	BankDown BankStatus = "DOWN"
)

// Bank is a bank customers can pay from. Code is the four-letter prefix of the bank's
// IFSC codes, for example HDFC for HDFC0001234.
type Bank struct {
	Code   string
	Name   string
	Accent string // brand colour for the mock login page, as #rrggbb
	Status BankStatus
}
