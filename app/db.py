import psycopg
from pgvector.psycopg import register_vector

from app.config import settings


def connect() -> psycopg.Connection:
    """Ouvre une connexion avec le support des vecteurs activé."""
    conn = psycopg.connect(settings.database_dsn)
    register_vector(conn)
    return conn