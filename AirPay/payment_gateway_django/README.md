# AirPay Payment Gateway (Django REST framework)

The gateway API for AirPay. It will accept payments and route them to the supporting services
that sit next to it:

| Service | Folder | Port |
| --- | --- | --- |
| Card payments (FastAPI, mock) | `../card_payment_service` | 8001 |
| Netbanking (Go, mock) | `../netbanking_support` | 8002 |
| UPI (Node, mock) | `../upi_payment_service` | see its README |

So far it has the project skeleton, the customer module with JWT login, error handling, API
docs and a health endpoint. The payment features go in new apps next to `customers`.

## Run

```bash
cd payment_gateway_django
docker compose up -d db          # Postgres
uv sync
uv run python manage.py migrate
uv run python manage.py runserver 8000
```

- API: <http://localhost:8000/api/v1/health>
- Swagger UI: <http://localhost:8000/api/docs/>
- OpenAPI schema: <http://localhost:8000/api/schema/>
- Admin: <http://localhost:8000/admin/> (create a user with `uv run python manage.py createsuperuser`)

No Docker? Run with SQLite instead: `DB_ENGINE=sqlite uv run python manage.py migrate`, and set
the same variable for `runserver` and `test`.

```bash
uv run python manage.py test     # needs Postgres up, or DB_ENGINE=sqlite
```

Export the schema to a file: `uv run python manage.py spectacular --file openapi.yml`.

### Postman

Import both files from `postman/`:

- `AirPay_Gateway.postman_collection.json`
- `AirPay_Gateway.local.postman_environment.json`

Select **AirPay Gateway — Local** as the environment. Run **Register** then **Login**; tests save `access_token` and `refresh_token`. **Create API key** saves `api_key`. **Add bank account** saves `bank_account_id`. Create a **card** transaction (card service on port 8001), then refund it (the **Refunds** folder), or settle and pay out. Run **Revoke API key** and **Logout** last — they are destructive.

A JWT cannot create a transaction (`POST /api/v1/transactions`). An API key cannot manage the account, bank accounts, payouts or refunds.

## Configuration

Settings come from environment variables. The defaults suit local development with the
`docker-compose.yml` database.

| Variable | Default | Meaning |
| --- | --- | --- |
| `DJANGO_DEBUG` | `1` | Set to `0` for anything that is not your own machine. |
| `DJANGO_SECRET_KEY` | a dev-only key | **Required** when `DJANGO_DEBUG=0`. |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,[::1]` | Comma separated. **Required** when `DJANGO_DEBUG=0`. |
| `DB_ENGINE` | `postgres` | `postgres` or `sqlite`. |
| `POSTGRES_DB` | `payment_gateway_db` | |
| `POSTGRES_USER` | `payment_gateway_user` | |
| `POSTGRES_PASSWORD` | `payment_gateway_password` | |
| `POSTGRES_HOST` | `localhost` | |
| `POSTGRES_PORT` | `5432` | |
| `API_ANON_RATE` | `100/minute` | Rate limit for callers who are not logged in. |
| `API_LOGIN_RATE` | `10/minute` | Login attempts allowed per IP address. |
| `JWT_ACCESS_MINUTES` | `15` | Life of an access token. |
| `JWT_REFRESH_DAYS` | `7` | Life of a refresh token. |
| `API_KEY_PEPPER` | (derived from `SECRET_KEY`) | HMAC key for API keys. Set this so rotating the JWT secret does not revoke payment keys. |
| `API_KEY_MAX_PER_CUSTOMER` | `20` | Active (not revoked, not expired) keys a customer may hold. |
| `API_KEY_MAX_LIFETIME_DAYS` | `365` | Furthest `expires_at` allowed when creating a key. |
| `BANK_ACCOUNT_KEY` | (derived from `SECRET_KEY`) | Fernet key for encrypting bank account numbers. |
| `BANK_ACCOUNT_MAX_PER_CUSTOMER` | `10` | Active bank accounts a customer may hold. |
| `CARD_PAYMENT_URL` | `http://localhost:8001` | Card payment service. |
| `NETBANKING_URL` | `http://localhost:8002` | Netbanking service. |
| `UPI_PAYMENT_URL` | `http://localhost:8003` | UPI payment service. |
| `RAIL_TIMEOUT_SECONDS` | `10` | How long to wait for a rail. |

