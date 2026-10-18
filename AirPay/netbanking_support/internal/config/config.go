// Package config reads settings from the environment.
package config

import (
	"fmt"
	"net/url"
	"strconv"
	"strings"
	"time"
)

// Config is everything the service can be told from outside.
type Config struct {
	// Port the HTTP server listens on. Env PORT, default 8002.
	Port string
	// BaseURL is the address callers and customers use to reach this service. It is
	// used to build the bank page link returned as redirect_url.
	// Env NETBANKING_BASE_URL, default http://localhost:<port>.
	BaseURL string
	// DBPath is the SQLite file. Env NETBANKING_DB, default netbanking.db.
	DBPath string
	// PaymentTTL is how long a customer has to finish a payment.
	// Env NETBANKING_PAYMENT_TTL, default 15m.
	PaymentTTL time.Duration
	// DownBanks are bank codes reported as DOWN, to test the "bank unavailable" path.
	// Env NETBANKING_DOWN_BANKS (comma separated), default BKID. Set it empty for none.
	DownBanks []string
}

// Lookup reads one environment variable and says whether it was set.
type Lookup func(key string) (string, bool)

// Load builds a Config. Pass os.LookupEnv in production.
func Load(lookup Lookup) (Config, error) {
	get := func(key, fallback string) string {
		if value, ok := lookup(key); ok && strings.TrimSpace(value) != "" {
			return strings.TrimSpace(value)
		}
		return fallback
	}

	cfg := Config{
		Port:       get("PORT", "8002"),
		DBPath:     get("NETBANKING_DB", "netbanking.db"),
		PaymentTTL: 15 * time.Minute,
		DownBanks:  []string{"BKID"},
	}

	if port, err := strconv.Atoi(cfg.Port); err != nil || port < 1 || port > 65535 {
		return Config{}, fmt.Errorf("PORT must be a number from 1 to 65535, got %q", cfg.Port)
	}

	baseURL := strings.TrimRight(get("NETBANKING_BASE_URL", "http://localhost:"+cfg.Port), "/")
	u, err := url.Parse(baseURL)
	if err != nil || u.Host == "" || (u.Scheme != "http" && u.Scheme != "https") {
		return Config{}, fmt.Errorf("NETBANKING_BASE_URL must be an absolute http or https URL, got %q", baseURL)
	}
	cfg.BaseURL = baseURL

	if raw := get("NETBANKING_PAYMENT_TTL", ""); raw != "" {
		ttl, err := time.ParseDuration(raw)
		if err != nil || ttl <= 0 || ttl > 24*time.Hour {
			return Config{}, fmt.Errorf("NETBANKING_PAYMENT_TTL must be a duration between 1s and 24h, got %q", raw)
		}
		cfg.PaymentTTL = ttl
	}

	if value, ok := lookup("NETBANKING_DOWN_BANKS"); ok {
		cfg.DownBanks = nil
		for _, code := range strings.Split(value, ",") {
			if code = strings.ToUpper(strings.TrimSpace(code)); code != "" {
				cfg.DownBanks = append(cfg.DownBanks, code)
			}
		}
	}
	return cfg, nil
}
