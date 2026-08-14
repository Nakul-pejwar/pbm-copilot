import io
import re
import pandas as pd
from sqlalchemy import create_engine, text
from .config import settings
from .db import ensure_schema
from .rules import evaluate
from .anomaly import fit_model, score_model
from .scoring import final_score

REQUIRED_COLUMNS = [
    "claim_id", "claim_date", "member_id", "provider_id", "plan_id",
    "product_id", "quantity", "days_supply", "unit_price",
    "allowed_unit_price", "paid_amount", "allowed_amount",
    "provider_claim_count_30d", "is_duplicate", "refill_too_soon",
    "ndc_mismatch", "status",
]

MAX_ROWS = 500_000
MAX_BYTES = 100 * 1024 * 1024


def slugify(name):
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().upper()).strip("_")
    if not slug:
        raise ValueError("Company name must contain letters or digits.")
    return slug[:50]


def _to_int_positive(series, name):
    out = pd.to_numeric(series, errors="coerce")
    bad = out.isna() | (out < 0)
    if bad.any():
        raise ValueError(f"Column '{name}' must contain non-negative integers (bad rows: {bad.sum()}).")
    return out.astype(int)


def _to_float_positive(series, name):
    out = pd.to_numeric(series, errors="coerce")
    bad = out.isna() | (out <= 0)
    if bad.any():
        raise ValueError(f"Column '{name}' must contain positive numbers (bad rows: {bad.sum()}).")
    return out.astype(float)


def _to_bool(series, name):
    def parse(v):
        if isinstance(v, bool):
            return v
        return str(v).strip().lower() in ("1", "true", "yes", "y")
    out = series.map(parse).astype(bool)
    return out


def read_table(raw, filename):
    size = len(raw)
    if size > MAX_BYTES:
        raise ValueError("File is larger than the 100 MB limit.")
    if size == 0:
        raise ValueError("File is empty.")
    try:
        if filename.lower().endswith((".xlsx", ".xls")):
            return pd.read_excel(io.BytesIO(raw))
        return pd.read_csv(io.BytesIO(raw), dtype=str)
    except Exception as e:
        raise ValueError(f"Could not parse file as {'Excel' if filename.lower().endswith(('.xlsx', '.xls')) else 'CSV'}: {e}")


def validate(df):
    df = df.dropna(how="all")
    if df.empty:
        raise ValueError("No data rows found in the file.")
    if len(df) > MAX_ROWS:
        raise ValueError(f"File exceeds the {MAX_ROWS:,} row limit.")

    cols = list(df.columns)
    missing = [c for c in REQUIRED_COLUMNS if c not in cols]
    extra = [c for c in cols if c not in REQUIRED_COLUMNS]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}.")
    if extra:
        raise ValueError(f"Unexpected columns (expected exact schema): {', '.join(extra)}.")

    if df["claim_id"].duplicated().any():
        raise ValueError("Duplicate claim_id values found within the file.")

    clean = pd.DataFrame()
    clean["claim_id"] = df["claim_id"].astype(str).str.strip()
    clean["claim_date"] = pd.to_datetime(df["claim_date"], errors="coerce")
    if clean["claim_date"].isna().any():
        raise ValueError("Column 'claim_date' contains unparseable dates.")
    for c in ("member_id", "provider_id", "plan_id", "product_id", "status"):
        clean[c] = df[c].astype(str).str.strip()
        if clean[c].str.len().eq(0).any():
            raise ValueError(f"Column '{c}' contains empty values.")
    clean["quantity"] = _to_int_positive(df["quantity"], "quantity")
    clean["days_supply"] = _to_int_positive(df["days_supply"], "days_supply")
    clean["provider_claim_count_30d"] = _to_int_positive(df["provider_claim_count_30d"], "provider_claim_count_30d")
    clean["unit_price"] = _to_float_positive(df["unit_price"], "unit_price")
    clean["allowed_unit_price"] = _to_float_positive(df["allowed_unit_price"], "allowed_unit_price")
    clean["paid_amount"] = _to_float_positive(df["paid_amount"], "paid_amount")
    clean["allowed_amount"] = _to_float_positive(df["allowed_amount"], "allowed_amount")
    clean["is_duplicate"] = _to_bool(df["is_duplicate"], "is_duplicate")
    clean["refill_too_soon"] = _to_bool(df["refill_too_soon"], "refill_too_soon")
    clean["ndc_mismatch"] = _to_bool(df["ndc_mismatch"], "ndc_mismatch")
    return clean


def process(df):
    model, scaler = fit_model(df)
    ml_scores, ml_flags = score_model(model, scaler, df)

    rule_scores, final_scores, levels, codes, evidence = [], [], [], [], []
    for row, ml in zip(df.to_dict("records"), ml_scores):
        rr = evaluate(row)
        rs = min(100, sum(x.score for x in rr))
        fs, lvl = final_score(rs, ml)
        rule_scores.append(rs)
        final_scores.append(fs)
        levels.append(lvl)
        codes.append("|".join(x.code for x in rr))
        evidence.append(" ".join(x.evidence for x in rr))

    df["rule_score"] = rule_scores
    df["ml_score"] = ml_scores
    df["risk_score"] = final_scores
    df["risk_level"] = levels
    df["anomaly"] = (df["rule_score"] > 0) | ml_flags
    df["rule_codes"] = codes
    df["evidence"] = evidence
    return df


def upload(raw, filename, company_name):
    company_id = slugify(company_name)

    df = read_table(raw, filename)
    df = validate(df)
    df = process(df)

    df["company_id"] = company_id
    df["claim_date"] = df["claim_date"].dt.date

    engine = create_engine(settings.database_url)
    ensure_schema()

    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM claims WHERE company_id=:cid"),
            {"cid": company_id},
        )
        df.to_sql(
            "claims",
            con=conn,
            if_exists="append",
            index=False,
            chunksize=1000,
        )
        conn.execute(
            text("""
                INSERT INTO companies (company_id, name, record_count, status)
                VALUES (:cid, :name, :n, 'uploaded')
                ON CONFLICT (company_id)
                DO UPDATE SET name=EXCLUDED.name, record_count=EXCLUDED.record_count,
                              status='uploaded', uploaded_at=now()
            """),
            {"cid": company_id, "name": company_name.strip(), "n": len(df)},
        )

    return {
        "company_id": company_id,
        "rows_loaded": len(df),
        "anomalies": int(df["anomaly"].sum()),
        "risk_levels": {
            k: int(v) for k, v in df["risk_level"].value_counts().items()
        },
    }
