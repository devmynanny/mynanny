from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()


def ensure_audit_log_schema() -> None:
    with engine.begin() as conn:
        exists = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_logs'"))
        if not exists.fetchone():
            return

        cols = conn.execute(text("PRAGMA table_info(audit_logs)"))
        existing = {row[1] for row in cols.fetchall()}

        def add_col(name: str, col_type: str):
            if name not in existing:
                conn.execute(text(f"ALTER TABLE audit_logs ADD COLUMN {name} {col_type}"))

        add_col("actor_user_id", "INTEGER")
        add_col("actor_role", "TEXT")
        add_col("target_user_id", "INTEGER")
        add_col("entity", "TEXT")
        add_col("entity_type", "TEXT")
        add_col("entity_id", "TEXT")
        add_col("action", "TEXT")
        add_col("before_json", "TEXT")
        add_col("after_json", "TEXT")
        add_col("changed_fields", "TEXT")
        add_col("ip", "TEXT")
        add_col("user_agent", "TEXT")
        add_col("created_at", "DATETIME")
        add_col("event_type", "TEXT")
        add_col("details", "TEXT")

        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_actor_user_id ON audit_logs(actor_user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_target_user_id ON audit_logs(target_user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_entity ON audit_logs(entity)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_entity_id ON audit_logs(entity_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_action ON audit_logs(action)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs(created_at)"))


def _table_exists(conn, name: str) -> bool:
    exists = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"), {"name": name})
    return exists.fetchone() is not None


def ensure_booking_requests_schema() -> None:
    with engine.begin() as conn:
        if not _table_exists(conn, "booking_requests"):
            return

        cols = conn.execute(text("PRAGMA table_info(booking_requests)"))
        existing = {row[1] for row in cols.fetchall()}

        create_sql_row = conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type='table' AND name='booking_requests'")
        ).fetchone()
        create_sql = create_sql_row[0] if create_sql_row else ""

        needs_rebuild = False
        if "start_dt" not in existing or "end_dt" not in existing:
            needs_rebuild = True
        if "tbc" not in (create_sql or ""):
            needs_rebuild = True

        if not needs_rebuild:
            if "group_id" not in existing:
                conn.execute(text("ALTER TABLE booking_requests ADD COLUMN group_id BIGINT"))
                conn.execute(text("UPDATE booking_requests SET group_id = id WHERE group_id IS NULL"))
            if "sleepover" not in existing:
                conn.execute(text("ALTER TABLE booking_requests ADD COLUMN sleepover BOOLEAN"))
            if "wage_cents" not in existing:
                conn.execute(text("ALTER TABLE booking_requests ADD COLUMN wage_cents INTEGER"))
            if "booking_fee_pct" not in existing:
                conn.execute(text("ALTER TABLE booking_requests ADD COLUMN booking_fee_pct NUMERIC(5,4)"))
            if "booking_fee_cents" not in existing:
                conn.execute(text("ALTER TABLE booking_requests ADD COLUMN booking_fee_cents INTEGER"))
            if "total_cents" not in existing:
                conn.execute(text("ALTER TABLE booking_requests ADD COLUMN total_cents INTEGER"))
            if "paid_at" not in existing:
                conn.execute(text("ALTER TABLE booking_requests ADD COLUMN paid_at DATETIME"))
            if "company_retained_cents" not in existing:
                conn.execute(text("ALTER TABLE booking_requests ADD COLUMN company_retained_cents INTEGER"))
            if "nanny_retained_cents" not in existing:
                conn.execute(text("ALTER TABLE booking_requests ADD COLUMN nanny_retained_cents INTEGER"))
            if "refund_cents" not in existing:
                conn.execute(text("ALTER TABLE booking_requests ADD COLUMN refund_cents INTEGER"))
            if "refund_status" not in existing:
                conn.execute(text("ALTER TABLE booking_requests ADD COLUMN refund_status TEXT"))
            if "refund_requested_at" not in existing:
                conn.execute(text("ALTER TABLE booking_requests ADD COLUMN refund_requested_at DATETIME"))
            if "refund_processed_at" not in existing:
                conn.execute(text("ALTER TABLE booking_requests ADD COLUMN refund_processed_at DATETIME"))
            if "refund_failed_at" not in existing:
                conn.execute(text("ALTER TABLE booking_requests ADD COLUMN refund_failed_at DATETIME"))
            if "refund_failure_reason" not in existing:
                conn.execute(text("ALTER TABLE booking_requests ADD COLUMN refund_failure_reason TEXT"))
            if "refund_reviewed_at" not in existing:
                conn.execute(text("ALTER TABLE booking_requests ADD COLUMN refund_reviewed_at DATETIME"))
            if "refund_reviewed_by" not in existing:
                conn.execute(text("ALTER TABLE booking_requests ADD COLUMN refund_reviewed_by BIGINT"))
            if "refund_review_reason" not in existing:
                conn.execute(text("ALTER TABLE booking_requests ADD COLUMN refund_review_reason TEXT"))
            if "paystack_reference" not in existing:
                conn.execute(text("ALTER TABLE booking_requests ADD COLUMN paystack_reference TEXT"))
            if "paystack_transaction_id" not in existing:
                conn.execute(text("ALTER TABLE booking_requests ADD COLUMN paystack_transaction_id TEXT"))
            if "paystack_refund_reference" not in existing:
                conn.execute(text("ALTER TABLE booking_requests ADD COLUMN paystack_refund_reference TEXT"))
            if "cancelled_at" not in existing:
                conn.execute(text("ALTER TABLE booking_requests ADD COLUMN cancelled_at DATETIME"))
            return

        conn.execute(text("ALTER TABLE booking_requests RENAME TO booking_requests_old"))

        conn.execute(text("""
            CREATE TABLE booking_requests (
              id BIGINT NOT NULL PRIMARY KEY,
              parent_user_id BIGINT NOT NULL,
              nanny_id BIGINT NOT NULL,
              status TEXT NOT NULL DEFAULT 'tbc',
              group_id BIGINT,
              start_dt TEXT,
              end_dt TEXT,
              sleepover BOOLEAN,
              wage_cents INTEGER,
              booking_fee_pct NUMERIC(5,4),
              booking_fee_cents INTEGER,
              total_cents INTEGER,
              paid_at DATETIME,
              company_retained_cents INTEGER,
              nanny_retained_cents INTEGER,
              refund_cents INTEGER,
              refund_status TEXT,
              refund_requested_at DATETIME,
              refund_processed_at DATETIME,
              refund_failed_at DATETIME,
              refund_failure_reason TEXT,
              refund_reviewed_at DATETIME,
              refund_reviewed_by BIGINT,
              refund_review_reason TEXT,
              paystack_reference TEXT,
              paystack_transaction_id TEXT,
              paystack_refund_reference TEXT,
              cancelled_at DATETIME,
              hold_expires_at DATETIME,
              payment_status TEXT NOT NULL DEFAULT 'pending_payment',
              admin_notes TEXT,
              client_notes TEXT,
              created_by_admin_user_id BIGINT,
              requested_starts_at DATETIME NOT NULL,
              requested_ends_at DATETIME NOT NULL,
              location_id BIGINT,
              admin_user_id BIGINT,
              admin_decided_at DATETIME,
              admin_reason TEXT,
              created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
              updated_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
              CONSTRAINT booking_requests_status_check CHECK (status IN ('tbc','pending_admin','approved','rejected','cancelled')),
              CONSTRAINT booking_requests_payment_status_check CHECK (payment_status IN ('pending_payment','paid','cancelled')),
              FOREIGN KEY(parent_user_id) REFERENCES users (id) ON DELETE RESTRICT,
              FOREIGN KEY(nanny_id) REFERENCES nannies (id) ON DELETE RESTRICT,
              FOREIGN KEY(created_by_admin_user_id) REFERENCES users (id) ON DELETE SET NULL,
              FOREIGN KEY(location_id) REFERENCES parent_locations (id) ON DELETE SET NULL,
              FOREIGN KEY(admin_user_id) REFERENCES users (id) ON DELETE SET NULL
            );
        """))

        conn.execute(text("""
            INSERT INTO booking_requests (
              id, parent_user_id, nanny_id, status, group_id, start_dt, end_dt,
              sleepover, wage_cents, booking_fee_pct, booking_fee_cents, total_cents,
              paid_at, company_retained_cents, nanny_retained_cents, refund_cents,
              refund_status, refund_requested_at, refund_processed_at, refund_failed_at,
              refund_failure_reason, refund_reviewed_at, refund_reviewed_by, refund_review_reason,
              paystack_reference, paystack_transaction_id, paystack_refund_reference,
              cancelled_at,
              hold_expires_at, payment_status, admin_notes, client_notes,
              created_by_admin_user_id, requested_starts_at, requested_ends_at,
              location_id, admin_user_id, admin_decided_at, admin_reason,
              created_at, updated_at
            )
            SELECT
              id,
              parent_user_id,
              nanny_id,
              CASE WHEN status = 'pending_admin' THEN 'tbc' ELSE status END,
              id,
              CAST(requested_starts_at AS TEXT),
              CAST(requested_ends_at AS TEXT),
              NULL,
              NULL,
              NULL,
              NULL,
              NULL,
              NULL,
              NULL,
              NULL,
              NULL,
              NULL,
              NULL,
              NULL,
              NULL,
              NULL,
              NULL,
              NULL,
              NULL,
              NULL,
              NULL,
              NULL,
              NULL,
              hold_expires_at,
              payment_status,
              admin_notes,
              client_notes,
              created_by_admin_user_id,
              requested_starts_at,
              requested_ends_at,
              location_id,
              admin_user_id,
              admin_decided_at,
              admin_reason,
              created_at,
              updated_at
            FROM booking_requests_old;
        """))

        conn.execute(text("DROP TABLE booking_requests_old"))


def ensure_nanny_availability_schema() -> None:
    with engine.begin() as conn:
        if not _table_exists(conn, "nanny_availability"):
            return

        cols = conn.execute(text("PRAGMA table_info(nanny_availability)"))
        existing = {row[1] for row in cols.fetchall()}

        def add_col(name: str, col_type: str):
            if name not in existing:
                conn.execute(text(f"ALTER TABLE nanny_availability ADD COLUMN {name} {col_type}"))

        add_col("start_dt", "TEXT")
        add_col("end_dt", "TEXT")
        add_col("type", "TEXT DEFAULT 'available'")


def ensure_bookings_schema() -> None:
    with engine.begin() as conn:
        if not _table_exists(conn, "bookings"):
            return

        cols = conn.execute(text("PRAGMA table_info(bookings)"))
        existing = {row[1] for row in cols.fetchall()}

        def add_col(name: str, col_type: str):
            if name not in existing:
                conn.execute(text(f"ALTER TABLE bookings ADD COLUMN {name} {col_type}"))

        add_col("start_dt", "TEXT")
        add_col("end_dt", "TEXT")
        add_col("check_in_at", "DATETIME")
        add_col("check_in_lat", "FLOAT")
        add_col("check_in_lng", "FLOAT")
        add_col("check_in_distance_m", "FLOAT")
        add_col("check_out_at", "DATETIME")
        add_col("check_out_lat", "FLOAT")
        add_col("check_out_lng", "FLOAT")
        add_col("check_out_distance_m", "FLOAT")


def ensure_nanny_profiles_schema() -> None:
    with engine.begin() as conn:
        if not _table_exists(conn, "nanny_profiles"):
            return

        cols = conn.execute(text("PRAGMA table_info(nanny_profiles)"))
        existing = {row[1] for row in cols.fetchall()}

        def add_col(name: str, col_type: str):
            if name not in existing:
                conn.execute(text(f"ALTER TABLE nanny_profiles ADD COLUMN {name} {col_type}"))

        add_col("application_status", "TEXT")
        add_col("admin_reason", "TEXT")
        add_col("reviewed_at", "TEXT")
        add_col("reviewed_by_user_id", "INTEGER")
        add_col("passport_number", "TEXT")
        add_col("passport_expiry", "TEXT")
        add_col("passport_document_url", "TEXT")
        add_col("work_permit", "BOOLEAN")
        add_col("work_permit_expiry", "TEXT")
        add_col("work_permit_document_url", "TEXT")
        add_col("waiver", "BOOLEAN")
        add_col("sa_id_number", "TEXT")
        add_col("sa_id_document_url", "TEXT")
        add_col("previous_jobs_json", "TEXT")


def ensure_admin_invites_schema() -> None:
    with engine.begin() as conn:
        if _table_exists(conn, "admin_invites"):
            return

        conn.execute(text("""
            CREATE TABLE admin_invites (
              id INTEGER NOT NULL PRIMARY KEY,
              email TEXT NOT NULL,
              token TEXT NOT NULL UNIQUE,
              status TEXT NOT NULL DEFAULT 'pending',
              created_at DATETIME NOT NULL,
              expires_at DATETIME NOT NULL,
              accepted_at DATETIME,
              invited_by_user_id INTEGER,
              accepted_user_id INTEGER,
              reason TEXT,
              FOREIGN KEY(invited_by_user_id) REFERENCES users (id),
              FOREIGN KEY(accepted_user_id) REFERENCES users (id)
            );
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_admin_invites_email ON admin_invites(email)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_admin_invites_token ON admin_invites(token)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_admin_invites_email_status ON admin_invites(email, status)"))


def ensure_users_schema() -> None:
    with engine.begin() as conn:
        if not _table_exists(conn, "users"):
            return
        cols = conn.execute(text("PRAGMA table_info(users)"))
        existing = {row[1] for row in cols.fetchall()}
        if "is_admin" not in existing:
            conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0"))
        if "is_active" not in existing:
            conn.execute(text("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1"))
        if "phone_alt" not in existing:
            conn.execute(text("ALTER TABLE users ADD COLUMN phone_alt TEXT"))


def ensure_languages_seed() -> None:
    with engine.begin() as conn:
        if not _table_exists(conn, "languages"):
            return
        rows = conn.execute(text("SELECT name FROM languages")).fetchall()
        existing = {row[0] for row in rows}
        languages = [
            "Afrikaans",
            "English",
            "isiNdebele",
            "isiXhosa",
            "isiZulu",
            "Sepedi",
            "Sesotho",
            "Setswana",
            "siSwati",
            "Tshivenda",
            "Xitsonga",
            "South African Sign Language",
        ]
        for name in languages:
            if name not in existing:
                conn.execute(text("INSERT INTO languages (name) VALUES (:name)"), {"name": name})


def ensure_parent_favorites_schema() -> None:
    with engine.begin() as conn:
        if _table_exists(conn, "parent_favorites"):
            return
        conn.execute(text("""
            CREATE TABLE parent_favorites (
              id INTEGER NOT NULL PRIMARY KEY,
              parent_user_id INTEGER NOT NULL,
              nanny_id INTEGER NOT NULL,
              created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP),
              FOREIGN KEY(parent_user_id) REFERENCES users (id) ON DELETE CASCADE,
              FOREIGN KEY(nanny_id) REFERENCES nannies (id) ON DELETE CASCADE,
              CONSTRAINT uq_parent_favorite UNIQUE (parent_user_id, nanny_id)
            );
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_parent_favorites_parent_user_id ON parent_favorites(parent_user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_parent_favorites_nanny_id ON parent_favorites(nanny_id)"))


def ensure_pricing_settings_schema() -> None:
    with engine.begin() as conn:
        if not _table_exists(conn, "pricing_settings"):
            conn.execute(text("""
                CREATE TABLE pricing_settings (
                  id INTEGER NOT NULL PRIMARY KEY,
                  weekday_half_day INTEGER NOT NULL DEFAULT 250,
                  weekday_full_day INTEGER NOT NULL DEFAULT 300,
                  weekend_half_day INTEGER NOT NULL DEFAULT 300,
                  weekend_full_day INTEGER NOT NULL DEFAULT 350,
                  sleepover_add INTEGER NOT NULL DEFAULT 150,
                  sleepover_only_weekday INTEGER NOT NULL DEFAULT 400,
                  sleepover_only_weekend INTEGER NOT NULL DEFAULT 450,
                  sleepover_extra_hour_over14 INTEGER NOT NULL DEFAULT 50,
                  after17_weekday INTEGER NOT NULL DEFAULT 30,
                  after17_weekend INTEGER NOT NULL DEFAULT 35,
                  over9_weekday INTEGER NOT NULL DEFAULT 45,
                  over9_weekend INTEGER NOT NULL DEFAULT 50,
                  sleepover_start_hour INTEGER NOT NULL DEFAULT 14,
                  sleepover_end_hour INTEGER NOT NULL DEFAULT 7,
                  sleepover_after7_hourly INTEGER NOT NULL DEFAULT 45,
                  booking_fee_pct_1_5 NUMERIC(5,4) NOT NULL DEFAULT 0.30,
                  booking_fee_pct_6_10 NUMERIC(5,4) NOT NULL DEFAULT 0.27,
                  booking_fee_pct_10_plus NUMERIC(5,4) NOT NULL DEFAULT 0.25,
                  cancellation_fee_window_hours INTEGER NOT NULL DEFAULT 12
                );
            """))
            conn.execute(text("INSERT INTO pricing_settings (id) VALUES (1)"))
            return

        rows = conn.execute(text("SELECT COUNT(*) FROM pricing_settings")).fetchone()
        if rows and rows[0] == 0:
            conn.execute(text("INSERT INTO pricing_settings (id) VALUES (1)"))

        cols = conn.execute(text("PRAGMA table_info(pricing_settings)"))
        existing = {row[1] for row in cols.fetchall()}
        if "cancellation_fee_window_hours" not in existing:
            conn.execute(text("ALTER TABLE pricing_settings ADD COLUMN cancellation_fee_window_hours INTEGER NOT NULL DEFAULT 12"))
