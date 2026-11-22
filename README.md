# DFS COMMAND CENTER PRO

A self-hostable NBA + NFL DraftKings DFS analytics starter application. It includes a working FastAPI backend, CSV salary import, configurable scoring, baseline sport-aware projections, ownership estimates, reproducible Monte Carlo simulation, contest-configurable lineup optimization, CSV export, and a responsive dark dashboard.

## Current implementation status

**Working locally with CSV data:** API, SQLite persistence, CSV import, projections, simulations, lineup optimization, export, health endpoint, and dashboard.

**Requires configuration / further integration:** live licensed sports data, official injury/news feeds, real historical ownership, production authentication, hosted PostgreSQL, managed background workers, and calibrated ML models. The 100-model registry is an extensible set of distinct analytical configurations; its outputs are estimates and should be calibrated against historical data before wagering decisions.

No live salaries, player statuses, ownership, or projections are fabricated. Upload a current DraftKings salary file to work with a real slate.

## Quick start (local)

Requirements: Python 3.11+.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Open http://127.0.0.1:8000. API docs: http://127.0.0.1:8000/docs.

SQLite is used by default. To use PostgreSQL, set `DATABASE_URL` to a SQLAlchemy URL, for example:
`postgresql+psycopg://user:password@host:5432/dfs_command_center`

## CSV import

Upload a DraftKings salary CSV from the dashboard or call `POST /api/import/csv` as multipart form data with:
- `sport`: `NBA` or `NFL`
- `file`: CSV file

The importer recognizes common DraftKings headers such as `ID`, `Name`, `Position`, `Salary`, `Game Info`, `TeamAbbrev`, and `AvgPointsPerGame`. It stores source and timestamp metadata. Duplicate IDs in a file are rejected. Rows without player ID, name, position, or valid salary are rejected. Position eligibility is retained as a comma-separated list.

After import:
1. Select the imported slate.
2. Review players in the player pool.
3. Run projections.
4. Run simulations if desired.
5. Optimize lineups using a contest roster template.

## API overview

- `GET /api/health`
- `GET /api/slates`
- `GET /api/players?sport=NBA&slate_id=...`
- `POST /api/import/csv`
- `POST /api/projections/run`
- `POST /api/simulations/run`
- `POST /api/optimizer/run`
- `GET /api/lineups/{lineup_id}/export`
- `GET /api/models`

## Contest roster configuration

The optimizer takes `slots` as a list of `{name, eligible}` objects and a `salary_cap`. Defaults are provided for common NBA and NFL classic formats, but the supplied contest configuration is authoritative. Edit the roster template in the request when your contest differs.

## Online deployment

This repository is portable and can be deployed to a Python-capable host (for example, Render, Railway, Fly.io, or a VPS). For an online deployment:
1. Create a managed PostgreSQL database.
2. Set `DATABASE_URL`.
3. Set `APP_ENV=production`.
4. Configure HTTPS and a persistent secret (`APP_SECRET`).
5. Deploy the repository using the included `Dockerfile`.
6. Add licensed data provider credentials only as server-side environment variables.

This package does not create a hosting account or provision paid infrastructure. The app is ready to deploy, but it is not publicly online until you choose a host and deploy it.

## Important limitations

- Baseline projection distributions are analytical estimates, not guaranteed outcomes.
- Ownership is explicitly an estimate, never verified DraftKings field ownership.
- Without current stats and role/injury feeds, the engine uses only uploaded player-pool fields and conservative defaults.
- Do not use demo data as current slate data.
- The initial optimizer uses an exact branch-and-bound search for small/medium pools with pruning and a bounded fallback for larger pools. Install OR-Tools for more advanced portfolio constraints in the next iteration.
- This is an initial functional foundation, not a claim of a fully audited production wagering system.
