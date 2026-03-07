"""Seed data for FinAlly database."""

SEED_SQL = """
-- Seed default user profile with $10,000
INSERT OR REPLACE INTO users_profile (id, cash_balance, created_at)
VALUES ('default', 10000.0, datetime('now'));

-- Seed default watchlist with 10 tickers
INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at)
VALUES
    ('a1', 'default', 'AAPL', datetime('now')),
    ('a2', 'default', 'GOOGL', datetime('now')),
    ('a3', 'default', 'MSFT', datetime('now')),
    ('a4', 'default', 'AMZN', datetime('now')),
    ('a5', 'default', 'TSLA', datetime('now')),
    ('a6', 'default', 'NVDA', datetime('now')),
    ('a7', 'default', 'META', datetime('now')),
    ('a8', 'default', 'JPM', datetime('now')),
    ('a9', 'default', 'V', datetime('now')),
    ('a10', 'default', 'NFLX', datetime('now'));
"""
