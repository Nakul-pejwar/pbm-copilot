from sqlalchemy import create_engine, text
from .config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)

def ensure_schema():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS claims (
                claim_id text,
                claim_date date,
                member_id text,
                provider_id text,
                plan_id text,
                product_id text,
                quantity integer,
                days_supply integer,
                unit_price numeric(12,2),
                allowed_unit_price numeric(12,2),
                paid_amount numeric(14,2),
                allowed_amount numeric(14,2),
                provider_claim_count_30d integer,
                is_duplicate boolean,
                refill_too_soon boolean,
                ndc_mismatch boolean,
                status text,
                company_id text not null default 'SEED_DEMO',
                rule_score integer default 0,
                ml_score numeric(8,2) default 0,
                risk_score numeric(8,2) default 0,
                risk_level text default 'LOW',
                anomaly boolean default false,
                rule_codes text default '',
                evidence text default ''
            )
        """))
        conn.execute(text("""
            ALTER TABLE claims ADD COLUMN IF NOT EXISTS company_id text not null default 'SEED_DEMO'
        """))
        conn.execute(text("""
            ALTER TABLE claims DROP CONSTRAINT IF EXISTS claims_pkey
        """))
        conn.execute(text("""
            ALTER TABLE claims ADD PRIMARY KEY (company_id, claim_id)
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS companies (
                company_id text primary key,
                name text not null,
                uploaded_at timestamp not null default now(),
                record_count integer not null default 0,
                status text not null default 'uploaded'
            )
        """))

def fetch_one(sql, params=None):
    with engine.connect() as conn:
        row = conn.execute(text(sql), params or {}).mappings().first()
        return dict(row) if row else None

def fetch_all(sql, params=None):
    with engine.connect() as conn:
        return [dict(r) for r in conn.execute(text(sql), params or {}).mappings().all()]