With `DJANGO_DEBUG=0` the server refuses to start without a real secret key and host list, so a
production start cannot quietly use the development values.

## What is set up

**Project layout**

```
config/      settings, root URLs, WSGI/ASGI
core/        shared pieces: health endpoint and the error handler
customers/   Customer, JWT, API keys, bank accounts
payments/    AirPay transactions (API key), wallet, settlement, bank-transfer payouts, refunds
```

Each feature gets its own app (for example `payments`) with its own `urls.py`, mounted in
`config/urls.py` under `/api/v1/`.

**REST framework defaults** (`REST_FRAMEWORK` in `config/settings.py`)

- JSON only. The browsable HTML API is off.
- Closed by default: every view needs a valid JWT access token unless it says `AllowAny`.
- Page number pagination, 20 per page.
- Rate limiting for anonymous callers.
- OpenAPI 3 documentation generated from the views by drf-spectacular. A test fails if the
  schema generates with warnings.

**One error shape.** Every error, including 404, 405, 429 and 500, looks like the other AirPay
services:

```json
{"success": false, "message": "Validation failed",
 "errors": [{"field": "items.1.qty", "message": "Ensure this value is greater than or equal to 1."}]}
```

`errors` appears for validation problems only, with nested fields written as `items.1.qty`.
Validation failures return `400`. A server error never shows internal details.
With `DJANGO_DEBUG=1`, Django still shows its own HTML page for unknown URLs. That is a
development aid and does not happen when debug is off.

**Health.** `GET /api/v1/health` returns `200` when the database answers `SELECT 1`, and `503`
when it does not. It needs no login and is not rate limited, so probes always get through.

## Customers and login

### The Customer model

`customers.Customer` is built on Django's `AbstractUser` with Django's own manager, so it keeps
password hashing, `is_active`, permissions, groups and admin support.

| Field | Notes |
| --- | --- |
| `first_name`, `last_name` | Required, up to 150 characters. |
| `company_name` | Required, up to 150 characters. |
| `company_address` | Required, up to 500 characters. |
| `email` | Required and unique. Stored in lower case. |
| `username` | Django's login name. For customers who sign up through the API it is their email. |
| `password` | A bcrypt hash. The password itself is never stored. |
| `id` | A UUID, so customer ids cannot be guessed or counted. |

`AUTH_USER_MODEL` points at this model. Django needs that to be set before a database's first
migration. To start from scratch locally: `docker compose down -v`, then `docker compose up -d db`
and `migrate` again.

### Passwords

Passwords are hashed with bcrypt, with a random salt for each password. The hasher is Django's
`BCryptSHA256PasswordHasher` at cost 12, and it is the only hasher in `PASSWORD_HASHERS`. The
SHA-256 step is there because plain bcrypt silently ignores everything after 72 bytes of a
password. New passwords must pass Django's four validators: at least 8 characters, not a common
password, not all digits, and not too similar to the email or name.

### Endpoints

