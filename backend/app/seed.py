import os, random
from datetime import date, timedelta
import numpy as np
import pandas as pd
from faker import Faker
from sqlalchemy import text
from .db import engine, ensure_schema
from .rules import evaluate
from .anomaly import fit_model, score_model
from .scoring import final_score

fake = Faker()
random.seed(42)
np.random.seed(42)

def generate(n=100_000):
    providers = [f"PRV{1000+i}" for i in range(250)]
    products = [f"{11+i:05d}-{i%10:02d}-{i%10:02d}" for i in range(100)]
    plans = [f"PLAN-{i:03d}" for i in range(20)]
    rows=[]
    for i in range(n):
        qty = int(np.random.choice([30,60,90,120], p=[.45,.25,.20,.10]))
        days = int(np.random.choice([30,60,90,120], p=[.55,.20,.20,.05]))
        unit = round(float(np.random.lognormal(2.2, .65)),2)
        allowed_unit = round(unit * random.uniform(.80, 1.05),2)
        allowed = round(allowed_unit * qty,2)
        paid = round(allowed * random.uniform(.85,1.08),2)
        anomaly = random.random() < .045
        if anomaly:
            kind=random.choice(["price","paid","qty","refill","mismatch","duplicate"])
            if kind=="price": unit=round(allowed_unit*random.uniform(1.3,2.5),2)
            elif kind=="paid": paid=round(allowed*random.uniform(1.25,2.5),2)
            elif kind=="qty": qty=random.choice([150,180,240])
            elif kind=="refill": pass
            elif kind=="mismatch": pass
        rows.append({
            "claim_id": f"CLM-{i+1:08d}",
            "company_id": "SEED_DEMO",
            "claim_date": date.today()-timedelta(days=random.randint(0,179)),
            "member_id": f"MBR-{random.randint(1,25000):06d}",
            "provider_id": random.choice(providers),
            "plan_id": random.choice(plans),
            "product_id": random.choice(products),
            "quantity": qty,
            "days_supply": days,
            "unit_price": unit,
            "allowed_unit_price": allowed_unit,
            "paid_amount": paid,
            "allowed_amount": allowed,
            "provider_claim_count_30d": int(np.random.gamma(4,35)),
            "is_duplicate": anomaly and random.random()<.20,
            "refill_too_soon": anomaly and random.random()<.25,
            "ndc_mismatch": anomaly and random.random()<.15,
            "status": "PAID"
        })
    return pd.DataFrame(rows)

def run():
    ensure_schema()

    with engine.begin() as conn:

        count = conn.execute(
            text("SELECT count(*) FROM claims")
        ).scalar()

    if count:
        print(f"Claims already exist: {count}. Skipping seed.")
        return

    print("Generating 100,000 synthetic claims...")

    df = generate(100_000)

    print("Training anomaly model...")
    model, scaler = fit_model(df)

    print("Scoring claims...")
    ml_scores, ml_flags = score_model(model, scaler, df)

    rule_scores = []
    levels = []
    final_scores = []
    codes = []
    evidence = []

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

    print("Inserting claims into PostgreSQL...")

    df.to_sql(
        "claims",
        engine,
        if_exists="append",
        index=False,
        chunksize=1000
    )

    print("Seeded 100,000 synthetic claims.")

if __name__=="__main__":
    run()
