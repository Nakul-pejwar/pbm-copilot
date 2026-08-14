# PBM Claims Anomaly & Compliance Copilot

## Demo architecture

Synthetic PBM claims -> PostgreSQL -> deterministic rules + Isolation Forest -> risk score -> FastAPI -> Superset + GenAI explanation.

**Important:** all claim data is synthetic. This is a technical demonstration, not production clinical/compliance software.

## 1. Start

Copy `.env.example` to `.env`. Optionally add an Anthropic API key.

Then:

```bash
docker compose up -d --build
```

Check:

- Upload UI + API: http://localhost:8000
- API docs: http://localhost:8000/docs
- Superset: http://localhost:8088
- Superset login: `admin` / `admin`

## 2. Generate 100K claims

```bash
docker compose exec api python -m app.seed
```

Then check:

```bash
curl http://localhost:8000/metrics
```

Windows PowerShell:

```powershell
Invoke-RestMethod http://localhost:8000/metrics
```

## 3. Upload a company's data

### Generate sample data

No sample file handy? Generate one from the project root (pure stdlib, no installs):

```bash
python make_sample_csv.py --rows 5000          # -> sample_claims.csv
python make_sample_csv.py --rows 5000 --seed 7 # different dataset
```

Output has the exact 17 required columns and ~4.5% injected anomalies.

### Upload

Open http://localhost:8000, enter a company name, pick a CSV or Excel file, and click **Upload & Process**.

The upload endpoint (`POST /api/upload`) validates the file, trains a per-company Isolation Forest baseline, applies the business rules, scores every claim, replaces that company's previous rows, and records it in the `companies` table.

Expected columns (exact, in any order): `claim_id`, `claim_date`, `member_id`, `provider_id`, `plan_id`, `product_id`, `quantity`, `days_supply`, `unit_price`, `allowed_unit_price`, `paid_amount`, `allowed_amount`, `provider_claim_count_30d`, `is_duplicate`, `refill_too_soon`, `ndc_mismatch`, `status`.

Re-uploading the same company replaces its existing data. Errors are reported per file (missing columns, bad types, duplicate `claim_id`s, size/row limits). Seed data is tagged `company_id = SEED_DEMO`.

## 4. Connect Superset to PostgreSQL

In Superset:

Settings -> Data -> Database Connections -> + Database

SQLAlchemy URI:

postgresql://postgres:postgres@postgres:5432/pbm

If `postgres` is not resolvable from the Superset container, use:

postgresql://postgres:postgres@host.docker.internal:5432/pbm

Create dataset:

`public.claims`

After the first upload or seed, open the dataset -> `Sync columns from source` so `company_id` appears, then add a native dashboard filter on `company_id` to view individual companies.

Recommended charts:

1. Big Number: COUNT(claim_id) -> Claims Processed
2. Big Number: SUM(CASE WHEN anomaly THEN 1 ELSE 0 END) -> Anomalies
3. Big Number: COUNT(*) filtered risk_level='CRITICAL' -> Critical Claims
4. Pie: risk_level by COUNT(claim_id)
5. Time-series: claim_date by COUNT(claim_id), split by risk_level
6. Bar: provider_id by SUM(paid_amount), filter anomaly=true
7. Bar: rule_codes by COUNT(claim_id)
8. Table: claim_id, provider_id, plan_id, paid_amount, allowed_amount, risk_score, risk_level, rule_codes

Put these into one dashboard called:

`PBM Claims Risk & Compliance Command Center`

## 5. Explain an anomaly

Pick a high-risk claim, e.g.:

```bash
curl -X POST http://localhost:8000/explain/CLM-00000001
```

If `CLAUDE_API_KEY` is configured, the endpoint uses the configured Anthropic model. Without a key, it returns a deterministic explainability fallback so the demo still works.

## 6. Presentation story

Do not say "AI detects fraud". Say:

> "The system combines deterministic PBM business rules with an unsupervised baseline anomaly model. The result is a risk-ranked triage queue. GenAI sits after detection and explains the evidence for a human reviewer."

Business value:

- reduces manual first-pass review
- prioritizes high-risk claims
- makes anomaly evidence easier to understand
- gives analysts a repeatable investigation path
- preserves an audit trail through stored scores, rule codes and evidence

## 7. Production evolution

For production, add:

- real PBM source adapters
- PHI/PII controls and encryption
- RBAC and SSO
- immutable audit logging
- model registry/versioning
- feature store
- drift monitoring
- human approval workflow
- rule versioning
- data retention policies
- automated model/rule validation
- SIEM integration
