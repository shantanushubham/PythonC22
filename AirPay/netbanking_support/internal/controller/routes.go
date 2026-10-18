package controller

import (
	"fmt"
	"log/slog"
	"net/http"
	"strings"
)

// Route ties one HTTP method and path to a handler.
type Route struct {
	Method  string
	Path    string
	Handler http.Handler
	// InSpec is true for the endpoints the OpenAPI document describes. Bank pages and
	// the documentation endpoints are left out. A test keeps the spec and these routes
	// in step.
	InSpec bool
}

// Controllers is every controller the service has.
type Controllers struct {
	Logger    *slog.Logger
	Health    *HealthController
	Banks     *BankController
	Payments  *PaymentController
	BankPages *BankPageController
	OpenAPI   *OpenAPIController
}

// Routes lists every endpoint. This is the one place routes are declared.
func (c Controllers) Routes() []Route {
	json := func(fn HandlerFunc) http.Handler { return jsonHandler(c.Logger, fn) }
	return []Route{
		{http.MethodGet, "/health", json(c.Health.Check), true},
		{http.MethodGet, "/api/v1/banks", json(c.Banks.List), true},
		{http.MethodPost, "/api/v1/payments", json(c.Payments.Create), true},
		{http.MethodGet, "/api/v1/payments/{transaction_id}", json(c.Payments.Get), true},

		{http.MethodGet, "/bank/{transaction_id}", c.BankPages.page(c.BankPages.ShowLogin), false},
		{http.MethodPost, "/bank/{transaction_id}/login", c.BankPages.page(c.BankPages.SubmitLogin), false},

		{http.MethodGet, "/openapi", json(c.OpenAPI.Spec), false},
		{http.MethodGet, "/openapi.json", json(c.OpenAPI.Spec), false},
		{http.MethodGet, "/docs", json(c.OpenAPI.Docs), false},
	}
}

// NewRouter builds the router from the route list. Unknown paths and wrong methods get
// the standard JSON error instead of the router's plain-text default.
func NewRouter(routes []Route) http.Handler {
	mux := http.NewServeMux()

	var paths []string
	methods := map[string][]string{}
	for _, route := range routes {
		mux.Handle(route.Method+" "+route.Path, route.Handler)

		if _, seen := methods[route.Path]; !seen {
			paths = append(paths, route.Path)
		}
		methods[route.Path] = append(methods[route.Path], route.Method)
		if route.Method == http.MethodGet {
			methods[route.Path] = append(methods[route.Path], http.MethodHead)
		}
	}

	// A path with no method is less specific than "GET /path", so it only receives the
	// methods nothing else claimed.
	for _, path := range paths {
		allow := strings.Join(methods[path], ", ")
		mux.HandleFunc(path, func(w http.ResponseWriter, r *http.Request) {
			w.Header().Set("Allow", allow)
			writeJSON(w, http.StatusMethodNotAllowed, errorBody{
				Message: fmt.Sprintf("Method %s is not allowed on %s. Allowed: %s", r.Method, r.URL.Path, allow),
			})
		})
	}

	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusNotFound, errorBody{
			Message: fmt.Sprintf("Route %s %s not found", r.Method, r.URL.Path),
		})
	})
	return mux
}
