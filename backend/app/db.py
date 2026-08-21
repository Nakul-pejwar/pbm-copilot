from sqlalchemy import create_engine, text
from .config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)

CLAIMS_TABLE = """
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
"""

LEGACY_PK_MIGRATION = """
    DO $$
    DECLARE legacy_pk boolean;
    BEGIN
        SELECT EXISTS (
            SELECT 1 FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid AND t.relname = 'claims'
            WHERE c.contype = 'p' AND c.conname = 'claims_pkey'
              AND (SELECT array_agg(a.attname ORDER BY k.ord)
                   FROM unnest(c.conkey) WITH ORDINALITY AS k(attnum, ord)
                   JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum)
                  = ARRAY['claim_id']::name[])
        INTO legacy_pk;
        IF legacy_pk THEN
            ALTER TABLE claims DROP CONSTRAINT claims_pkey;
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid AND t.relname = 'claims'
            WHERE c.contype = 'p'
        ) THEN
            ALTER TABLE claims ADD PRIMARY KEY (company_id, claim_id);
        END IF;
    END $$;
"""

COMPANIES_TABLE = """
    CREATE TABLE IF NOT EXISTS companies (
        company_id text primary key,
        name text not null,
        uploaded_at timestamp not null default now(),
        record_count integer not null default 0,
        status text not null default 'uploaded'
    )
"""

PROVIDER_SCORES_TABLE = """
    CREATE TABLE IF NOT EXISTS provider_scores (
        company_id text not null,
        provider_id text not null,
        claim_count integer not null default 0,
        anomaly_rate numeric(6,4) default 0,
        avg_risk numeric(8,2) default 0,
        critical_count integer default 0,
        high_count integer default 0,
        overpayment_total numeric(14,2) default 0,
        top_rule_codes text default '',
        score integer not null default 300,
        band text not null default 'Poor',
        sufficient_data boolean not null default false,
        factors text default '',
        updated_at timestamp not null default now(),
        primary key (company_id, provider_id)
    )
"""

MIGRATIONS = {
    1: [
        CLAIMS_TABLE,
        "ALTER TABLE claims ADD COLUMN IF NOT EXISTS company_id text not null default 'SEED_DEMO'",
        LEGACY_PK_MIGRATION,
        COMPANIES_TABLE,
    ],
    2: [PROVIDER_SCORES_TABLE],
}


def ensure_schema():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version integer primary key,
                applied_at timestamp not null default now()
            )
        """))
        applied = {
            row[0] for row in conn.execute(text("SELECT version FROM schema_migrations"))
        }
        for version in sorted(MIGRATIONS):
            if version in applied:
                continue
            for statement in MIGRATIONS[version]:
                conn.execute(text(statement))
            conn.execute(
                text("INSERT INTO schema_migrations (version) VALUES (:v)"),
                {"v": version},
            )

def fetch_one(sql, params=None):
    with engine.connect() as conn:
        row = conn.execute(text(sql), params or {}).mappings().first()
        return dict(row) if row else None

def fetch_all(sql, params=None):
    with engine.connect() as conn:
        return [dict(r) for r in conn.execute(text(sql), params or {}).mappings().all()]