| Method and path | Needs a token | Purpose |
| --- | --- | --- |
| `POST /api/v1/customers` | no | Sign up. |
| `POST /api/v1/auth/login` | no | Email and password in, access and refresh token out. |
| `POST /api/v1/auth/refresh` | no | Refresh token in, new access and refresh token out. |
| `POST /api/v1/auth/logout` | no | Revokes a refresh token. Returns `204`. |
| `GET /api/v1/customers/me` | access token | Your own account. |
| `PATCH /api/v1/customers/me` | access token | Change `first_name`, `last_name`, `company_name`, `company_address`. |
| `GET /api/v1/customers/me/api-keys` | access token | List your API keys (secret never included). |
| `POST /api/v1/customers/me/api-keys` | access token | Create an API key. The secret is in `key`, shown this once. |
| `GET /api/v1/customers/me/api-keys/{id}` | access token | One of your keys. |
| `DELETE /api/v1/customers/me/api-keys/{id}` | access token | Revoke a key. It stops working at once. |
| `GET` / `POST /api/v1/customers/me/bank-accounts` | access token | List or add beneficiary accounts. |
| `GET` / `PATCH` / `DELETE …/bank-accounts/{id}` | access token | One account. Delete removes it from payouts. |
| `GET /api/v1/customers/me/balance` | access token | Settled, unsettled and total. |
| `POST /api/v1/customers/me/settle` | access token | Settle to one of your bank accounts (`bank_account_id`). `amount` is optional; omit it to settle every unsettled rupee. |
| `GET /api/v1/customers/me/settlements` | access token | List your settlements. |
| `GET` / `POST /api/v1/customers/me/payouts` | access token | List or request a bank-transfer payout. |
| `GET /api/v1/customers/me/payouts/{id}` | access token | One payout. |
| `GET /api/v1/customers/me/transactions` | access token | Incoming AirPay transactions. Each shows `refunded`, `refundable` and `refund_status` (`NONE`, `PARTIAL`, `FULL`). |
| `POST /api/v1/customers/me/transactions/{id}/refunds` | access token | Refund a successful payment, in full or in part. `amount` is optional; omit it to refund what is left. |
| `GET /api/v1/customers/me/transactions/{id}/refunds` | access token | The refunds of one payment. |
| `GET /api/v1/customers/me/refunds` | access token | All your refunds. |
| `GET /api/v1/customers/me/refunds/{id}` | access token | One refund. |
| `POST /api/v1/transactions` | API key | Collect via card, UPI or netbanking. Credits **unsettled** only on `SUCCESS`. |
| `GET /api/v1/transactions` | API key | List those transactions. |
| `GET /api/v1/transactions/{id}` | API key | One transaction. Polls the rail if it is still `PENDING`. |
| `GET /api/v1/payments/whoami` | API key | Confirms the key. |

```bash
# sign up
curl -X POST localhost:8000/api/v1/customers -H 'Content-Type: application/json' -d '{
  "email": "jane@acme.com", "password": "Corr3ct-Horse-Battery",
  "first_name": "Jane", "last_name": "Doe",
  "company_name": "Acme Pvt Ltd", "company_address": "1 Marine Drive, Mumbai"}'

# log in
curl -X POST localhost:8000/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"email": "jane@acme.com", "password": "Corr3ct-Horse-Battery"}'
# {"access": "eyJ...", "refresh": "eyJ..."}

# call the API
curl localhost:8000/api/v1/customers/me -H 'Authorization: Bearer <access>'
```

### Tokens

- The **access token** is short lived (15 minutes). Send it as `Authorization: Bearer <access>`.
  It holds only the customer id, an expiry and a token id. It holds no email or password.
- The **refresh token** lasts 7 days. Send it to `/auth/refresh` for a new pair.
- **Refresh tokens rotate.** Every refresh returns a new refresh token and revokes the one you
  sent. Using an old one a second time is refused with `401`.
- **Logout** revokes the refresh token. An access token already issued keeps working until it
  expires, so discard it on the client. That is the reason it is short lived.
- A deactivated customer is refused at once, even with a valid access token.
- Tokens are signed with HS256 using `DJANGO_SECRET_KEY`. Changing the key signs everyone out.
- Revoked and issued refresh tokens are kept in the database. Clear the expired ones now and
  then: `uv run python manage.py flushexpiredtokens`.

### Security notes

