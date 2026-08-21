import pandas as pd

CLAIMTRUST_NAME = "ClaimTrust Score"
CLAIMTRUST_RANGE = (300, 900)

BANDS = [
    (750, "Excellent"),
    (650, "Good"),
    (550, "Fair"),
    (0, "Poor"),
]

MIN_SCORE = 300
MAX_SCORE = 900
THIN_FILE_MIN_CLAIMS = 10
THIN_FILE_CAP = 650
OVERPAYMENT_THRESHOLD = 1.15

PENALTY_ANOMALY_RATE_W = 400.0
PENALTY_ANOMALY_RATE_MAX = 250.0
PENALTY_CRIT_HIGH_W = 600.0
PENALTY_CRIT_HIGH_MAX = 200.0
PENALTY_OVERPAYMENT_W = 800.0
PENALTY_OVERPAYMENT_MAX = 150.0
PENALTY_AVG_RISK_W = 1.5
PENALTY_AVG_RISK_MAX = 100.0


def band_for(score: int) -> str:
    for threshold, band in BANDS:
        if score >= threshold:
            return band
    return "Poor"


def _top_rules(g):
    counts = {}
    for codes in g["rule_codes"]:
        if not codes:
            continue
        for code in codes.split("|"):
            counts[code] = counts.get(code, 0) + 1
    return sorted(counts, key=counts.get, reverse=True)[:3]


def compute_provider_scores(df):
    """Aggregate per-provider ClaimTrust scores within one company's claims.

    Deterministic penalty model (CIBIL-style 300-900): every provider starts at
    900 and loses points for anomaly rate (<=250), CRITICAL/HIGH share (<=200),
    overpayments (<=150) and average risk (<=100). Providers with too few claims
    (thin files) are capped at 650.
    """
    rows = []
    for pid, g in df.groupby("provider_id"):
        n = len(g)
        anomalies = int(g["anomaly"].sum())
        anomaly_rate = anomalies / n if n else 0.0
        avg_risk = float(g["risk_score"].mean()) if n else 0.0
        critical = int((g["risk_level"] == "CRITICAL").sum())
        high = int((g["risk_level"] == "HIGH").sum())
        over = g[g["paid_amount"] > g["allowed_amount"] * OVERPAYMENT_THRESHOLD]
        overpayment_total = float(
            (over["paid_amount"] - over["allowed_amount"]).sum()
        ) if len(over) else 0.0
        total_paid = float(g["paid_amount"].sum()) or 1.0
        overpayment_rate = overpayment_total / total_paid

        crit_high_share = (critical + high) / n if n else 0.0
        p_anomaly = min(PENALTY_ANOMALY_RATE_MAX, anomaly_rate * PENALTY_ANOMALY_RATE_W)
        p_ch = min(PENALTY_CRIT_HIGH_MAX, crit_high_share * PENALTY_CRIT_HIGH_W)
        p_over = min(PENALTY_OVERPAYMENT_MAX, overpayment_rate * PENALTY_OVERPAYMENT_W)
        p_risk = min(PENALTY_AVG_RISK_MAX, avg_risk * PENALTY_AVG_RISK_W)

        score = int(round(MAX_SCORE - p_anomaly - p_ch - p_over - p_risk))
        score = max(MIN_SCORE, score)
        sufficient = bool(n >= THIN_FILE_MIN_CLAIMS)
        if not sufficient:
            score = min(score, THIN_FILE_CAP)

        rows.append({
            "provider_id": pid,
            "claim_count": n,
            "anomaly_rate": round(anomaly_rate, 4),
            "avg_risk": round(avg_risk, 2),
            "critical_count": critical,
            "high_count": high,
            "overpayment_total": round(overpayment_total, 2),
            "top_rule_codes": "|".join(_top_rules(g)),
            "score": score,
            "band": band_for(score),
            "sufficient_data": sufficient,
            "factors": {
                "penalty_anomaly": round(p_anomaly, 2),
                "penalty_critical_high": round(p_ch, 2),
                "penalty_overpayment": round(p_over, 2),
                "penalty_avg_risk": round(p_risk, 2),
            },
        })
    return pd.DataFrame(rows)