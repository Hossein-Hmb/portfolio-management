"""SQLAlchemy engine + session setup."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

DB_PATH = os.environ.get("PORTFOLIO_DB", os.path.join(os.path.dirname(__file__), "..", "portfolio.db"))
DB_PATH = os.path.abspath(DB_PATH)

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
