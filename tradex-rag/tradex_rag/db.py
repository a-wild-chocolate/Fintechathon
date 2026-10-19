import sqlite3
from contextlib import contextmanager
SCHEMA='''
CREATE TABLE IF NOT EXISTS documents(
 id TEXT PRIMARY KEY, tenant TEXT NOT NULL, title TEXT NOT NULL, source_key TEXT,
 metadata TEXT NOT NULL, latest_version INTEGER NOT NULL DEFAULT 0,
 current_version INTEGER NOT NULL DEFAULT 0, deleted INTEGER NOT NULL DEFAULT 0,
 created_at REAL NOT NULL, UNIQUE(tenant,source_key));
CREATE TABLE IF NOT EXISTS versions(
 document_id TEXT NOT NULL, version INTEGER NOT NULL, filename TEXT NOT NULL,
 path TEXT NOT NULL, status TEXT NOT NULL, created_at REAL NOT NULL,
 PRIMARY KEY(document_id,version), FOREIGN KEY(document_id) REFERENCES documents(id));
CREATE TABLE IF NOT EXISTS parents(
 id TEXT PRIMARY KEY, document_id TEXT NOT NULL, version INTEGER NOT NULL,
 text TEXT NOT NULL, section TEXT NOT NULL, locator TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS chunks(
 id TEXT PRIMARY KEY, document_id TEXT NOT NULL, version INTEGER NOT NULL,
 parent_id TEXT NOT NULL, text TEXT NOT NULL, section TEXT NOT NULL, locator TEXT NOT NULL,
 embedding_model TEXT, FOREIGN KEY(parent_id) REFERENCES parents(id));
CREATE INDEX IF NOT EXISTS chunk_document ON chunks(document_id,version);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(chunk_id UNINDEXED,tokens);
CREATE TABLE IF NOT EXISTS jobs(
 id TEXT PRIMARY KEY, document_id TEXT NOT NULL, version INTEGER NOT NULL,
 operation TEXT NOT NULL, status TEXT NOT NULL, error TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS queued_jobs ON jobs(status,created_at);
CREATE TABLE IF NOT EXISTS leases(
 document_id TEXT PRIMARY KEY, owner TEXT NOT NULL, token TEXT NOT NULL,
 fence INTEGER NOT NULL, expires_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS events(
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant TEXT NOT NULL, kind TEXT NOT NULL,
 document_id TEXT NOT NULL, version INTEGER NOT NULL, payload TEXT NOT NULL, created_at REAL NOT NULL);
'''
class Database:
    def __init__(self,path):
        self.path=path
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL');db.executescript(SCHEMA)
    @contextmanager
    def connect(self,write=False):
        db=sqlite3.connect(self.path,timeout=10);db.row_factory=sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            if write:db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except Exception:
            db.rollback();raise
        finally:db.close()
