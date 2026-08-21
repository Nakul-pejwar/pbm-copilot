import io

import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.main import app
from app.provider_score import (
    THIN_FILE_CAP,
    band_for,
    compute_provider_scores,
)

client = TestClient(app)


def _claim(provider, risk_score=5, risk_level="LOW", anomaly=False,
           codes="", paid=100.0, allowed=100.0):
    return {
        "provider_id": provider,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "anomaly": anomaly,
        "rule_codes": codes,
        "paid_amount": paid,
        "allowed_amount": allowed,
    }


def _row(claim_id, provider="PRV1000", date="2026-01-15", member="MBR-000001",
         qty=30, days=30, unit=10.0):
    allowed_unit = round(unit, 2)
    allowed = round(allowed_unit * qty, 2)
    paid = round(allowed * 1.0, 2)
    return {
        "claim_id": claim_id, "claim_date": date, "member_id": member,
        "provider_id": provider, "plan_id": "PLAN-001",
        "product_id": "00011-01-01", "quantity": qty, "days_supply": days,
        "unit_price": allowed_unit, "allowed_unit_price": allowed_unit,
        "paid_amount": paid, "allowed_amount": allowed,
        "provider_claim_count_30d": 40, "is_duplicate": "false",
        "refill_too_soon": "false", "ndc_mismatch": "false", "status": "PAID",
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
        conn.execute(text("DELETE FROM provider_scores WHERE company_id=:c"), {"c": company_id})
        conn.execute(text("DELETE FROM companies WHERE company_id=:c"), {"c": company_id})


def test_band_boundaries():
    assert band_for(900) == "Excellent"
    assert band_for(750) == "Excellent"
    assert band_for(749) == "Good"
    assert band_for(650) == "Good"
    assert band_for(649) == "Fair"
    assert band_for(550) == "Fair"
    assert band_for(549) == "Poor"
    assert band_for(300) == "Poor"


def test_clean_provider_scores_excellent_and_bad_scores_poor():
    clean = pd.DataFrame([_claim("PRV-CLEAN") for _ in range(20)])
    bad = pd.DataFrame([
        _claim("PRV-BAD", risk_score=90, risk_level="CRITICAL", anomaly=True,
               codes="OVERPAYMENT", paid=200.0, allowed=100.0)
        for _ in range(20)
    ])
    scores = compute_provider_scores(pd.concat([clean, bad]))
    by_provider = scores.set_index("provider_id")

    clean_row = by_provider.loc["PRV-CLEAN"]
    bad_row = by_provider.loc["PRV-BAD"]

    assert clean_row["score"] >= 750
    assert clean_row["band"] == "Excellent"
    assert bool(clean_row["sufficient_data"]) is True
    assert bad_row["score"] == 300
    assert bad_row["band"] == "Poor"
    assert bad_row["critical_count"] == 20
    assert bad_row["overpayment_total"] == 2000.0
    assert "OVERPAYMENT" in bad_row["top_rule_codes"]
    factors = clean_row["factors"]
    assert factors["penalty_anomaly"] == 0
    assert factors["penalty_critical_high"] == 0


def test_thin_file_provider_capped():
    thin = pd.DataFrame([_claim("PRV-THIN") for _ in range(3)])
    scores = compute_provider_scores(thin)
    row = scores.iloc[0]
    assert row["score"] <= THIN_FILE_CAP
    assert bool(row["sufficient_data"]) is False


def test_upload_replaces_provider_scores():
    company_id = "PT_SCORE_CO"
    try:
        r = _upload(company_id, [
            _row("CLM-P001", provider="PRV-A"),
            _row("CLM-P002", provider="PRV-B"),
        ])
        assert r.status_code == 200, r.text
        assert r.json()["providers_scored"] == 2

        rows = client.get("/api/providers", params={"company_id": company_id}).json()
        assert {r["provider_id"] for r in rows} == {"PRV-A", "PRV-B"}

        r = _upload(company_id, [_row("CLM-P003", provider="PRV-C")])
        assert r.status_code == 200, r.text
        rows = client.get("/api/providers", params={"company_id": company_id}).json()
        assert [r["provider_id"] for r in rows] == ["PRV-C"]
    finally:
        _cleanup(company_id)


def test_providers_endpoint_orders_worst_first():
    company_id = "PT_ORDER_CO"
    try:
        rows = [
            _row(f"CLM-O{i:03d}", provider=("PRV-GOOD" if i < 15 else "PRV-BAD"))
            for i in range(20)
        ]
        for row in rows[15:]:
            row["paid_amount"] = 500.0
            row["allowed_amount"] = 300.0
            row["unit_price"] = 50.0
        r = _upload(company_id, rows)
        assert r.status_code == 200, r.text

        data = client.get("/api/providers", params={"company_id": company_id}).json()
        assert len(data) == 2
        assert data[0]["provider_id"] == "PRV-BAD"
        assert data[0]["score"] <= data[1]["score"]

        good_only = client.get(
            "/api/providers", params={"company_id": company_id, "band": "Excellent"}
        ).json()
        assert all(r["band"] == "Excellent" for r in good_only)
    finally:
        _cleanup(company_id)
