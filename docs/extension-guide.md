# PBM Copilot — Superset Extension: Install & User Guide

**PBM Copilot** is a Superset extension that adds a **PBM Copilot** tab inside SQL Lab.
From that tab you can upload claim files, browse companies and anomalies, and get
GenAI explanations — without leaving Superset.

It ships as a packaged extension file: `pbm.pbm-copilot-<version>.<timestamp>.supx`
(a zip containing a `manifest.json` plus the built frontend bundle).

---

## 1. What you need

| Requirement | Notes |
|---|---|
| Superset **6.x** | The `.supx` extension format is supported by Superset 6+. |
| Node.js **20+** | Only needed if you want to rebuild the extension from source. |
| The PBM API | The extension talks to the FastAPI service (`/api/config`, `/api/upload`, `/api/companies`, `/anomalies`, `/explain/…`). Use the bundled docker stack, or point the extension at your own deployment. |

The easiest path is the bundled docker stack (Option A). If you already run your own
Superset, use Option B.

---

## 2. Option A — Run the full docker stack (recommended)

```bash
git clone https://github.com/Nakul-pejwar/pbm-copilot.git
cd pbm-copilot
Copy-Item .env.example .env        # Windows PowerShell
# or: cp .env.example .env          # macOS / Linux
docker compose up -d --build
```

This starts four services:

| Service | URL | Login |
|---|---|---|
| PBM API + upload UI | http://localhost:8000 | — |
| API docs | http://localhost:8000/docs | — |
| Superset (with the extension pre-installed) | http://localhost:8088 | `admin` / `admin` |
| PostgreSQL | localhost:5432 | `postgres` / `postgres` |

The Superset image is built with the extension already copied in
(`superset/extensions/*.supx`), so it just works. Open http://localhost:8088,
sign in, and go to **SQL Lab → PBM Copilot** (see section 6).

Optional: set `CLAUDE_API_KEY` in `.env` to enable real GenAI explanations.
Without it, the app falls back to a deterministic explainability mode.

---

## 3. Option B — Install into an existing Superset instance

You only need the `.supx` file. You can either download a prebuilt one from the
repository (`superset/extensions/`) or build it yourself (section 4).

### 3.1 Enable the extension feature flag

Add to your `superset_config.py`:

```python
FEATURE_FLAGS = {
    "ENABLE_EXTENSIONS": True,
}
EXTENSIONS_PATH = "/app/extensions"   # where Superset scans for .supx files
```

### 3.2 Copy the extension file

```bash
mkdir -p /app/extensions
cp pbm.pbm-copilot-0.1.0.*.supx /app/extensions/
```

For the bundled Docker setup this is already wired up by the Dockerfile:

```dockerfile
COPY extensions/ /app/extensions/
```

### 3.3 Restart Superset

If the `.supx` was copied into an already-running container's filesystem (e.g. you
mounted `EXTENSIONS_PATH` yourself), a restart is enough:

```bash
docker compose restart superset
```

> For the bundled Docker stack there is **no volume mount** for extensions — the
> image copies `superset/extensions/*.supx` at build time. In that setup, deploy a
> new bundle with `docker compose build superset && docker compose up -d superset`
> (see section 4); a plain `restart` will not pick up a newly added file.

Watch the logs for a successful load:

```
superset.extensions.discovery:Loaded extension 'pbm.pbm-copilot' from /app/extensions/pbm.pbm-copilot-...supx
```

---

## 4. Rebuild the extension from source

If you clone this repo, the source lives in `extensions/pbm-copilot/frontend/`:

```bash
cd extensions/pbm-copilot/frontend
npm install
node bundle.mjs        # builds with webpack and produces extensions/pbm.pbm-copilot-<version>.<ts>.supx
```

Then deploy it:

```bash
# copy the new bundle into the superset build context
cp ../pbm.pbm-copilot-*.supx ../../superset/extensions/
# remove any older .supx files in superset/extensions/
docker compose build superset
docker compose up -d superset
```

> Note: `bundle.mjs` does not clean the `dist/` directory. If a previous build left
> stale `remoteEntry.*.js` files behind, remove `dist/` before rebuilding:
> `Remove-Item -Recurse -Force dist` (PowerShell) or `rm -rf dist` (macOS/Linux).

---

## 5. Point the extension at the PBM API

The extension runs in your browser and calls the API directly, so:

- The API must be reachable from your browser (default `http://localhost:8000`).
- Superset's origin must be allowed by the API (CORS). Default:
  `SUPERSET_ORIGIN=http://localhost:8088` in the API's `.env` / environment.
  Comma-separate multiple origins if needed.
- If you set `PBM_API_TOKEN` on the API, every request must include that token.

Open **SQL Lab → PBM Copilot → Settings** tab and check:
- **API base URL** — `http://localhost:8000` (default)
- **API token** — leave empty unless `PBM_API_TOKEN` is set
- Click **Save**, then **Test connection** — you should see
  `Connected to pbm-copilot-api v1.0.0`.

---

## 6. Using the extension

1. In Superset open **SQL Lab** (URL: `/sqllab` in Superset 6, or
   `superset/sqllab` in older versions).
2. Click the **PBM Copilot** tab (next to Results / Query history).
3. The panel shows five tabs:

| Tab | What it does |
|---|---|
| **Upload** | Enter a company name, pick a CSV/Excel claim file, click **Upload & Process**. Re-uploading the same company **replaces** its previous data. |
| **Companies** | Table of every uploaded company (rows, upload time, status, dashboard link). |
| **Anomalies** | Top 25 flagged claims with risk score/level and triggered rules. Click **Explain** for an AI explanation. |
| **Explain** | Explain any claim by ID (`CLM-…`), optionally scoped to one company. |
| **Settings** | Configure the API base URL + token and test the connection. |

### Supported claim file format

CSV or Excel (`.csv`, `.xlsx`, `.xls`) with these **exact column names** (any order):

```
claim_id, claim_date, member_id, provider_id, plan_id, product_id, quantity,
days_supply, unit_price, allowed_unit_price, paid_amount, allowed_amount,
provider_claim_count_30d, is_duplicate, refill_too_soon, ndc_mismatch, status
```

Generate a demo file from the repo root (Python 3, stdlib only):

```bash
python script/make_sample_csv.py --rows 5000   # -> sample_claims.csv
```

Uploading trains a per-company Isolation Forest baseline, applies business rules,
scores every claim, and auto-provisions a Superset dashboard for that company.

---

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| `Cannot reach the PBM API / Failed to fetch` | Start the API (`docker compose up -d api`), check the **Settings** tab base URL, and confirm `SUPERSET_ORIGIN` matches your Superset origin. |
| Extension tab missing in SQL Lab | Verify `ENABLE_EXTENSIONS` flag + `EXTENSIONS_PATH`, and that the `.supx` is present there; check Superset logs for the `Loaded extension` line. |
| No extension content visible | Hard-refresh the page (**Ctrl+F5**) to drop the cached old bundle; if the panel is short, scroll the SQL Lab bottom pane. |
| `401` errors | `PBM_API_TOKEN` is set on the API — add the same token in the extension **Settings** tab. |
| Stale bundle after rebuild | Clear browser cache / hard-refresh; the bundle filename is content-hashed so a new build serves a new file. |

---

All claim data is synthetic — this is a technical demonstration, not production
clinical/compliance software.
