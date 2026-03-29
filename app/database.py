import os
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent
_env_db = os.environ.get("SQLITE_PATH")
if _env_db:
    db_path = Path(_env_db).expanduser()
    if not db_path.is_absolute():
        db_path = BASE_DIR / db_path
else:
    db_path = BASE_DIR / "notes.sqlite3"
db_path.parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = f"sqlite:///{db_path}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _sqlite_enable_fk(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def apply_sqlite_migrations() -> None:
    if not DATABASE_URL.startswith("sqlite"):
        return
    inspector = inspect(engine)
    if not inspector.has_table("notes"):
        return
    col_names = {c["name"] for c in inspector.get_columns("notes")}
    if "tag_id" in col_names:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE notes ADD COLUMN tag_id INTEGER"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
