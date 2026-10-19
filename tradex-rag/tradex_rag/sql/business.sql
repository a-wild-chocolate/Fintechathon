CREATE TABLE IF NOT EXISTS companies (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, country TEXT NOT NULL,
 base_currency TEXT NOT NULL, planning_start TEXT NOT NULL,
 financial_version INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS counterparties (
 company_id TEXT NOT NULL REFERENCES companies(id), id TEXT NOT NULL,
 name TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('customer','supplier')),
 country TEXT NOT NULL, PRIMARY KEY(company_id,id)
);
CREATE TABLE IF NOT EXISTS bank_accounts (
 company_id TEXT NOT NULL REFERENCES companies(id), id TEXT NOT NULL,
 name TEXT NOT NULL, currency TEXT NOT NULL, opening_minor INTEGER NOT NULL,
 as_of TEXT NOT NULL, reserved INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(company_id,id)
);
CREATE TABLE IF NOT EXISTS trade_orders (
 company_id TEXT NOT NULL REFERENCES companies(id), id TEXT NOT NULL,
 customer_id TEXT NOT NULL, goods TEXT NOT NULL, currency TEXT NOT NULL,
 total_minor INTEGER NOT NULL, received_minor INTEGER NOT NULL,
 adjustment_minor INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL,
 PRIMARY KEY(company_id,id),
 FOREIGN KEY(company_id,customer_id) REFERENCES counterparties(company_id,id),
 CHECK(total_minor >= received_minor + adjustment_minor)
);
CREATE TABLE IF NOT EXISTS cash_movements (
 company_id TEXT NOT NULL REFERENCES companies(id), id TEXT NOT NULL,
 order_id TEXT, counterparty_id TEXT, label TEXT NOT NULL,
 due_date TEXT NOT NULL, currency TEXT NOT NULL, signed_minor INTEGER NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('expected','obligation','posted')),
 original_currency TEXT, original_minor INTEGER, conversion_basis TEXT,
 PRIMARY KEY(company_id,id),
 FOREIGN KEY(company_id,order_id) REFERENCES trade_orders(company_id,id),
 FOREIGN KEY(company_id,counterparty_id) REFERENCES counterparties(company_id,id)
);
CREATE INDEX IF NOT EXISTS cash_by_date ON cash_movements(company_id,due_date);
CREATE TABLE IF NOT EXISTS business_evidence (
 company_id TEXT NOT NULL REFERENCES companies(id), document_id TEXT NOT NULL,
 document_version INTEGER NOT NULL, order_id TEXT, purpose TEXT NOT NULL,
 PRIMARY KEY(company_id,document_id,purpose),
 FOREIGN KEY(company_id,order_id) REFERENCES trade_orders(company_id,id)
);
CREATE TABLE IF NOT EXISTS financial_revisions (
 company_id TEXT NOT NULL REFERENCES companies(id), version INTEGER NOT NULL,
 snapshot TEXT NOT NULL, reason TEXT NOT NULL, created_at REAL NOT NULL,
 PRIMARY KEY(company_id,version)
);
CREATE TABLE IF NOT EXISTS workspace_views (
 company_id TEXT NOT NULL REFERENCES companies(id), view_key TEXT NOT NULL,
 revision INTEGER NOT NULL, payload TEXT NOT NULL, updated_at REAL NOT NULL,
 PRIMARY KEY(company_id,view_key)
);
CREATE TABLE IF NOT EXISTS company_access (
 owner TEXT NOT NULL, company_id TEXT PRIMARY KEY REFERENCES companies(id)
);
CREATE TABLE IF NOT EXISTS order_terms (
 company_id TEXT NOT NULL, order_id TEXT NOT NULL,
 expected_minor INTEGER NOT NULL, receipt_date TEXT, fx_rate TEXT NOT NULL,
 supplier_id TEXT, supplier_minor INTEGER NOT NULL, supplier_date TEXT,
 PRIMARY KEY(company_id,order_id),
 FOREIGN KEY(company_id,order_id) REFERENCES trade_orders(company_id,id),
 FOREIGN KEY(company_id,supplier_id) REFERENCES counterparties(company_id,id)
);
