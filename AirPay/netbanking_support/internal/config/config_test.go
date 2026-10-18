package config_test

import (
	"reflect"
	"strings"
	"testing"
	"time"

	"airpay/netbanking/internal/config"
)

func env(values map[string]string) config.Lookup {
	return func(key string) (string, bool) {
		v, ok := values[key]
		return v, ok
	}
}

func TestDefaults(t *testing.T) {
	cfg, err := config.Load(env(nil))

	if err != nil {
		t.Fatal(err)
	}
	want := config.Config{
		Port:       "8002",
		BaseURL:    "http://localhost:8002",
		DBPath:     "netbanking.db",
		PaymentTTL: 15 * time.Minute,
		DownBanks:  []string{"BKID"},
	}
	if !reflect.DeepEqual(cfg, want) {
		t.Errorf("got %+v, want %+v", cfg, want)
	}
}

func TestEverythingCanBeOverridden(t *testing.T) {
	cfg, err := config.Load(env(map[string]string{
		"PORT":                   "9100",
		"NETBANKING_BASE_URL":    "https://nb.example.com/",
		"NETBANKING_DB":          "/data/nb.db",
		"NETBANKING_PAYMENT_TTL": "90s",
		"NETBANKING_DOWN_BANKS":  " sbin , hdfc,,",
	}))

	if err != nil {
		t.Fatal(err)
	}
	if cfg.Port != "9100" || cfg.BaseURL != "https://nb.example.com" || cfg.DBPath != "/data/nb.db" ||
		cfg.PaymentTTL != 90*time.Second || !reflect.DeepEqual(cfg.DownBanks, []string{"SBIN", "HDFC"}) {
		t.Errorf("got %+v", cfg)
	}
}

func TestBaseURLFollowsThePort(t *testing.T) {
	cfg, _ := config.Load(env(map[string]string{"PORT": "7777"}))

	if cfg.BaseURL != "http://localhost:7777" {
		t.Errorf("BaseURL = %s", cfg.BaseURL)
	}
}

func TestAnEmptyDownBanksListMeansNoBankIsDown(t *testing.T) {
	cfg, err := config.Load(env(map[string]string{"NETBANKING_DOWN_BANKS": ""}))

	if err != nil || len(cfg.DownBanks) != 0 {
		t.Errorf("got %v, %v", cfg.DownBanks, err)
	}
}

func TestBlankValuesFallBackToTheDefault(t *testing.T) {
	cfg, err := config.Load(env(map[string]string{"PORT": "  ", "NETBANKING_DB": ""}))

	if err != nil || cfg.Port != "8002" || cfg.DBPath != "netbanking.db" {
		t.Errorf("got %+v, %v", cfg, err)
	}
}

func TestInvalidValuesAreRejectedWithTheVariableName(t *testing.T) {
	cases := map[string]map[string]string{
		"PORT":                     {"PORT": "abc"},
		"PORT ":                    {"PORT": "70000"},
		"PORT  ":                   {"PORT": "0"},
		"NETBANKING_BASE_URL":      {"NETBANKING_BASE_URL": "not a url"},
		"NETBANKING_BASE_URL ":     {"NETBANKING_BASE_URL": "ftp://x.example"},
		"NETBANKING_PAYMENT_TTL":   {"NETBANKING_PAYMENT_TTL": "soon"},
		"NETBANKING_PAYMENT_TTL ":  {"NETBANKING_PAYMENT_TTL": "0s"},
		"NETBANKING_PAYMENT_TTL  ": {"NETBANKING_PAYMENT_TTL": "25h"},
	}
	for name, values := range cases {
		_, err := config.Load(env(values))

		if err == nil || !strings.Contains(err.Error(), strings.TrimSpace(name)) {
			t.Errorf("%v: got %v", values, err)
		}
	}
}
