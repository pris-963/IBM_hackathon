
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from urllib.parse import quote_plus


# --------------------------------------------------
# MYSQL DATABASE CONFIGURATION
# --------------------------------------------------

DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Rivan@21")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "exposed_safety_db")


# --------------------------------------------------
# CONNECTION URL USING MYSQL CONNECTOR/PYTHON
# --------------------------------------------------

encoded_user = quote_plus(DB_USER)
encoded_password = quote_plus(DB_PASSWORD)

DATABASE_URL = (
    f"mysql+mysqlconnector://{encoded_user}:"
    f"{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)


# --------------------------------------------------
# SQLALCHEMY ENGINE
# --------------------------------------------------

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=5,
    max_overflow=10,
)


# --------------------------------------------------
# SESSION CONFIGURATION
# --------------------------------------------------

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# --------------------------------------------------
# DECLARATIVE BASE
# --------------------------------------------------

Base = declarative_base()


# --------------------------------------------------
# DATABASE DEPENDENCY FOR FASTAPI
# --------------------------------------------------

def get_db():
    """Provide a database session to a FastAPI route."""

    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# --------------------------------------------------
# TEST DATABASE CONNECTION
# --------------------------------------------------

def test_connection():
    """Check whether MySQL is reachable."""

    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
            print("MySQL Connector connection successful.")
            print(f"Database: {DB_NAME}")
            print(f"Host: {DB_HOST}:{DB_PORT}")

    except Exception as exc:
        print("MySQL connection failed.")
        print(f"Host: {DB_HOST}:{DB_PORT}")
        print(f"Database: {DB_NAME}")
        print(f"Error: {exc}")
        raise


if __name__ == "__main__":
    test_connection()
