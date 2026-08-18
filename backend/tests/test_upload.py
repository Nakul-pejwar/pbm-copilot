import io
import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.main import app

client = TestClient(app)


def _row(claim_id, date="2026-01-15", member="MBR-000001", provider="PRV1000",
         product="00011-01-01", qty=30, days=30, unit=10.0, dup="false",
         refill="false", mismatch="false"):
    allowed_unit = round(unit, 2)
    allowed = round(allowed_unit * qty, 2)
    paid = round(allowed * 1.0, 2)
    return {
        "claim_id": claim_id, "claim_date": date, "member_id": member,
        "provider_id": provider, "plan_id": "PLAN-001", "product_id": product,
        "quantity": qty, "days_supply": days, "unit_price": allowed_unit,
        "allowed_unit_price": allowed_unit, "paid_amount": paid,
        "allowed_amount": allowed, "provider_claim_count_30d": 40,
        "is_duplicate": dup, "refill_too_soon": refill, "ndc_mismatch": mismatch,
        "status": "PAID",
    }


def _csv(rows):
    buf = io.StringIO()
    pd.DataFrame(rows).to_csv(buf, index=False)
    return buf.getvalue().encode()


def _upload(company_name, rows):
    return client.post(
        "/api/upload",
        data={"company_name": company_name},
        files={"file": ("smoke.csv", _csv(rows), "text/csv")},
    )


def _cleanup(company_id):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM claims WHERE company_id=:c"), {"c": company_id})
        conn.execute(text("DELETE FROM companies WHERE company_id=:c"), {"c": company_id})


def test_upload_valid_file():
    company_id = "SMOKE_TEST_CO"
    try:
        r = _upload("Smoke Test Co", [
            _row("CLM-A001"), _row("CLM-A002"), _row("CLM-A003"),
        ])
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["company_id"] == company_id
        assert data["rows_loaded"] == 3
    finally:
        _cleanup(company_id)


def test_upload_missing_column():
    rows = [_row("CLM-B001")]
    rows[0].pop("quantity")
    r = _upload("Missing Col Co", rows)
    assert r.status_code == 400
    assert "quantity" in r.json()["detail"]


def test_upload_invalid_bool():
    rows = [_row("CLM-B002")]
    rows[0]["is_duplicate"] = "maybe"
    r = _upload("Bad Bool Co", rows)
    assert r.status_code == 400
    assert "is_duplicate" in r.json()["detail"]


def test_duplicate_claims_derived():
    company_id = "DUP_TEST_CO"
    try:
        r = _upload("Dup Test Co", [
            _row("CLM-C001", member="MBR-DUP01", provider="PRV2000"),
            _row("CLM-C002", member="MBR-DUP01", provider="PRV2000"),
        ])
        assert r.status_code == 200, r.text
        assert r.json()["anomalies"] >= 1
        claim = client.get("/claims/CLM-C001", params={"company_id": company_id}).json()
        assert claim["is_duplicate"] is True
        assert "DUPLICATE_CLAIM" in claim["rule_codes"]
    finally:
        _cleanup(company_id)


def test_refill_too_soon_derived():
    company_id = "REFILL_TEST_CO"
    try:
        r = _upload("Refill Test Co", [
            _row("CLM-E001", date="2026-01-01", member="MBR-R01", qty=90, days=90),
            _row("CLM-E002", date="2026-01-15", member="MBR-R01", qty=30, days=30),
        ])
        assert r.status_code == 200, r.text
        claim = client.get("/claims/CLM-E002", params={"company_id": company_id}).json()
        assert claim["refill_too_soon"] is True
        assert "REFILL_TOO_SOON" in claim["rule_codes"]
    finally:
        _cleanup(company_id)
