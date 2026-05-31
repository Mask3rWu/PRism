from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./prism.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def _migrate_db():
    """Add missing columns to existing tables (no Alembic)."""
    with engine.connect() as conn:
        result = conn.exec_driver_sql("PRAGMA table_info(projects)")
        columns = {row[1] for row in result}
        if "tags" not in columns:
            conn.exec_driver_sql("ALTER TABLE projects ADD COLUMN tags TEXT DEFAULT '[]'")
        if "is_favorite" not in columns:
            conn.exec_driver_sql("ALTER TABLE projects ADD COLUMN is_favorite BOOLEAN DEFAULT 0")
        if "permission" not in columns:
            conn.exec_driver_sql("ALTER TABLE projects ADD COLUMN permission TEXT DEFAULT 'Viewer'")
        if "last_synced_at" not in columns:
            conn.exec_driver_sql("ALTER TABLE projects ADD COLUMN last_synced_at TIMESTAMP")
        conn.commit()

        result = conn.exec_driver_sql("PRAGMA table_info(app_settings)")
        columns = {row[1] for row in result}
        if "encrypted_llm_api_key" not in columns:
            conn.exec_driver_sql("ALTER TABLE app_settings ADD COLUMN encrypted_llm_api_key TEXT DEFAULT ''")
        if "llm_provider" not in columns:
            conn.exec_driver_sql("ALTER TABLE app_settings ADD COLUMN llm_provider TEXT DEFAULT 'pat'")
        if "llm_endpoint" not in columns:
            conn.exec_driver_sql("ALTER TABLE app_settings ADD COLUMN llm_endpoint TEXT DEFAULT ''")
        if "llm_model" not in columns:
            conn.exec_driver_sql("ALTER TABLE app_settings ADD COLUMN llm_model TEXT DEFAULT ''")
        if "review_count" not in columns:
            conn.exec_driver_sql("ALTER TABLE app_settings ADD COLUMN review_count INTEGER DEFAULT 0")
        conn.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