- A wrong password and an unknown email give the same `401` answer.
- Login is limited to 10 attempts a minute per IP address. The limit is per address, not per
  account, so a stranger cannot lock a real customer out. Behind a proxy, set
  `REST_FRAMEWORK["NUM_PROXIES"]` or every caller will look like the proxy.
- Rate limit counters use Django's in-process cache, so each worker counts separately. Use a
  shared cache such as Redis in production.
- Sign up only reads the listed fields. A request that includes `is_staff` or `is_superuser`
  is ignored.
- Sign up says when an email is already registered. That is friendlier but lets someone check
  whether an address has an account.

### API keys

A customer logs into the dashboard with JWT, then creates one or more API keys. Transaction
endpoints accept only those keys. A JWT cannot call `/api/v1/transactions`, and an API key
cannot manage the account, settle funds or request a payout.

**How a key is built**

1. 8 random bytes (lookup) and 32 random bytes (secret) from the OS CSPRNG (`secrets`).
2. The key the customer receives: `apk_<lookup>_<secret>`.
3. What is stored: the lookup prefix, the last four characters, and
   `HMAC-SHA256(pepper, full_key)`. The secret is not stored and cannot be recovered.

HMAC is a keyed hash, not reversible encryption. A database dump does not contain working
keys. HMAC is used rather than bcrypt because the secret already has 256 bits of entropy,
so stretching would only slow every payment request.

**Using a key**

```bash
# create one (JWT)
curl -X POST localhost:8000/api/v1/customers/me/api-keys \
  -H 'Authorization: Bearer <access>' -H 'Content-Type: application/json' \
  -d '{"name": "Production", "expires_at": "2027-01-01T00:00:00Z"}'
# { "key": "apk_a1b2…_…", "prefix": "apk_a1b2…", "last_four": "xYzA", "expires_at": "…", … }

# call the payment API
curl localhost:8000/api/v1/payments/whoami -H 'X-API-Key: apk_…'
# Authorization: Api-Key apk_… is also accepted
```

`expires_at` is required, must be in the future, and at most 365 days away. A customer may
hold 20 active keys. Revoked and expired keys do not count. After revoke, the key is refused
at once with `401`. `last_used_at` is updated on each successful payment call.

`API_KEY_PEPPER` should be set in production. If it is left empty, the pepper is derived from
`DJANGO_SECRET_KEY`, so changing that secret revokes every API key as well as every JWT.

### Bank accounts, balances and payouts

There are two money movements, and they are not the same thing.

**Transactions** go through AirPay — card, UPI or netbanking. The gateway calls the
matching service. The customer's wallet is credited (unsettled) only when that
service reports `SUCCESS`. A declined card, a pending UPI collect, or a cancelled
netbanking login does not change the wallet.

**Payouts** are direct bank transfers of **settled** funds to a beneficiary account
the customer has added. They never go through the card/UPI/netbanking rails.

| Amount | Meaning |
| --- | --- |
| **Unsettled** | Successful AirPay collections that cannot be paid out yet. |
| **Settled** | Money available for a bank-transfer payout. |

```
POST /api/v1/transactions          API key   →  rail →  SUCCESS? unsettled ↑
POST /api/v1/customers/me/settle   JWT       →  unsettled ↓  settled ↑  (chosen bank account + amount)
POST /api/v1/customers/me/payouts  JWT       →  settled ↓  (mock NEFT/IMPS)
```

**Commission.** AirPay keeps a commission on every successful collection. It is taken
out of the amount that lands in **unsettled**, and shown on the transaction as
`commission`, `commission_rate` (percent) and `net_amount`.

| Payment | Rate |
| --- | --- |
| Credit card — Visa, Mastercard | 1% |
| Credit card — Diners, American Express | 4% |
| Credit card — RuPay | 0.5% |
| Netbanking | 2% |
| UPI | 1% |

Debit cards are not in the schedule and are charged nothing. The commission is rounded
half up to the paise and is fixed when the wallet is credited, so a later rate change
does not touch past transactions. Failed or pending payments pay no commission. Each
success writes two ledger rows: a `COLLECTION` credit for the full amount and a
`COMMISSION` debit for the fee. Rates live in `payments/commission.py`.

