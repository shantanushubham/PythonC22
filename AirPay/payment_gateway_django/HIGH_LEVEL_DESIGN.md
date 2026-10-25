# Payment Gateway: High-Level Design

This document explains how the gateway is built and why. For endpoints, configuration and
examples, see the [README](README.md). For how the gateway fits with the three rail services, see
the [AirPay system README](../README.md).

## 1. What it is

The gateway is AirPay's **front door and its book of record**. It does five jobs:

1. **Accounts.** Merchants ("customers") sign up, log in, and manage API keys and bank accounts.
2. **Collecting payments.** It takes a payment request and routes it to the right *rail*: card, UPI
   or netbanking.
3. **Keeping the books.** When a payment succeeds it credits the merchant's wallet, minus AirPay's
   commission, and writes a ledger entry for every movement.
4. **Moving money out.** Settlement (unsettled to settled), bank payouts, and refunds.
5. **Presenting one API.** One error shape, one idempotency rule and one amount format, whatever
   rail is behind a payment.

It does **not** authorize cards, approve UPI requests or log customers in to banks. The rail services
do that. The gateway never decides whether a payment is good, only what to do with the answer.

## 2. Where it sits

```mermaid
flowchart LR
    Dash["Merchant dashboard<br/>(React, :5173)"]
    App["Merchant's own app<br/>(server-side code)"]
    subgraph GW["Payment gateway (Django + DRF, :8000)"]
        direction TB
        API["REST API /api/v1"]
        Biz["Payment, wallet and refund logic"]
        Adapters["Rail adapters<br/>(requests)"]
        API --> Biz --> Adapters
    end
    DB[("PostgreSQL<br/>accounts, transactions, ledger")]
    Card["Card service<br/>FastAPI :8001"]
    NB["Netbanking service<br/>Go :8002"]
    UPI["UPI service<br/>Node :8003"]

    Dash -- "JWT" --> API
    App -- "X-API-Key" --> API
    Biz --> DB
    Adapters --> Card
    Adapters --> NB
    Adapters --> UPI
```

## 3. How the code is organised

Four Django apps. Each feature has its own app and its own `urls.py`.

```mermaid
flowchart TB
    subgraph config["config/"]
        S["settings.py<br/>env-driven"]
        U["urls.py<br/>mounts /api/v1"]
    end
    subgraph core["core/  (shared)"]
        EXC["exceptions.py<br/>one error shape"]
        MON["money.py<br/>parse_amount, format_amount, AmountField"]
        HV["health view"]
    end
    subgraph customers["customers/  (who you are)"]
        CM["models: Customer, APIKey, BankAccount"]
        AU["authentication.py<br/>APIKeyAuthentication"]
        AC["accounts.py<br/>Fernet encryption"]
        CV["views: signup, login, me, keys, bank accounts"]
    end
    subgraph payments["payments/  (the money)"]
        PM["models: Transaction, Wallet, LedgerEntry,<br/>Settlement, Payout, Refund"]
        PV["views.py"]
        PSV["services.py<br/>transactions, settle, payout"]
        RF["refunds.py"]
        WL["wallet.py<br/>THE ONLY place balances change"]
        CMS["commission.py"]
        IDM["idempotency.py"]
        subgraph rails["rails/  (adapters)"]
            RB["base.py: PaymentRail, RailResult, errors"]
            RC["card.py"]
            RU["upi.py"]
            RN["netbanking.py"]
            RH["http.py: requests"]
        end
    end

    U --> CV
    U --> PV
    PV --> PSV
    PV --> RF
    PSV --> WL
    PSV --> CMS
    PSV --> IDM
    PSV --> rails
    RF --> WL
    RC --> RH
    RU --> RH
    RN --> RH
    PV -. uses .-> AU
    CV -. uses .-> AC
    PV --> EXC
    PSV --> MON
```

The rule that holds this together: **views are thin, services decide, `wallet.py` is the only code
that changes a balance, and `rails/` is the only code that talks to the outside.**

## 4. Who is calling: two credentials

The gateway has two kinds of caller, and they get two kinds of credential on purpose.

```mermaid
flowchart LR
    subgraph JWTside["JWT (Authorization: Bearer ...)"]
        direction TB
        J1["Who: the merchant, in the dashboard"]
        J2["Can: view account, API keys, bank accounts,<br/>balance, settle, payouts, refunds,<br/>transactions list"]
        J3["Cannot: create a payment"]
    end
    subgraph Keyside["API key (X-API-Key: apk_...)"]
        direction TB
        K1["Who: the merchant's server code"]
        K2["Can: create a payment, list and read payments"]
        K3["Cannot: move money out, manage the account"]
    end
```

