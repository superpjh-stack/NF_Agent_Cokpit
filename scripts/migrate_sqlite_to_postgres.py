"""Explicit full-replacement import; atomic and repeatable. Source is read-only."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from needs_agent.postgres import PostgresRepository
from needs_agent.knowledge import MIGRATION_TABLES


def migrate(source, target):
    source = Path(source).resolve()
    if not source.is_file():
        raise ValueError("원본 SQLite 파일이 없습니다.")
    with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        present = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        missing = set(MIGRATION_TABLES) - present
        if missing:
            raise ValueError("이관 전 최신 앱으로 원본을 초기화하세요. 누락 테이블: " + ", ".join(sorted(missing)))
        snapshot = {name: [dict(r) for r in connection.execute(f"SELECT * FROM {name}")] for name in MIGRATION_TABLES}
    with target._connect() as connection:
        for table in reversed(MIGRATION_TABLES):
            connection.execute(f"DELETE FROM {table}")
        for table, rows in snapshot.items():
            if not rows:
                continue
            columns = list(rows[0])
            # Source schema column names are validated before constructing identifiers.
            import re
            if not all(re.fullmatch(r"[a-z_]+", col) for col in columns):
                raise ValueError("지원하지 않는 원본 컬럼 이름입니다.")
            connection.executemany(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})", [[r[c] for c in columns] for r in rows])
        for table, rows in snapshot.items():
            if connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] != len(rows):
                raise ValueError("이관 행 수 검증 실패: " + table)
    return {table: len(rows) for table, rows in snapshot.items()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--replace", action="store_true", required=True, help="대상 데이터 전체 교체를 명시적으로 선택")
    args = parser.parse_args()
    url = os.environ.get("DATABASE_URL")
    if not url:
        parser.error("DATABASE_URL을 설정하세요.")
    print(migrate(args.source, PostgresRepository(url)))
