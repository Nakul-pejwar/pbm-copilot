from dataclasses import dataclass

@dataclass
class RuleResult:
    code: str
    severity: str
    score: int
    evidence: str

def evaluate(c):
    results = []
    def add(code, severity, score, evidence):
        results.append(RuleResult(code, severity, score, evidence))

    if c["is_duplicate"]:
        add("DUPLICATE_CLAIM", "HIGH", 35, "Same member/provider/product/date combination appears more than once.")
    if c["quantity"] > 90:
        add("HIGH_QUANTITY", "HIGH", 25, f"Quantity {c['quantity']} is unusually high.")
    if c["unit_price"] > c["allowed_unit_price"] * 1.20:
        add("PRICE_DEVIATION", "HIGH", 25, "Submitted unit price is more than 20% above allowed baseline.")
    if c["paid_amount"] > c["allowed_amount"] * 1.15:
        add("OVERPAYMENT", "CRITICAL", 35, "Paid amount materially exceeds the allowed amount.")
    if c["days_supply"] > 90:
        add("LONG_DAYS_SUPPLY", "MEDIUM", 10, f"Days supply is {c['days_supply']}.")
    if c["refill_too_soon"]:
        add("REFILL_TOO_SOON", "HIGH", 25, "Refill occurred before the expected refill interval.")
    if c["provider_claim_count_30d"] > 250:
        add("PROVIDER_VOLUME_OUTLIER", "MEDIUM", 15, "Provider has unusually high recent claim volume.")
    if c["ndc_mismatch"]:
        add("PRODUCT_MISMATCH", "HIGH", 25, "Product/NDC combination failed the expected plan mapping.")

    return results
