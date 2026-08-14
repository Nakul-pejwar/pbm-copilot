def final_score(rule_score: int, ml_score: float):
    score = min(100, round(rule_score * 0.65 + float(ml_score) * 0.35, 2))
    if score >= 80:
        return score, "CRITICAL"
    if score >= 60:
        return score, "HIGH"
    if score >= 35:
        return score, "MEDIUM"
    return score, "LOW"