| | JWT | API key |
| --- | --- | --- |
| **Held by** | A person in a browser | A server, in config |
| **Lifetime** | Access 15 min, refresh 7 days, refresh tokens rotate and are blacklisted after use | Up to 365 days, can be revoked at once |
| **Stored** | Nothing (signed) | Only an HMAC of the secret, plus a public prefix for lookup. The secret is shown once. |
| **Allows** | Everything about the account and the money | Taking payments only |
| **Why separate** | An access token cannot be revoked, so it is short-lived and never put in a page that charges cards. | A leaked key can take payments but cannot pay out, refund or read bank details. |

This split is the most important security decision in the gateway. **A key that can charge cards
cannot also move money out.** Refunds are JWT-only for the same reason.

## 5. Rails: one interface, three adapters

The gateway needs the same two things from every rail: *start a payment* and *tell me where it is
now*. That is the whole interface.

```mermaid
classDiagram
    class PaymentRail {
        <<Protocol>>
        +create(payload, idempotency_key) RailResult
        +fetch(rail_transaction_id) RailResult
    }
    class RailResult {
        rail_transaction_id
        status
        amount
        rail_reference
        failure_reason
        failure_code
        instrument
        redirect_url
        replayed
    }
    class CardRail
    class UpiRail
    class NetbankingRail
    class RailError
    PaymentRail <|.. CardRail
    PaymentRail <|.. UpiRail
    PaymentRail <|.. NetbankingRail
    PaymentRail ..> RailResult : returns
    RailError <|-- RailValidation
    RailError <|-- RailConflict
    RailError <|-- RailNotFound
    RailError <|-- RailUnavailable
```

Each adapter does only translation: build the rail's request body from the gateway's fields, call it
through `rails/http.py` (which uses `requests`), and turn the rail's response into a `RailResult`.

| Rail | Sync? | What the adapter maps |
| --- | --- | --- |
| Card | Answers in the same call | `last4`, `network`, `card_type` to `instrument`. `authorization_code` to `rail_reference`. |
| UPI | `PENDING`, resolves in seconds | Payer VPA and failure code. |
| Netbanking | `PENDING` until the customer finishes at the bank | `bank_code`, `bank_name`, **`redirect_url`**. |

### Rail errors become API errors in one place

| Rail says | Gateway raises | Merchant sees |
| --- | --- | --- |
| `400` validation | `RailValidation` | `400` with the rail's field errors, in the standard shape |
| `409` key reused with a different body | `RailConflict` | `409` |
| `404` unknown payment | `RailNotFound` | Treated as "no news": the transaction is returned unchanged |
| Timeout, refused connection, `5xx`, unreadable reply | `RailUnavailable` | `503` |
| `402` (card declined) | *not an error* | A normal `FAILED` transaction |

A decline is a **business result**, not an exception: the transaction is saved as `FAILED` with a
reason, and the call returns `201`.

## 6. Creating a payment

```mermaid
sequenceDiagram
    autonumber
    actor M as Merchant app
    participant G as Gateway
    participant R as Rail service
    participant DB as PostgreSQL

    M->>G: POST /api/v1/transactions (X-API-Key, Idempotency-Key)
    G->>G: authenticate key, validate body
    G->>DB: key already used by this customer?
    alt same key, same request
        DB-->>G: existing transaction
        G-->>M: 200 existing (refreshed if PENDING)
    else same key, different request
        G-->>M: 409
    else new
        G->>R: POST /api/v1/payments (same Idempotency-Key)
        R-->>G: RailResult (SUCCESS / FAILED / PENDING)
        G->>DB: BEGIN, insert Transaction
        G->>DB: lock the row, apply the outcome
        opt status is SUCCESS
            G->>DB: credit wallet (unsettled) and write ledger rows
        end
        G->>DB: COMMIT
        G-->>M: 201 transaction
    end
```

Two details matter:

- **The rail is called before the local row exists, and outside any database transaction.** A slow
  rail never holds a database lock. The cost is described in section 11.
- **The same `Idempotency-Key` is passed to the rail**, so a retry that reaches the rail again gets the
  original rail payment back instead of a second one.

### Pending payments finish later

