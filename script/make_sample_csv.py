#!/usr/bin/env python3
"""Generate a synthetic PBM claims CSV compatible with the upload pipeline.

Pure Python stdlib - no third-party dependencies. Run from the project root:

    python make_sample_csv.py --rows 5000          # -> sample_claims.csv
    python make_sample_csv.py --rows 5000 --seed 7 # different dataset

Output has the exact 17 columns required by POST /api/upload.
"""
import argparse
import csv
import math
import random
from datetime import date, timedelta

COLUMNS = [
    "claim_id", "claim_date", "member_id", "provider_id", "plan_id",
    "product_id", "quantity", "days_supply", "unit_price",
    "allowed_unit_price", "paid_amount", "allowed_amount",
    "provider_claim_count_30d", "is_duplicate", "refill_too_soon",
    "ndc_mismatch", "status",
]


def generate(n, rng):
    providers = [f"PRV{1000 + i}" for i in range(250)]
    products = [f"{11 + i:05d}-{i % 10:02d}-{i % 10:02d}" for i in range(100)]
    plans = [f"PLAN-{i:03d}" for i in range(20)]
    rows = []
    for i in range(n):
        qty = rng.choices([30, 60, 90, 120], weights=[.45, .25, .20, .10])[0]
        days = rng.choices([30, 60, 90, 120], weights=[.55, .20, .20, .05])[0]
        unit = round(math.exp(rng.gauss(2.2, .65)), 2)
        allowed_unit = round(unit * rng.uniform(.80, 1.05), 2)
        allowed = round(allowed_unit * qty, 2)
        paid = round(allowed * rng.uniform(.85, 1.08), 2)
        anomaly = rng.random() < .045
        is_dup = refill = mismatch = False
        if anomaly:
            kind = rng.choice(["price", "paid", "qty", "refill", "mismatch", "duplicate"])
            if kind == "price":
                unit = round(allowed_unit * rng.uniform(1.3, 2.5), 2)
            elif kind == "paid":
                paid = round(allowed * rng.uniform(1.25, 2.5), 2)
            elif kind == "qty":
                qty = rng.choice([150, 180, 240])
            elif kind == "duplicate":
                is_dup = True
            elif kind == "refill":
                refill = True
            elif kind == "mismatch":
                mismatch = True
        rows.append({
            "claim_id": f"CLM-{i + 1:08d}",
            "claim_date": (date.today() - timedelta(days=rng.randint(0, 179))).isoformat(),
            "member_id": f"MBR-{rng.randint(1, 25000):06d}",
            "provider_id": rng.choice(providers),
            "plan_id": rng.choice(plans),
            "product_id": rng.choice(products),
            "quantity": qty,
            "days_supply": days,
            "unit_price": f"{unit:.2f}",
            "allowed_unit_price": f"{allowed_unit:.2f}",
            "paid_amount": f"{paid:.2f}",
            "allowed_amount": f"{allowed:.2f}",
            "provider_claim_count_30d": int(rng.gammavariate(4, 35)),
            "is_duplicate": is_dup,
            "refill_too_soon": refill,
            "ndc_mismatch": mismatch,
            "status": "PAID",
        })
    return rows


def summarize(rows):
    anomalies = 0
    levels = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for r in rows:
        rule = 0
        if r["is_duplicate"]:
            rule += 35
        if r["quantity"] > 90:
            rule += 25
        if float(r["unit_price"]) > float(r["allowed_unit_price"]) * 1.20:
            rule += 25
        if float(r["paid_amount"]) > float(r["allowed_amount"]) * 1.15:
            rule += 35
        if r["days_supply"] > 90:
            rule += 10
        if r["refill_too_soon"]:
            rule += 25
        if r["provider_claim_count_30d"] > 250:
            rule += 15
        if r["ndc_mismatch"]:
            rule += 25
        if rule:
            anomalies += 1
        level = "LOW"
        if rule >= 80:
            level = "CRITICAL"
        elif rule >= 60:
            level = "HIGH"
        elif rule >= 35:
            level = "MEDIUM"
        levels[level] += 1
    return anomalies, levels


def main():
    ap = argparse.ArgumentParser(description="Generate synthetic PBM claims CSV for upload.")
    ap.add_argument("--rows", type=int, default=10_000, help="Number of claims (default 10000)")
    ap.add_argument("--out", default="sample_claims.csv", help="Output file (default sample_claims.csv)")
    ap.add_argument("--seed", type=int, default=None, help="Random seed (default random)")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    rows = generate(args.rows, rng)

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    anomalies, levels = summarize(rows)
    print(f"Wrote {len(rows):,} claims to {args.out}")
    print(f"Rule-flagged anomalies: {anomalies:,}")
    print("Rule risk levels:", ", ".join(f"{k}={v:,}" for k, v in levels.items()))


if __name__ == "__main__":
    main()