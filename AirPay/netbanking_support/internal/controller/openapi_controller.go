package controller

import (
	"net/http"

	"airpay/netbanking/api"
)

// OpenAPIController serves the API description and a page to read it.
type OpenAPIController struct{}

func NewOpenAPIController() *OpenAPIController { return &OpenAPIController{} }

// Spec handles GET /openapi and GET /openapi.json.
func (OpenAPIController) Spec(w http.ResponseWriter, _ *http.Request) error {
	w.Header().Set("Content-Type", "application/json")
	_, _ = w.Write(api.Spec)
	return nil
}

// Docs handles GET /docs: Swagger UI, loaded from a CDN, showing the whole spec.
func (OpenAPIController) Docs(w http.ResponseWriter, _ *http.Request) error {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	_, _ = w.Write([]byte(docsPage))
	return nil
}

const docsPage = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Netbanking Support API</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    window.ui = SwaggerUIBundle({ url: "/openapi.json", dom_id: "#swagger-ui", deepLinking: true });
  </script>
</body>
</html>
`
