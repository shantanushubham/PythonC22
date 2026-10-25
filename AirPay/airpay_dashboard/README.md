# AirPay merchant dashboard

The web app for AirPay customers (merchants). It talks to the Django gateway in
`../payment_gateway_django` and covers every customer-facing API.

React 19, TypeScript, Vite, React Router and Recharts. No UI framework: the styles are one
CSS file with light and dark themes.

## Run

Start the gateway first (and the card, netbanking and UPI services if you want to take payments):

```bash
cd ../payment_gateway_django && uv run python manage.py runserver 8000
```

Then:

```bash
cd airpay_dashboard
npm install
npm run dev          # http://localhost:5173
```

The browser only talks to the Vite server. It forwards `/api/*` to the gateway, so Django needs
**no CORS setup**. If the gateway is not on port 8000:

```bash
GATEWAY_URL=http://localhost:9000 npm run dev
```

Other commands: `npm run build` (type-check and bundle to `dist/`), `npm run preview`,
`npm run typecheck`.

> For production, serve `dist/` from the same origin as the API behind one reverse proxy
> (`/api/*` to Django, everything else to `index.html`). That keeps CORS off and lets you
> move the refresh token to an httpOnly cookie later.

## What a customer can do

| Page | What it does | Endpoints |
| --- | --- | --- |
| Sign up / Log in | Create an account, sign in, stay signed in across reloads | `POST /customers`, `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout` |
| **Dashboard** | Settled, unsettled and total balance. Gross collected, refunded, commission and net earnings (both after refunds), success rate. 14-day chart, split by method, recent payments, settlements and payouts. Pending UPI/netbanking payments are refreshed in the background. | `GET /customers/me/balance`, `…/transactions`, `…/payouts`, `…/settlements`, `…/bank-accounts`, `…/api-keys` |
| **Transactions** | Filter by status and method, search, page through, export CSV. Detail page shows the commission breakdown and keeps polling while `PENDING`. | `GET /customers/me/transactions`, `GET /customers/me/transactions/{id}` |
| **Refunds** | List every refund with stats, status filter, search and CSV export. A payment is refunded from its detail page: full or partial, a reason, and a preview of the commission AirPay returns. The page shows the refund history of that payment. | `GET /customers/me/refunds`, `GET /customers/me/refunds/{id}`, `GET/POST /customers/me/transactions/{id}/refunds` |
| **Collect payment** | Take a payment the way your own app would, with an API key: card, UPI or netbanking. Test cards and UPI IDs for each mock outcome. Netbanking redirects to the bank and returns to `/pay/return`. | `GET /payments/whoami`, `POST /transactions`, `GET /transactions`, `GET /transactions/{id}` (API key) |
| **Balance & settlements** | Settle all or part of the unsettled balance to a chosen bank account. History. | `GET /customers/me/balance`, `POST /customers/me/settle`, `GET /customers/me/settlements` |
| **Payouts** | Pay out settled funds by bank transfer. History and detail. | `GET/POST /customers/me/payouts`, `GET /customers/me/payouts/{id}` |
| **Bank accounts** | Add, edit, set default, remove. | `GET/POST /customers/me/bank-accounts`, `GET/PATCH/DELETE …/{id}` |
| **API keys** | Create (secret shown once, with copy and verify), list, inspect, revoke. | `GET/POST /customers/me/api-keys`, `GET/DELETE …/{id}` |
| **Profile** | Edit name and company details, log out. | `GET/PATCH /customers/me` |
| Sidebar | Gateway status light. | `GET /health` |

## How it works

- **Two kinds of credential.** Account pages use the JWT. Creating a payment needs an
  **API key** (`X-API-Key`), and the gateway rejects a JWT there. The Collect payment page
  asks for a key, or creates a 24-hour test key for you. The key lives in `sessionStorage`
  only and is cleared on logout or when the tab closes.
- **Token refresh** (`src/api/client.ts`). The access token is kept in memory and the
  refresh token in `localStorage`. The gateway rotates refresh tokens, so a second refresh
  with the old token would fail. All callers therefore share one in-flight refresh, and a
  `401` triggers one refresh and one retry. If the refresh token is rejected, the app returns
  to the login page.
- **Refunds.** The refund dialog previews the commission AirPay returns with the same formula as
  the gateway (`src/lib/refund.ts`), but the server is the authority. If the wallet has already
  paid the money out, the gateway refuses and the dialog shows why. A declined refund (amount
  ending in `.99` in the mock) is shown in the history as Failed and moves no money.
- **Idempotency.** Payments, payouts and refunds send an `Idempotency-Key`. The same request body keeps
  the same key, so a retry after a network error cannot charge or pay out twice.
- **Pending payments.** UPI and netbanking start as `PENDING`. The list endpoint does not ask
  the rail again, but the detail endpoint does and credits the wallet on success. The app
  polls the detail endpoint while anything is pending.
- **Netbanking return.** The `status` in the return URL is only a hint, since the customer can
  edit it. `/pay/return` finds the payment on the gateway and shows what the gateway says.
- **Money.** The API sends amounts as strings (`"1500.50"`). Sums are done in whole paise
  (`src/lib/format.ts`), and amounts are only turned into numbers for display.
- **Errors.** The gateway's `{message, errors:[{field,message}]}` shape is mapped onto the
  matching form fields.

## Layout

```
src/
  api/        types.ts, client.ts (fetch, auth, refresh, errors), endpoints.ts (one function per route)
  auth/       AuthContext (session restore, sign in/out)
  components/ Layout, ui kit (buttons, modal, toasts, badges…), TransactionTable, AccountSelect
  lib/        format (money, dates), txn (stats, charts, pending sync), refund (commission preview, totals), useFetch, test data
  pages/      one file per screen
```

## Known limits

- The gateway has no endpoint for the ledger, so there is no ledger view.
- Lists are not paginated by the API, so filtering and paging happen in the browser. That is
  fine for hundreds of payments, not for hundreds of thousands.
- The refresh token is in `localStorage`, readable by any script on the page. Keep third-party
  scripts out of the app, or switch to an httpOnly cookie when the gateway supports it.
- Two tabs refreshing at the same moment can race, because each holds its own copy of the
  rotating refresh token. The loser is sent to the login page.
