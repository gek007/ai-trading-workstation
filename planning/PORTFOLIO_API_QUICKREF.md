# Portfolio API Quick Reference

## Base URL
```
http://localhost:8000/api/portfolio
```

## Endpoints

### Get Portfolio
```http
GET /api/portfolio
```

**Response (200 OK)**:
```json
{
  "cash_balance": 10000.00,
  "total_value": 15000.00,
  "positions": [
    {
      "ticker": "AAPL",
      "quantity": 10.5,
      "avg_cost": 185.00,
      "current_price": 190.50,
      "market_value": 2000.25,
      "cost_basis": 1942.50,
      "unrealized_pl": 57.75,
      "unrealized_pl_percent": 2.97
    }
  ],
  "total_unrealized_pl": 234.50,
  "total_unrealized_pl_percent": 1.56
}
```

### Execute Trade
```http
POST /api/portfolio/trade
Content-Type: application/json

{
  "ticker": "AAPL",
  "quantity": 10.5,
  "side": "buy"
}
```

**Response (200 OK)**:
```json
{
  "status": "executed",
  "trade": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "ticker": "AAPL",
    "side": "buy",
    "quantity": 10.5,
    "price": 190.50,
    "total_value": 2000.25,
    "executed_at": "2025-01-15T10:30:45.123Z"
  },
  "portfolio": { ... }
}
```

## Validation Rules

### Ticker
- Format: 1-5 uppercase letters (auto-normalized)
- Pattern: `^[A-Z]+$`
- Must be in watchlist/price cache

### Quantity
- Range: 0.0001 to 1,000,000
- Precision: Max 4 decimal places
- Fractional shares supported

### Side
- Values: `"buy"` or `"sell"`

## Error Codes

| Code | Status | Description |
|------|--------|-------------|
| `INVALID_REQUEST` | 400 | Invalid request body |
| `INVALID_TICKER` | 400 | Ticker format invalid |
| `INVALID_QUANTITY` | 400 | Quantity out of range |
| `INVALID_SIDE` | 400 | Invalid trade side |
| `INSUFFICIENT_CASH` | 400 | Not enough cash to buy |
| `INSUFFICIENT_SHARES` | 400 | Not enough shares to sell |
| `TICKER_NOT_FOUND` | 404 | Ticker not in watchlist |
| `INTERNAL_ERROR` | 500 | Server error |

## Example Error Response

```json
{
  "detail": "Insufficient cash: need $2000.25, have $1000.00"
}
```

## Test Coverage

- **97% code coverage**
- **39 tests, all passing**
- 21 service layer tests
- 18 integration tests

## Files

- **Models**: `/backend/app/portfolio/models.py`
- **Service**: `/backend/app/portfolio/service.py`
- **Router**: `/backend/app/portfolio/router.py`
- **Tests**: `/backend/tests/portfolio/`