UPI and netbanking return `PENDING`. The gateway has **no webhook** from the rails, so it learns the
result by asking.

```mermaid
sequenceDiagram
    autonumber
    participant D as Dashboard / merchant
    participant G as Gateway
    participant R as Rail
    D->>G: GET /transactions/{id}
    G->>G: status is PENDING and a rail id exists
    G->>R: GET /api/v1/payments/{rail_id}
    R-->>G: SUCCESS / FAILED / EXPIRED / CANCELLED
    G->>G: apply_outcome (lock, write, credit once)
    G-->>D: current transaction
```

`refresh_transaction` runs on every **detail** read of a `PENDING` payment. The **list** endpoint does
not call the rails, so a long list stays fast and cannot fan out into dozens of rail calls. The
dashboard therefore polls the detail endpoint for anything pending.

## 7. A transaction's life, and crediting exactly once

```mermaid
stateDiagram-v2
    [*] --> PENDING: UPI or netbanking started
    [*] --> SUCCESS: card approved
    [*] --> FAILED: card declined
    PENDING --> SUCCESS
    PENDING --> FAILED
    PENDING --> EXPIRED
    PENDING --> CANCELLED
    SUCCESS --> [*]: credited once
    FAILED --> [*]
    EXPIRED --> [*]
    CANCELLED --> [*]
```

Several requests can learn about the same result at once: a poll, a retry, the dashboard, the
merchant's own check. The wallet must be credited **exactly once**. `apply_outcome` guarantees this:

```mermaid
flowchart TD
    A["apply_outcome(txn, rail result)"] --> B["SELECT ... FOR UPDATE on the transaction row"]
    B --> C{"Already final?"}
    C -- "yes" --> D{"SUCCESS but credited_at is empty?"}
    D -- "yes (crash recovery)" --> E["credit now"]
    D -- "no" --> Z["return unchanged"]
    C -- "no" --> F{"Rail amount equals our amount?"}
    F -- "no" --> G["mark FAILED:<br/>amount does not match"]
    F -- "yes" --> H["write status, references, instrument"]
    H --> I{"SUCCESS and credited_at empty?"}
    I -- "yes" --> J["commission = rate x amount<br/>credit wallet, set credited_at"]
    I -- "no" --> K["save"]
    J --> K
```

- The **row lock** serializes concurrent callers: the second one waits, then finds a final state.
- **`credited_at`** is the "already paid" marker. A `SUCCESS` with no `credited_at` is credited
  late, which repairs a crash between the status write and the credit.
- The gateway **checks the amount the rail reports** against its own. A mismatch fails the payment
  instead of crediting the wrong sum.

## 8. Money: one wallet, one ledger

All amounts are **integer paise** in the database and rupee strings (`"1500.50"`) in the API, so
floats never touch money. `AmountField` does the conversion at the edge.

```mermaid
flowchart LR
    P(("Payer")) -- "SUCCESS" --> U["UNSETTLED<br/>collected, not yet payable"]
    U -- "Commission<br/>(AirPay keeps it)" --> AP(("AirPay"))
    U -- "Settle<br/>POST /settle" --> S["SETTLED<br/>available to pay out"]
    S -- "Payout<br/>POST /payouts" --> BANK(("Merchant's bank"))
    U -- "Refund (first)" --> P
    S -- "Refund (then)" --> P
    AP -- "Commission returned,<br/>in proportion" --> U
```

| Movement | Wallet effect | Ledger rows |
| --- | --- | --- |
| Payment succeeds | Unsettled up by amount, then down by commission | `COLLECTION` credit, `COMMISSION` debit |
| Settle | Unsettled down, settled up | `SETTLEMENT` debit and credit |
| Payout | Settled down | `PAYOUT` debit |
| Payout fails | Settled restored | `PAYOUT_REVERSAL` credit |
| Refund | Commission back to unsettled, then refund from unsettled, then from settled | `COMMISSION_REVERSAL` credit, `REFUND` debit(s) |

### The wallet cannot be wrong

- **Single writer.** `payments/wallet.py` is the only code that changes `Wallet`. Every change writes
  a `LedgerEntry` in the same database transaction, under `SELECT ... FOR UPDATE` on the wallet row,
  so two payouts cannot spend the same rupee.
- **Database guards.** `CHECK (unsettled_paise >= 0)` and `CHECK (settled_paise >= 0)` mean a bug in
  the code still cannot create a negative balance.
