"""Seed data for FinAlly database.

Fixed UUIDs are intentional: they make INSERT OR IGNORE idempotent across
multiple init_db calls without generating duplicates.
"""

from __future__ import annotations

SEED_SQL = """
-- Seed default user profile with $10,000 (only on first creation)
INSERT OR IGNORE INTO users_profile (id, cash_balance, created_at)
VALUES ('default', 10000.0, datetime('now'));

-- Seed default watchlist with 10 tickers (fixed UUIDs ensure idempotency)
INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at)
VALUES
    ('00000000-0000-0000-0000-000000000001', 'default', 'AAPL',  datetime('now')),
    ('00000000-0000-0000-0000-000000000002', 'default', 'GOOGL', datetime('now')),
    ('00000000-0000-0000-0000-000000000003', 'default', 'MSFT',  datetime('now')),
    ('00000000-0000-0000-0000-000000000004', 'default', 'AMZN',  datetime('now')),
    ('00000000-0000-0000-0000-000000000005', 'default', 'TSLA',  datetime('now')),
    ('00000000-0000-0000-0000-000000000006', 'default', 'NVDA',  datetime('now')),
    ('00000000-0000-0000-0000-000000000007', 'default', 'META',  datetime('now')),
    ('00000000-0000-0000-0000-000000000008', 'default', 'JPM',   datetime('now')),
    ('00000000-0000-0000-0000-000000000009', 'default', 'V',     datetime('now')),
    ('00000000-0000-0000-0000-000000000010', 'default', 'NFLX',  datetime('now'));
"""
