"""PostgreSQL adapter; business queries remain shared with SQLite."""
import os
from contextlib import contextmanager

from .data_hub import NeedsFoodRepository
from .config import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL


class Row(dict):
    def __getitem__(self, key):
        return list(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


def row_factory(cursor):
    columns = [col.name for col in cursor.description or []]
    return lambda values: Row(zip(columns, values))


class Connection:
    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql, params=()):
        sql = sql.replace("?", "%s").replace("ROUND(r.qty_per_meal*r.unit_cost,2)", "ROUND((r.qty_per_meal*r.unit_cost)::numeric,2)")
        return self.raw.execute(sql, params)

    def executemany(self, sql, rows):
        with self.raw.cursor() as cursor:
            cursor.executemany(sql.replace("?", "%s"), rows)

    def executescript(self, sql):
        for statement in sql.split(";"):
            if statement.strip():
                self.execute(statement)


class PostgresRepository(NeedsFoodRepository):
    backend = "PostgreSQL + pgvector · 데모 데이터"

    def __init__(self, url):
        import psycopg
        self.url = url
        # Bootstrap BEFORE any pgvector adapter registration, including on fresh DBs.
        with psycopg.connect(url) as raw:
            raw.execute("CREATE EXTENSION IF NOT EXISTS vector")
        self._initialize()
        self.initialize_knowledge()
        with self._connect() as con:
            con.execute(f"ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS embedding vector({EMBEDDING_DIMENSIONS})")
            con.execute("ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS embedding_model TEXT")
            con.execute("CREATE INDEX IF NOT EXISTS knowledge_embedding_hnsw ON knowledge_documents USING hnsw (embedding vector_cosine_ops)")

    @contextmanager
    def _connect(self):
        import psycopg
        from pgvector.psycopg import register_vector
        raw = psycopg.connect(self.url, row_factory=row_factory)
        try:
            register_vector(raw)
            with raw:
                yield Connection(raw)
        finally:
            raw.close()

    def save_embedding(self, document_id, vector, model=EMBEDDING_MODEL):
        import numpy as np
        values = np.asarray(vector, dtype=float)
        if values.shape != (EMBEDDING_DIMENSIONS,) or not np.isfinite(values).all():
            raise ValueError("문서 벡터 차원 또는 값이 올바르지 않습니다.")
        with self._connect() as con:
            con.execute("UPDATE knowledge_documents SET embedding=?,embedding_model=? WHERE document_id=?", (values, model, document_id))

    def nearest_knowledge(self, vector, limit=5):
        import numpy as np
        values = np.asarray(vector, dtype=float)
        if values.shape != (EMBEDDING_DIMENSIONS,) or not np.isfinite(values).all() or not 1 <= limit <= 20:
            raise ValueError("검색 벡터 또는 검색 개수가 올바르지 않습니다.")
        with self._connect() as con:
            return self._rows(con.execute("SELECT document_id,filename,title,body AS text,status,revision,embedding <=> ? AS distance FROM knowledge_documents WHERE embedding IS NOT NULL AND embedding_model=? ORDER BY embedding <=> ? LIMIT ?", (values, EMBEDDING_MODEL, values, limit)).fetchall())


def create_repository(database_path, database_url=None):
    url = database_url if database_url is not None else os.getenv("DATABASE_URL", "")
    return PostgresRepository(url) if url else NeedsFoodRepository(database_path)
