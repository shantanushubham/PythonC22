// Package api embeds the OpenAPI description of the service.
package api

import _ "embed"

// Spec is the OpenAPI 3.1 document, as JSON. It is served at /openapi and /openapi.json.
// A test checks that it lists exactly the routes the service registers.
//
//go:embed openapi.json
var Spec []byte
