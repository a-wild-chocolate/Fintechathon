# Business data and persistence

CashWeave uses FastAPI services, SQLite business records, a versioned document library and Qdrant vectors. The browser loads saved business state from the backend; localStorage is an offline cache and a migration source for older demos.

## Storage locations

Paths are relative to `tradex-rag/`. `TRADEX_DATA_DIR` changes the root directory.

| Location | Contents |
| --- | --- |
| `var/agents.sqlite3` | Company, counterparties, accounts, orders, cash movements, financial revisions, saved workspace views, AI sessions, runs, proposals and drafts |
| `var/library.sqlite3` | Document metadata, original-file versions, sections, chunks, indexing jobs, leases and document events |
| `var/files/` | Original uploaded files and their versions |
| `var/qdrant/` | Local vector index; remote Qdrant can be configured separately |

[Business SQL](../tradex-rag/tradex_rag/sql/business.sql) runs when the backend starts. Existing accepted `agent_workspaces` forecasts migrate once into relational records. A fresh database is created automatically; completing the demo baseline or saving the standard demo creates its business records.

## Business schema

| Table | Record and relationships |
| --- | --- |
| `companies` | Company identity, country, reporting currency, planning start and financial version |
| `counterparties` | Customers and suppliers belonging to a company |
| `bank_accounts` | Currency-specific opening balances, balance date and reserved-funds flag |
| `trade_orders` | Customer, goods, order value, settled value, adjustments and order status |
| `cash_movements` | Expected receipts and payment obligations, linked to an order and counterparty where applicable, with date, currency, amount and conversion basis |
| `business_evidence` | Document/version references associated with an order or the company |
| `financial_revisions` | Accepted financial-state versions and change reasons |
| `workspace_views` | Saved UI conversations, upload workflow state, reminder preferences and navigation context |
| `company_access` | Companies belonging to the configured local workspace |
| `order_terms` | Editable receipt amount/date, explicit FX assumption and supplier payment terms |

Money is stored as integer minor units (for example, CNY 128,000 is `12800000`). Every business record belongs to a company, and composite foreign keys link orders, counterparties and movements within that company. SQLite foreign-key enforcement is enabled on each connection.

Financial values are removed from the saved workspace JSON and reconstructed from business tables on reads. `agent_workspaces` remains a compatibility snapshot written in the same transaction; financial tools read the relational state. Run outputs retain historical snapshots for their execution record.

## Shared update path

1. Uploads enter the document library, retaining their original files and version identifiers.
2. Extraction and user clarification produce a proposal rather than a bank receipt.
3. Confirmation updates the expected cash movement, financial version, evidence links and proposal status in one business-database transaction.
4. The frontend receives that version and recomputes the cash view. AI tools subsequently read the same accepted records.
5. Page state is saved through a serialized, debounced request. A separate browser can restore the saved workspace, including its conversation and task references.

A partial-payment promise changes the expected receipt schedule, while actual account balances and the unsettled order amount remain unchanged. In the demo, a USD 6,000 promise leaves the full USD 12,000 outstanding until actual settlement is recorded.

## API

| Method | Endpoint | Result |
| --- | --- | --- |
| GET | `/api/business` | Company, counterparties, accounts, orders, movements, evidence links and derived financial state |
| GET | `/api/business/workspace?key=main` | Saved UI state overlaid with current business records |
| PUT | `/api/business/workspace?key=main` | Save `{revision, workspace}`; return the next revision and accepted financial state |
| POST | `/api/agents/proposals/{id}/confirm` | Confirm the proposal and update its financial records atomically |

The configured `TRADEX_TENANT` selects the legacy demo scope and owns the local company list; company-prefixed routes select each new company. Stale UI revisions return HTTP 409 rather than overwriting another browser's work; older financial versions cannot overwrite a newer confirmed payment plan. The header shows saving, saved or failed status in Chinese and English.

## Company and order workflow

The default application supports multiple saved companies in one local workspace. Company creation stores the name, country, planning date and CNY/USD opening balances; it creates no sample orders. Order entry supports arbitrary order numbers, customers, goods, USD/EUR/GBP/CNY values, historical receipts, a planned next receipt and a CNY supplier obligation.

`POST /api/companies` creates the company. All subsequent requests use `/api/companies/{id}` before the existing API suffix. `/business/orders/preview` runs the order changes in a transaction and rolls them back after computing before/after forecasts. `/business/orders` creates the order; `/business/orders/{order_id}` edits it with a financial-version check. These commands update counterparties, order terms and movements atomically and append a financial revision.

The normal frontend uses `/business/overview` for company records and server-calculated cash series, and `/business/view` to preserve conversations. It never posts a demo forecast into the new company. A scoped agent runtime shares the service's model adapter and storage while retaining that company's document permissions and financial tools. MCP calls resolve the run's company before executing; another company's run or document cannot be read through the selected company's routes.

One next receipt and one remaining supplier obligation are editable per order. Already received amounts describe history included in the entered opening balances; editing them does not post new bank cash. Expected foreign-currency receipts enter the CNY availability forecast using the saved rate and availability date. Unknown receipt dates leave the balance unscheduled, and events beyond the 56-day horizon are listed separately. Bank feeds, full settlement accounting, multi-user login and multiple receipt instalments per order remain outside this entry flow.

The configured `TRADEX_TENANT` owns the local company list. This is company scoping within the local application, not a user authentication system. Old demo pages remain accessible under `/?demo=1`.

The SQL files and service code belong in Git. Runtime databases, uploads, backups and credentials stay under ignored local directories. To move a complete workspace, back up the entire data directory while the service is stopped, or use SQLite's backup API for each live database and include the referenced files and vector index.

## Verification

- Backend tests cover relational creation, process-restart recovery, company isolation, version conflicts, transaction rollback and the HTTP save/load path.
- The existing clarification/confirmation test verifies that the real workflow service changes an expected receipt to USD 6,000 and recalculates the CNY 34,000 peak gap without recording cash as received.
- Browser verification restored the isolated demo from `127.0.0.1:5176` through `localhost:5176`, a separate localStorage origin: CNY 128,000 opening balance, USD 6,000 expected receipt, CNY 34,000 peak gap and three saved AI turns were preserved.
