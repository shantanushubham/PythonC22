# Payment Gateway (Mock) — Node + Express + TypeScript

A lightweight mock payment gateway that simulates a bank credit/debit transaction flow.
There is **no database** — all state is kept in an in-memory `Map` and is lost on restart.
Every transaction has a **25% chance of randomly failing**, to simulate real-world gateway flakiness.

## Setup

```bash
npm install
npm run dev     # start with hot-reload (ts-node-dev)
# or
npm run build && npm start   # compile then run
```

Server starts on `http://localhost:3000` (override with `PORT` env var).

## API

### 1. `POST /api/transactions`

Submit a credit/debit transaction against a bank account. ~25% of requests will randomly fail.

Request body:

```json
{
  "accountNumber": "123456789012",
  "ifsc": "HDFC0001234",
  "accountName": "John Doe",
  "bankName": "HDFC Bank",
  "transactionType": "credit",
  "amount": 1500.50
}
```

- `accountNumber`: numeric string, 9-18 digits
- `ifsc`: valid IFSC format, e.g. `HDFC0001234`
- `accountName` / `bankName`: non-empty strings
- `transactionType`: `"credit"` | `"debit"`
- `amount`: positive number

Success response (`200`):

```json
{
  "success": true,
  "data": {
    "transactionId": "txn_...",
    "status": "SUCCESS",
    "transactionType": "credit",
    "amount": 1500.5,
    "bankDetails": { "...": "..." },
    "createdAt": "2026-09-19T...",
    "processedAt": "2026-09-19T..."
  }
}
```

Simulated failure response (`402`):

```json
{
  "success": false,
  "data": {
    "transactionId": "txn_...",
    "status": "FAILED",
    "failureReason": "Insufficient funds",
    "...": "..."
  }
}
```

Validation error response (`400`):

```json
{
  "success": false,
  "message": "Validation failed",
  "errors": [{ "field": "ifsc", "message": "ifsc must be a valid IFSC code (e.g. HDFC0001234)" }]
}
```

### 2. `GET /api/transactions/:transactionId`

Fetch the result of a previously processed transaction (in-memory lookup only — resets on server restart).

- `200` with the transaction record if found
- `404` if the ID is unknown

### `GET /health`

Basic health check, returns `{ "status": "ok" }`.

## Notes

- Failure rate is defined by `FAILURE_RATE` in `src/services/paymentGatewayService.ts`.
- No persistence layer of any kind is used, per requirements.