- **The ledger is the proof.** `ledger_totals()` recomputes both balances from the ledger. Tests
  assert it equals the wallet after every kind of operation.

### Commission

AirPay's fee is worked out **once**, when the wallet is credited, from the method and instrument
(for example credit Visa 1%, Amex 4%, UPI 1%, netbanking 2%, debit 0%). It is stored on the
transaction (`commission_rate_bps`, `commission_paise`), so a later rate change never rewrites
history. Rates live in `payments/commission.py`.

### Refunds

A refund sends money back to a payer from the merchant's wallet:

```mermaid
flowchart TD
    A["POST .../transactions/{id}/refunds (JWT)"] --> B["Replay if Idempotency-Key was used"]
    B --> C["Lock the transaction row"]
    C --> D{"SUCCESS and credited?"}
    D -- "no" --> E["422 not refundable"]
    D -- "yes" --> F{"amount <= refundable?"}
    F -- "no" --> G["400 on amount"]
    F -- "yes" --> H["Mock processor verdict<br/>(amount ending in 99 paise declines)"]
    H -- "declined" --> I["Save FAILED refund<br/>no money moves"]
    H -- "approved" --> J["wallet.debit_refund<br/>returns commission share,<br/>takes unsettled then settled"]
    J -- "not enough money" --> K["400, nothing saved"]
    J -- "ok" --> L["Save SUCCESS refund,<br/>update refunded and commission_refunded"]
```

The commission returned is `round(commission x refunded_so_far / amount)` minus what was already
returned, so split refunds add up to **exactly** the commission charged, never a paisa more or less.

## 9. Data

```mermaid
erDiagram
    Customer ||--o{ APIKey : issues
    Customer ||--o{ BankAccount : owns
    Customer ||--|| Wallet : has
    Customer ||--o{ Transaction : collects
    Customer ||--o{ LedgerEntry : "money moved"
    Customer ||--o{ Settlement : requests
    Customer ||--o{ Payout : requests
    Customer ||--o{ Refund : makes
    Transaction ||--o{ Refund : "refunded by"
    BankAccount ||--o{ Settlement : "settled to"
    BankAccount ||--o{ Payout : "paid to"

    Customer {
        uuid id PK
        string email UK
        string company_name
    }
    APIKey {
        string prefix UK "public lookup"
        string secret_hash UK "HMAC, secret never stored"
        datetime expires_at
        datetime revoked_at
    }
    BankAccount {
        string account_number_encrypted "Fernet"
        string last_four
        string ifsc
    }
    Wallet {
        bigint unsettled_paise "CHECK >= 0"
        bigint settled_paise "CHECK >= 0"
    }
    LedgerEntry {
        bigint amount_paise
        string bucket "UNSETTLED or SETTLED"
        string direction "CREDIT or DEBIT"
        string kind "COLLECTION, COMMISSION, REFUND, ..."
        uuid reference_id "the transaction, payout, ..."
    }
    Transaction {
        uuid id PK
        string method "CARD, UPI, NETBANKING"
        string status
        bigint amount_paise
        bigint commission_paise
        bigint refunded_paise "CHECK 0..amount"
        string rail_transaction_id
        string idempotency_key "unique per customer"
        datetime credited_at "the already-paid marker"
    }
    Settlement {
        bigint amount_paise
    }
    Payout {
        bigint amount_paise
        string status
        string idempotency_key "unique per customer"
    }
    Refund {
        bigint amount_paise
        bigint commission_returned_paise
        string status "SUCCESS or FAILED"
        string idempotency_key "unique per customer"
    }
```

Bank account numbers are **encrypted** (Fernet). The API only ever returns the last four digits and
the IFSC. A transaction keeps only a masked instrument (card `last_four` and network, a VPA, a bank
name), never a full card number or CVV, which go to the card service and nowhere else.

## 10. Idempotency

Payments, payouts and refunds all accept an `Idempotency-Key`, and they all work the same way:

```mermaid
flowchart TD
    A["Request with Idempotency-Key"] --> B{"Key already stored<br/>for this customer?"}
    B -- "no" --> C["Do the work, store the key and a fingerprint of the request"]
    B -- "yes" --> D{"Same fingerprint?"}
    D -- "yes" --> E["Return the original result (200)"]
    D -- "no" --> F["409 Conflict"]
    C --> G{"Unique constraint hit?<br/>(a twin request won the race)"}
    G -- "yes" --> B
    G -- "no" --> H["Done (201)"]
```