`method` on a transaction is `CARD`, `UPI` or `NETBANKING`. Card is decided in the
same request. UPI and netbanking start as `PENDING`; `GET /api/v1/transactions/{id}`
asks the rail again and credits the wallet if it has succeeded. The full card
number and CVV are sent to the card service only and are never stored.

Balances change only in `payments/wallet.py`, under a row lock, with a matching
`LedgerEntry`. A failed payout puts the money back on settled. Tests recompute both
amounts from the ledger and check they match the wallet.

Account numbers are encrypted with Fernet. The API never returns the full number, only
`account_number_last_four` and the IFSC.

Mock payout declines, so every path can be tested: account numbers ending in `0000`,
and IFSCs starting with `FAIL`, fail the transfer and restore settled funds.
Minimum payout is ₹1.

`POST /transactions` and `POST /payouts` accept `Idempotency-Key`. A replay of the same
request returns the same record. A different body with the same key is `409`.

### Refunds

A customer can send money back to a payer for a payment that succeeded. Refunds need a
JWT. An API key cannot refund, because it is the credential your payment page holds.

```
POST /api/v1/customers/me/transactions/{id}/refunds   {"amount": "250.00", "reason": "…"}
```

**Rules**

- Only a `SUCCESS` payment whose wallet credit was made can be refunded. Pending, failed,
  expired and cancelled payments get `422`.
- Refund up to the amount not yet refunded. Several partial refunds are fine. Asking for more
  than is left is `400` on `amount`. Leave `amount` out to refund everything that is left.
- The payment stays `SUCCESS`. Its `refunded`, `refundable` and `refund_status` change.
- There is no time limit.

**Where the money comes from.** The refund is taken from the customer's wallet, **unsettled
first, then settled**. If the wallet cannot cover it, because the money was paid out, the
refund is refused with `400` and nothing changes. Balances change only in
`payments/wallet.py` (`debit_refund`), under a row lock, with ledger rows of kind `REFUND`
and `COMMISSION_REVERSAL`.

**Commission.** AirPay returns its commission in proportion to what is refunded, so a full
refund leaves the wallet exactly as it was before the payment. Refunding ₹250 of a ₹1,000
UPI payment (1%) takes ₹250 out and puts ₹2.50 of commission back, so ₹247.50 leaves the
wallet (`net_debit`). The share is worked out on the running total refunded and rounded half
up, minus what was already returned, so it never drifts: however a payment is split, the
parts add up to exactly the commission charged (`commission_to_return` in
`payments/refunds.py`).

**The payer's bank is a mock.** The card, UPI and netbanking services have no refund
endpoint, so the gateway decides the outcome itself (`_processor_verdict`). A refund
whose amount ends in **99 paise** (for example `100.99`) is declined: the refund is saved as
`FAILED` with a `failure_reason`, no money moves, and none of the refundable amount is used up.
To use a real rail later, replace `_processor_verdict` with a call to it. The call has to run
before the wallet is debited.

`POST …/refunds` accepts `Idempotency-Key`. A replay of the same request returns the same
refund with `200`. The same key with a different amount or reason is `409`. A refund that
failed is a result too, so retry it with a new key.

### Staff accounts

`uv run python manage.py createsuperuser` asks for a username, email, password and the company
fields. The admin at `/admin/` uses a session login and is separate from the JWT API.

## Adding a feature

1. `uv run python manage.py startapp payments`, then add `"payments"` to `INSTALLED_APPS`.
2. Write serializers, views and `payments/urls.py`.
3. Mount it in `config/urls.py`: `path("api/v1/", include("payments.urls"))`.
4. Give each view an `operation_id` and `tags` with `@extend_schema`, so the docs stay tidy.
5. Run the tests. They also check that the schema still generates cleanly.
