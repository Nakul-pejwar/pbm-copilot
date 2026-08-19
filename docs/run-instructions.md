# How to Run the PBM Claims Anomaly & Compliance Copilot

## Prerequisites

- Docker (with Docker Compose)
- Python 3.10+ (only needed to generate a sample CSV)
- Optional: an Anthropic API key for real LLM explanations

## 1. Configure environment

From the project root, copy the example env file to `.env`:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Optionally set `CLAUDE_API_KEY` in `.env` to enable real GenAI explanations. Without it, the app falls back to a deterministic explainability mode.

## 2. Start the stack

```bash
docker compose up -d --build
```

This starts four services:

| Service   | URL                          | Notes                              |
|-----------|------------------------------|------------------------------------|
| API + UI  | http://localhost:8000        | Upload UI                          |
| API docs  | http://localhost:8000/docs   | Swagger UI                         |
| Superset  | http://localhost:8088        | Login: `admin` / `admin`           |
| PostgreSQL| localhost:5432               | `postgres` / `postgres`, db `pbm`  |

## 3. Generate the 100K demo claims

```bash
docker compose exec api python -m app.seed
```

Verify with:

```bash
curl http://localhost:8000/metrics
```

Windows PowerShell:

```powershell
Invoke-RestMethod http://localhost:8000/metrics
```

## 4. Upload a company's data

Generate a sample CSV (optional, from the project root, stdlib only):

```bash
python script/make_sample_csv.py --rows 5000          # -> sample_claims.csv
python script/make_sample_csv.py --rows 5000 --seed 7 # different dataset
```

Then open http://localhost:8000, enter a company name, pick the CSV/Excel file, and click **Upload & Process**.

Expected columns (exact, any order): `claim_id`, `claim_date`, `member_id`, `provider_id`, `plan_id`, `product_id`, `quantity`, `days_supply`, `unit_price`, `allowed_unit_price`, `paid_amount`, `allowed_amount`, `provider_claim_count_30d`, `is_duplicate`, `refill_too_soon`, `ndc_mismatch`, `status`.

The upload endpoint (`POST /api/upload`) validates the file, trains a per-company Isolation Forest baseline, applies the business rules, scores every claim, replaces that company's previous rows, and auto-provisions the Superset dashboard (idempotent).

## 5. View the dashboard

After upload, use the **"Open your dashboard"** link from the UI — it opens the Superset dashboard `PBM Claims Risk & Compliance Command Center` pre-filtered to that company. Or open http://localhost:8088 directly and log in with `admin` / `admin`.

## 6. Use the PBM Copilot extension inside Superset

The stack ships with a Superset extension (`superset/extensions/pbm.pbm-copilot-*.supx`) that puts a **PBM Copilot** panel in SQL Lab: upload claim files, browse companies and anomalies, and get GenAI explanations without leaving Superset. It is baked into the Superset image, so it's already active after `docker compose up -d --build`:

```bash
docker compose up -d --build   # image already contains the extension
```

Then in Superset: **SQL Lab** → **PBM Copilot** tab. First time, open the **Settings** tab, set the API base URL (`http://localhost:8000`), add the API token if you configured `PBM_API_TOKEN`, and **Test connection**.

Rebuild the bundle from source (Node.js 20+):

```bash
cd extensions/pbm-copilot/frontend
npm install
node bundle.mjs                       # -> ../../pbm.pbm-copilot-<version>.<ts>.supx
Copy-Item ../pbm.pbm-copilot-*.supx ../../superset/extensions/   # PowerShell
# macOS/Linux: cp ../pbm.pbm-copilot-*.supx ../../superset/extensions/
docker compose build superset
docker compose up -d superset
```

> There is no volume mount for the extension — the Superset image copies `superset/extensions/*.supx` at build time, so a rebuilt bundle needs `docker compose build superset` (a plain `restart` will not pick it up).

## 7. Explain an anomaly

```bash
curl -X POST http://localhost:8000/explain/CLM-00000001
```

Windows PowerShell:

```powershell
Invoke-RestMethod -Method Post http://localhost:8000/explain/CLM-00000001
```

## 8. Run the tests

With the stack up (at least `postgres` + `api`):

```bash
docker compose exec api python -m pytest -q
```

Covers upload validation, per-company replace semantics and derived duplicate / refill-too-soon detection. Tests write to the real demo database and clean up after themselves.

## 9. Stop / clean up

```bash
docker compose down          # stop containers
docker compose down -v       # stop and remove volumes (resets all data)
```

## Troubleshooting

- **Ports already in use** — change the host ports in `docker-compose.yml` (e.g. `"8001:8000"`).
- **Superset hostname differs** — set `SUPERSET_URL` and `SUPERSET_PUBLIC_URL` in `.env` and restart.
- **`postgres` not resolvable from Superset** — use `postgresql://postgres:postgres@host.docker.internal:5432/pbm` when connecting manually.
- **Superset not ready** — it needs a few seconds after startup to initialize; re-run the upload if provisioning fails.

All claim data is synthetic — this is a technical demonstration, not production clinical/compliance software.