import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

FEATURES = [
    "quantity", "days_supply", "unit_price", "allowed_unit_price",
    "paid_amount", "allowed_amount", "provider_claim_count_30d"
]

def fit_model(df):
    X = df[FEATURES].astype(float).fillna(0)
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)
    model = IsolationForest(
        n_estimators=150,
        contamination=0.03,
        random_state=42,
        n_jobs=-1
    )
    model.fit(Xs)
    return model, scaler

def score_model(model, scaler, df):
    X = scaler.transform(df[FEATURES].astype(float).fillna(0))
    raw = model.decision_function(X)
    pred = model.predict(X)
    # Lower decision_function = more anomalous. Normalize to 0..100.
    score = (1 - (raw - raw.min()) / (raw.max() - raw.min() + 1e-9)) * 100
    return score.round(2), (pred == -1)