- A **fingerprint** is a SHA-256 of the meaningful fields of the request. It separates a *retry* from a
  *different request that reused a key*.
- A **unique constraint** on `(customer, idempotency_key)` settles races in the database. If two
  identical requests arrive together, one inserts and the other hits the constraint, loads the winner,
  and returns it.
- Keys are **per customer**, so one merchant's key can never collide with another's.
- A refund the mock bank *declined* is a stored result too. To try again, use a new key.

## 11. Design approach and why

| Decision | Why |
| --- | --- |
| **Gateway holds no payment logic of its own** | Rails decide if a payment is good. The gateway only routes and records. Replacing a rail means writing one adapter. |
| **`PaymentRail` protocol and `RailResult`** | Three very different rails (sync, async, redirect) look identical to the business code. |
| **A single HTTP helper (`rails/http.py`, `requests`)** | Timeouts, connection errors and unreadable replies become one `RailUnavailable`. HTTP error statuses are returned, not raised, so the caller decides what each means. |
| **Two credentials with different powers** | A leaked payment key cannot drain a wallet. See section 4. |
| **Integer paise everywhere** | No float rounding in money. Rupee strings only at the API edge. |
| **One writer for balances, plus a ledger and CHECK constraints** | Three independent safeguards: the code path, the audit trail, and the database. |
| **Row locks (`select_for_update`) over application locks** | The database already provides correct locking, and it works across several gateway processes. |
| **`credited_at` marker and a locked `apply_outcome`** | Crediting is idempotent and self-repairing, even if a poll, a retry and a crash all collide. |
| **Poll rails on detail reads, not on lists** | No webhooks exist, so asking is the only way to learn. Keeping lists rail-free keeps them fast. |
| **Commission frozen on the transaction** | History does not change when rates do. |
| **One error shape for everything** | `{success, message, errors[{field, message}]}`, matching the rails, so the dashboard has one parser. Validation is `400`. |
| **OpenAPI generated, and checked by a test** | Every view declares its schema, and a test fails if schema generation warns, so the docs cannot drift. |
| **Postgres in production, SQLite for tests** | Real locking and constraints where it matters, fast tests everywhere else. `DB_ENGINE=sqlite` switches. |

## 12. Failure behaviour

| Situation | What happens |
| --- | --- |
| A rail is down or slow (over `RAIL_TIMEOUT_SECONDS`, default 10 s) | `503`. Nothing is saved. |
| Card declined | `201`, status `FAILED`, reason stored, wallet untouched. |
| Retry with the same key | The original transaction, never a second charge. |
| Retry with a different body, same key | `409`. |
| Two polls learn `SUCCESS` together | Wallet credited once (row lock plus `credited_at`). |
| Rail reports a different amount | Transaction `FAILED`, nothing credited. |
| Payout bank declines | Settled balance restored, ledger shows the reversal. |
| Refund when the money was already paid out | `400`, nothing changes. |
| Refund declined by the mock bank | `FAILED` refund recorded, no money moves, refundable amount unchanged. |
| Login guessing | Throttled to 10 attempts a minute per IP. |

## 13. Limits and known gaps

- **Crash window on create.** The rail is called *before* the local transaction is saved. If the
  gateway dies in between, the rail has a payment the gateway never recorded. Retrying with the same
  `Idempotency-Key` recovers it, because the rail replays its original result. Without a key it is an
  orphan. A fix is to save a `PENDING` row *before* calling the rail.
- **Pending payments are credited by polling.** If nobody reads a pending UPI or netbanking payment,
  it stays `PENDING` here even after the rail finished it. A background reconciliation job, or a
  webhook from the rails, would close this.
- **Refunds are a mock.** The rails have no refund endpoint, so the gateway's own mock processor
  decides (a refund ending in 99 paise is declined). Real refunds need an endpoint on each rail.
- **The request fingerprint is an unsalted SHA-256** whose input includes the card number for card
  payments. For a mock that is acceptable. A real gateway should use an HMAC with a secret, or leave
  sensitive fields out of the hashed input.
- **Rails have no authentication.** The gateway trusts them on the network. They must not be exposed
  publicly.
- **List endpoints are not paginated.** They return every row, even though DRF's pagination class is
  configured in settings (no view uses it). That is fine for hundreds of payments and not for
  hundreds of thousands. The dashboard filters and pages in the browser.
- **One database, one region.** There is no sharding, read replica or queue.
