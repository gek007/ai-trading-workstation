# Database Location - RESOLVED ✅

**Critical Blocker #2 from Implementation Readiness Review - RESOLVED**

## Decision Made

All database files are consolidated under **`backend/db/`** only.

## Updated Directory Structure

```
finally/
├── backend/
│   └── db/                       # All database files (single location)
│       ├── schema.sql            # Database schema (committed to git)
│       ├── seed.sql              # Default seed data (committed to git)
│       └── finally.db            # Runtime database (gitignored, volume-mounted)
├── frontend/
├── planning/
├── scripts/
├── test/
├── Dockerfile
├── docker-compose.yml
├── .env
└── .gitignore
```

## What Changed

### Removed
- ❌ Root `db/` directory (no longer exists)
- ❌ Confusion about dual database locations

### Updated
- ✅ Directory structure diagram shows only `backend/db/`
- ✅ "Key Boundaries" section clarifies `backend/db/` contains everything
- ✅ Docker volume mount updated to `/app/backend/db` (not `/app/db`)
- ✅ Architecture overview updated to `backend/db/finally.db`

## Docker Volume Mapping

**Before:**
```bash
docker run -v finally-data:/app/db -p 8000:8000 --env-file .env finally
# Root db/ maps to /app/db
```

**After:**
```bash
docker run -v finally-data:/app/backend/db -p 8000:8000 --env-file .env finally
# backend/db/ maps to /app/backend/db
```

## Clarified Boundaries

**`backend/db/` contains:**
- `schema.sql` - SQL schema definitions (committed to git)
- `seed.sql` - Default seed data (committed to git)
- `finally.db` - Runtime SQLite database (gitignored, created on first run, persisted via Docker volume)

**Database initialization (lazy):**
1. Backend checks if `backend/db/finally.db` exists on startup
2. If not found (or empty), reads `backend/db/schema.sql` to create tables
3. Reads `backend/db/seed.sql` to populate default data
4. All future reads/writes go to `backend/db/finally.db`

## Benefits

1. **Single source of truth** - All database-related files in one directory
2. **Clearer for developers** - No confusion about where database files live
3. **Simpler Docker setup** - One volume mount point
4. **Easier local development** - Backend team owns entire `backend/` directory including database
5. **Consistent with backend ownership** - Backend agent responsible for everything under `backend/`

## Impact on Implementation

### Backend Agent
- ✅ Knows exactly where to create database: `backend/db/finally.db`
- ✅ Knows where schema files go: `backend/db/schema.sql`
- ✅ Knows where seed files go: `backend/db/seed.sql`
- ✅ Can initialize database on first request without ambiguity

### Frontend Agent
- ✅ No changes needed (frontend doesn't interact with database directly)

### DevOps/Docker
- ✅ Volume mount is clear: `/app/backend/db`
- ✅ No confusion about multiple db directories

## Files Updated

1. `planning/PLAN.md`:
   - Directory structure (lines 87-107)
   - Architecture overview (line 67)
   - Key Boundaries section (lines 109-117)
   - Docker Volume section (lines 394-402)
   - Review section (line 464)

2. `planning/PLAN_IMPLEMENTATION_READINESS_REVIEW.md`:
   - Marked Blocker #2 as resolved (to be updated)

## Next Steps

This resolution eliminates **Critical Blocker #2**. The backend agent can now proceed with database implementation without ambiguity.

**Remaining Critical Blockers:**
1. ✅ API Contracts (RESOLVED - see `API_CONTRACTS.md`)
2. ✅ Database Location (RESOLVED - this document)
3. ❌ SSE Streaming Format (RESOLVED in `API_CONTRACTS.md`)
4. ❌ Trade Validation Rules (RESOLVED in `API_CONTRACTS.md`)
5. ❌ Fractional Share Precision (RESOLVED in `API_CONTRACTS.md`)
6. ❌ Main Chart Data Source (still needed)
7. ❌ Portfolio Snapshot Retention (still needed)

**Status:** 5/7 critical blockers resolved ✅

Implementation can proceed on most endpoints. Remaining blockers (#6, #7) are for specific features (main chart and portfolio snapshots) and can be addressed separately.
