from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from sqlalchemy import text
from .db import engine, fetch_one, fetch_all, ensure_schema
from .seed import run as seed
from .config import settings
from .upload import upload as process_upload

app=FastAPI(
    title="PBM Claims Anomaly & Compliance Copilot",
    version="1.0.0",
    description="Synthetic PBM claims anomaly detection, risk scoring and explainability API."
)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/health")
def health():
    with engine.connect() as conn:
        conn.execute(text("select 1"))
    return {"status":"ok","service":"pbm-copilot-api"}

@app.post("/seed")
def seed_data():
    seed()
    return {"status":"ok","message":"Seed completed or data already existed."}

@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...), company_name: str = Form(...)):
    if not company_name.strip():
        raise HTTPException(400, "company_name is required.")
    raw = await file.read()
    try:
        result = process_upload(raw, file.filename or "upload.csv", company_name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"status":"ok", **result}

@app.get("/api/companies")
def companies():
    ensure_schema()
    return fetch_all("""
        select company_id, name, uploaded_at, record_count, status
        from companies
        order by uploaded_at desc
    """)

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

@app.post("/explain/{claim_id}")
def explain(claim_id:str, company_id:str=None):
    if company_id:
        row=fetch_one(
            "select * from claims where claim_id=:id and company_id=:cid",
            {"id":claim_id,"cid":company_id},
        )
    else:
        row=fetch_one("select * from claims where claim_id=:id", {"id":claim_id})
    if not row: raise HTTPException(404,"Claim not found")
    prompt=f"""Explain this synthetic pharmacy claim anomaly.
Claim: {row}
Return: 1) executive summary, 2) evidence, 3) likely investigation path,
4) data to validate, 5) compliance caveat. Do not invent facts."""
    if settings.claude_api_key:
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
    else:
        explanation=(
          f"Claim {claim_id} is {row['risk_level']} risk with score {row['risk_score']}. "
          f"Triggered rules: {row['rule_codes'] or 'ML-only anomaly'}. "
          f"Evidence: {row['evidence'] or 'The baseline ML model identified an unusual feature combination.'} "
          "Investigation path: validate member/provider history, pricing, refill timing, "
          "product mapping and duplicate-claim evidence before taking action. This is synthetic "
          "demo data and the score is a triage signal, not a final compliance decision."
        )
        mode="fallback"
    return {"claim_id":claim_id,"mode":mode,"risk_level":row["risk_level"],"risk_score":row["risk_score"],"explanation":explanation}
