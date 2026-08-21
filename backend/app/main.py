from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, Header
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from contextlib import asynccontextmanager
from html import escape
import logging
import time
from sqlalchemy import text
from .db import engine, fetch_one, fetch_all, ensure_schema
from .seed import run as seed
from .config import settings
from .upload import upload as process_upload

log = logging.getLogger("pbm.explain")


@asynccontextmanager
async def lifespan(app):
    try:
        from .superset_client import ensure_dashboard
        ensure_dashboard()
    except Exception as e:
        print(f"Superset self-heal skipped: {e}")
    yield


app=FastAPI(
    title="PBM Claims Anomaly & Compliance Copilot",
    version="1.0.0",
    description="Synthetic PBM claims anomaly detection, risk scoring and explainability API.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.superset_origin.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def require_token(x_api_token: str | None = Header(default=None)):
    if settings.api_token and x_api_token != settings.api_token:
        raise HTTPException(401, "Missing or invalid X-API-Token.")

@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/health")
def health():
    with engine.connect() as conn:
        conn.execute(text("select 1"))
    return {"status":"ok","service":"pbm-copilot-api"}

@app.post("/seed", dependencies=[Depends(require_token)])
def seed_data():
    seed()
    return {"status":"ok","message":"Seed completed or data already existed."}

@app.post("/api/upload", dependencies=[Depends(require_token)])
async def api_upload(file: UploadFile = File(...), company_name: str = Form(...)):
    if not company_name.strip():
        raise HTTPException(400, "company_name is required.")
    raw = await file.read()
    try:
        result = process_upload(raw, file.filename or "upload.csv", company_name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"status":"ok", **result}

@app.post("/api/provision", dependencies=[Depends(require_token)])
def provision():
    from .superset_client import dashboard_url
    try:
        url = dashboard_url()
        return {"status": "ok", "dashboard_url": url}
    except Exception as e:
        raise HTTPException(502, f"Superset provisioning failed: {e}")

@app.get("/api/config")
def api_config():
    return {
        "service": "pbm-copilot-api",
        "version": app.version,
        "auth_required": bool(settings.api_token),
    }

@app.get("/api/companies")
def companies():
    ensure_schema()
    rows = fetch_all("""
        select company_id, name, uploaded_at, record_count, status
        from companies
        order by uploaded_at desc
    """)
    for row in rows:
        try:
            from .superset_client import dashboard_url
            row["dashboard_url"] = dashboard_url(row["company_id"])
        except Exception:
            row["dashboard_url"] = None
    return rows


@app.get("/api/providers")
def providers(company_id: str = None, band: str = None, limit: int = 100):
    ensure_schema()
    q = "select * from provider_scores where 1=1"
    params = {}
    if company_id:
        q += " and company_id = :cid"
        params["cid"] = company_id
    if band:
        q += " and band = :band"
        params["band"] = band.strip().upper()
    q += " order by score asc, provider_id asc limit :limit"
    params["limit"] = min(limit, 500)
    return fetch_all(q, params)

@app.get("/metrics")
def metrics():
    q="""
    select
      count(*) claims_processed,
      count(*) filter(where anomaly) anomalies,
      count(*) filter(where risk_level='CRITICAL') critical,
      count(*) filter(where risk_level='HIGH') high,
      coalesce(round(avg(risk_score)::numeric,2),0) avg_risk,
      coalesce(round(sum(paid_amount)::numeric,2),0) total_paid
    from claims
    """
    return fetch_one(q)

@app.get("/claims/{claim_id}")
def claim(claim_id:str, company_id:str=None):
    if company_id:
        row=fetch_one(
            "select * from claims where claim_id=:id and company_id=:cid",
            {"id":claim_id,"cid":company_id},
        )
    else:
        row=fetch_one("select * from claims where claim_id=:id", {"id":claim_id})
    if not row: raise HTTPException(404,"Claim not found")
    return row

@app.get("/anomalies")
def anomalies(limit:int=25):
    return fetch_all("""
      select claim_id, claim_date, provider_id, plan_id, product_id,
             paid_amount, allowed_amount, risk_score, risk_level,
             rule_codes, evidence
      from claims
      where anomaly=true
      order by risk_score desc
      limit :limit
    """, {"limit":min(limit,200)})

from collections import OrderedDict

_EXPLAIN_CACHE: OrderedDict[tuple, tuple] = OrderedDict()
_EXPLAIN_TTL = 30 * 60
_EXPLAIN_MAX = 256


def _fetch_claim(claim_id: str, company_id: str | None):
    if company_id:
        row = fetch_one(
            "select * from claims where claim_id=:id and company_id=:cid",
            {"id": claim_id, "cid": company_id},
        )
    else:
        row = fetch_one("select * from claims where claim_id=:id", {"id": claim_id})
    return row


def _explain(claim_id: str, company_id: str | None):
    cache_key = (company_id, claim_id)
    cached = _EXPLAIN_CACHE.get(cache_key)
    if cached and cached[0] > time.time():
        _EXPLAIN_CACHE.move_to_end(cache_key)
        return cached[1]
    row = _fetch_claim(claim_id, company_id)
    if not row:
        raise HTTPException(404, "Claim not found")
    prompt=f"""Explain this synthetic pharmacy claim anomaly.
Claim: {row}
Return: 1) executive summary, 2) evidence, 3) likely investigation path,
4) data to validate, 5) compliance caveat. Do not invent facts."""
    mode = "fallback"
    explanation = (
        f"Claim {claim_id} is {row['risk_level']} risk with score {row['risk_score']}. "
        f"Triggered rules: {row['rule_codes'] or 'ML-only anomaly'}. "
        f"Evidence: {row['evidence'] or 'The baseline ML model identified an unusual feature combination.'} "
        "Investigation path: validate member/provider history, pricing, refill timing, "
        "product mapping and duplicate-claim evidence before taking action. This is synthetic "
        "demo data and the score is a triage signal, not a final compliance decision."
    )
    if settings.claude_api_key:
        try:
            from anthropic import Anthropic
            client=Anthropic(api_key=settings.claude_api_key)
            r=client.messages.create(
                model=settings.claude_model,
                max_tokens=1024,
                system="You are a PBM compliance analyst. Explain evidence only; do not invent facts.",
                messages=[{"role":"user","content":prompt}],
            )
            explanation=r.content[0].text
            mode="llm"
        except Exception as e:
            log.warning("LLM explanation failed (%s); using deterministic fallback", e)
    result={
        "claim_id": claim_id,
        "company_id": row["company_id"],
        "mode": mode,
        "risk_level": row["risk_level"],
        "risk_score": row["risk_score"],
        "provider_id": row["provider_id"],
        "paid_amount": row["paid_amount"],
        "rule_codes": row["rule_codes"],
        "evidence": row["evidence"],
        "explanation": explanation,
    }
    _EXPLAIN_CACHE[cache_key] = (time.time() + _EXPLAIN_TTL, result)
    _EXPLAIN_CACHE.move_to_end(cache_key)
    while len(_EXPLAIN_CACHE) > _EXPLAIN_MAX:
        _EXPLAIN_CACHE.popitem(last=False)
    return result


@app.post("/explain/{claim_id}", dependencies=[Depends(require_token)])
def explain(claim_id:str, company_id:str=None):
    return _explain(claim_id, company_id)


_EXPLAIN_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Claim Explanation</title>
<style>
  :root {{ --bg:#0f1420; --card:#1a2233; --text:#e8edf6; --muted:#93a1b8;
           --border:#2a3650; --accent:#2d6cdf; }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ background:var(--bg); color:var(--text); font-family:Segoe UI, Arial, sans-serif; padding:16px; }}
  .head {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:14px; }}
  h1 {{ font-size:15px; color:var(--muted); font-weight:600; }}
  .claim {{ font-size:18px; font-weight:700; }}
  .badge {{ padding:3px 10px; border-radius:6px; font-size:12px; font-weight:700; }}
  .badge.CRITICAL {{ background:#7a1f1f; color:#ffb3b3; }}
  .badge.HIGH {{ background:#8a4b0a; color:#ffd9a8; }}
  .badge.MEDIUM {{ background:#7a6a0a; color:#fff2b3; }}
  .badge.LOW {{ background:#1f5e3a; color:#c8f5d8; }}
  .meta {{ display:flex; gap:16px; flex-wrap:wrap; font-size:12px; color:var(--muted); margin-bottom:14px; }}
  .meta b {{ color:var(--text); }}
  .sec {{ background:var(--card); border:1px solid var(--border); border-radius:10px; padding:14px 16px; margin-bottom:12px; }}
  .sec h2 {{ font-size:12px; color:#9db8e8; text-transform:uppercase; letter-spacing:.5px; margin-bottom:8px; }}
  .sec p, .sec li {{ font-size:13px; line-height:1.65; color:var(--text); white-space:pre-wrap; }}
  .sec ul {{ padding-left:18px; }}
  .caveat {{ border-color:#5e2530; background:#2b1215; }}
  .foot {{ font-size:11px; color:var(--muted); margin-top:6px; }}
</style>
</head>
<body>
  <div class="head">
    <h1>AI Explanation</h1>
    <span class="claim">{claim_id}</span>
    <span class="badge {risk_level}">{risk_level}</span>
  </div>
  <div class="meta">
    <span>Risk score: <b>{risk_score}</b></span>
    <span>Provider: <b>{provider_id}</b></span>
    <span>Paid amount: <b>${paid_amount}</b></span>
  </div>
  <div class="sec"><h2>Analysis</h2><p>{explanation}</p></div>
  <div class="foot">Synthetic demo data. Score is a triage signal, not a final compliance decision.</div>
</body>
</html>"""


@app.get("/explain/view/{claim_id}", response_class=HTMLResponse)
def explain_view(claim_id: str, company_id: str = None):
    result = _explain(claim_id, company_id)
    return _EXPLAIN_PAGE.format(
        claim_id=escape(str(result["claim_id"])),
        risk_level=escape(str(result["risk_level"])),
        risk_score=escape(str(result["risk_score"])),
        provider_id=escape(str(result["provider_id"])),
        paid_amount=escape(str(result["paid_amount"])),
        explanation=escape(str(result["explanation"])),
    )
