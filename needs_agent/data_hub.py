"""Replaceable MES/Data Hub query facade with SQLite demo data."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from .knowledge import KnowledgeMixin


class NeedsFoodRepository(KnowledgeMixin):
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()
        self.initialize_knowledge()

    @contextmanager
    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _rows(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
        return [dict(row) for row in rows]

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS menus (
                    menu_code TEXT PRIMARY KEY, menu_name TEXT NOT NULL, meal_date TEXT NOT NULL,
                    planned_meals INTEGER NOT NULL, due_at TEXT NOT NULL, status TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS production_batches (
                    batch_id TEXT PRIMARY KEY, menu_code TEXT NOT NULL, kettle_no TEXT NOT NULL,
                    planned_qty INTEGER NOT NULL, actual_qty INTEGER NOT NULL,
                    started_at TEXT, ended_at TEXT, status TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS cooking_readings (
                    reading_id INTEGER PRIMARY KEY, batch_id TEXT NOT NULL, equipment_id TEXT NOT NULL,
                    temperature REAL, stir_speed REAL, pressure REAL, motor_speed REAL,
                    recorded_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS quality_checks (
                    check_id INTEGER PRIMARY KEY, batch_id TEXT, check_type TEXT NOT NULL,
                    sample_count INTEGER, result TEXT NOT NULL, issue TEXT,
                    inspector TEXT NOT NULL, checked_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS inventory (
                    material_code TEXT PRIMARY KEY, material_name TEXT NOT NULL,
                    quantity REAL NOT NULL, unit TEXT NOT NULL, safety_stock REAL NOT NULL,
                    expiry_date TEXT, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS recipe_costs (
                    menu_code TEXT NOT NULL, material_name TEXT NOT NULL,
                    qty_per_meal REAL NOT NULL, unit TEXT NOT NULL, unit_cost REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS shipments (
                    shipment_id TEXT PRIMARY KEY, menu_code TEXT NOT NULL,
                    planned_qty INTEGER NOT NULL, shipped_qty INTEGER NOT NULL,
                    due_at TEXT NOT NULL, shipped_at TEXT, status TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS equipment_events (
                    event_id INTEGER PRIMARY KEY, equipment_id TEXT NOT NULL,
                    event_type TEXT NOT NULL, detail TEXT, occurred_at TEXT NOT NULL,
                    resolved_at TEXT
                );
                """
            )
            if connection.execute("SELECT COUNT(*) FROM menus").fetchone()[0] == 0:
                self._seed(connection)

    @staticmethod
    def _seed(connection: sqlite3.Connection) -> None:
        connection.executemany(
            "INSERT INTO menus VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("M001", "소고기미역국 세트", "2026-09-03", 4000, "2026-09-03 11:20", "생산완료"),
                ("M002", "닭갈비 세트", "2026-09-03", 2800, "2026-09-03 11:30", "생산중"),
                ("M003", "카레라이스 세트", "2026-09-04", 6500, "2026-09-04 11:20", "계획"),
            ],
        )
        connection.executemany(
            "INSERT INTO production_batches VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("B-20260903-M001-01", "M001", "KETTLE-01", 2000, 1980, "2026-09-03 07:10", "2026-09-03 08:25", "완료"),
                ("B-20260903-M001-02", "M001", "KETTLE-02", 2000, 1995, "2026-09-03 07:20", "2026-09-03 08:38", "완료"),
                ("B-20260903-M002-01", "M002", "KETTLE-03", 1400, 1380, "2026-09-03 08:05", "2026-09-03 09:35", "완료"),
                ("B-20260903-M002-02", "M002", "KETTLE-04", 1400, 620, "2026-09-03 09:00", None, "지연"),
            ],
        )
        connection.executemany(
            "INSERT INTO cooking_readings VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (1, "B-20260903-M001-01", "KETTLE-01", 92.4, 38, 1.02, 1180, "2026-09-03 08:00"),
                (2, "B-20260903-M001-02", "KETTLE-02", 93.1, 40, 1.01, 1210, "2026-09-03 08:10"),
                (3, "B-20260903-M002-01", "KETTLE-03", 88.7, 44, 1.04, 1320, "2026-09-03 09:10"),
                (4, "B-20260903-M002-02", "KETTLE-04", 76.2, 31, 0.91, 980, "2026-09-03 10:05"),
            ],
        )
        connection.executemany(
            "INSERT INTO quality_checks VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (1, "B-20260903-M001-01", "영양사 검식", 1, "적합", None, "영양사 A", "2026-09-03 08:30"),
                (2, "B-20260903-M002-01", "영양사 검식", 1, "주의", "염도 편차 관찰", "영양사 A", "2026-09-03 09:40"),
                (3, None, "외부기관 검사", 3, "의뢰중", None, "품질담당 B", "2026-09-03 10:00"),
            ],
        )
        connection.executemany(
            "INSERT INTO inventory VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("R001", "쌀", 1850, "kg", 1200, "2026-12-10", "2026-09-03 06:30"),
                ("R002", "닭고기", 240, "kg", 300, "2026-09-05", "2026-09-03 06:30"),
                ("R003", "미역", 95, "kg", 60, "2027-03-01", "2026-09-03 06:30"),
                ("R004", "카레분말", 180, "kg", 150, "2027-02-12", "2026-09-03 06:30"),
            ],
        )
        connection.executemany(
            "INSERT INTO recipe_costs VALUES (?, ?, ?, ?, ?)",
            [
                ("M001", "쌀", 0.18, "kg", 2600),
                ("M001", "소고기", 0.05, "kg", 14500),
                ("M001", "미역", 0.01, "kg", 9800),
                ("M002", "쌀", 0.18, "kg", 2600),
                ("M002", "닭고기", 0.09, "kg", 7200),
            ],
        )
        connection.executemany(
            "INSERT INTO shipments VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("S-20260903-01", "M001", 4000, 3975, "2026-09-03 11:20", "2026-09-03 11:12", "출하완료"),
                ("S-20260903-02", "M002", 2800, 0, "2026-09-03 11:30", None, "대기"),
            ],
        )
        connection.execute(
            "INSERT INTO equipment_events VALUES (?, ?, ?, ?, ?, ?)",
            (1, "KETTLE-04", "조리지연", "목표 온도 도달 지연", "2026-09-03 09:45", None),
        )

    def dashboard(self, date: str = "2026-09-03") -> dict[str, Any]:
        with self._connect() as connection:
            planned = connection.execute("SELECT COALESCE(SUM(planned_meals),0) FROM menus WHERE meal_date=?", (date,)).fetchone()[0]
            actual = connection.execute(
                """SELECT COALESCE(SUM(b.actual_qty),0) FROM production_batches b
                   JOIN menus m ON m.menu_code=b.menu_code WHERE m.meal_date=?""", (date,)
            ).fetchone()[0]
            delays = connection.execute(
                """SELECT COUNT(*) FROM production_batches b JOIN menus m ON m.menu_code=b.menu_code
                   WHERE m.meal_date=? AND b.status='지연'""", (date,)
            ).fetchone()[0]
            quality = connection.execute("SELECT COUNT(*) FROM quality_checks WHERE checked_at LIKE ? AND result IN ('주의','부적합')", (f"{date}%",)).fetchone()[0]
            shortage = connection.execute("SELECT COUNT(*) FROM inventory WHERE quantity<safety_stock").fetchone()[0]
        return {"planned_meals": planned, "actual_meals": actual, "completion_rate": round(actual/planned*100, 1) if planned else 0, "delayed_batches": delays, "quality_alerts": quality, "stock_shortages": shortage}

    def daily_briefing(self, date: str | None) -> dict[str, Any]:
        day = date or "2026-09-03"
        return {
            "date": day,
            "kpi": self.dashboard(day),
            "delays": self.production_delays(day),
            "inventory_shortages": self.inventory_status(None, True),
            "quality_alerts": self.quality_summary(day, None),
        }

    def production_delays(self, date: str | None) -> list[dict[str, Any]]:
        day = date or "2026-09-03"
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT b.batch_id,m.menu_name,b.kettle_no,b.planned_qty,b.actual_qty,b.status,m.due_at
                   FROM production_batches b JOIN menus m ON m.menu_code=b.menu_code
                   WHERE m.meal_date=? AND b.status IN ('지연','중단') ORDER BY m.due_at""", (day,)
            ).fetchall()
        return self._rows(rows)

    def inventory_status(self, item: str | None, shortage_only: bool = False) -> list[dict[str, Any]]:
        query = """SELECT *, CASE WHEN quantity<safety_stock THEN '부족' ELSE '정상' END AS status
                   FROM inventory WHERE 1=1"""
        params: list[Any] = []
        if item:
            query += " AND material_name LIKE ?"
            params.append(f"%{item}%")
        if shortage_only:
            query += " AND quantity<safety_stock"
        query += " ORDER BY status, material_name"
        with self._connect() as connection:
            return self._rows(connection.execute(query, params).fetchall())

    def quality_summary(self, date: str | None, menu_name: str | None) -> list[dict[str, Any]]:
        query = """SELECT q.check_type,q.batch_id,m.menu_name,q.sample_count,q.result,
                          COALESCE(q.issue,'-') AS issue,q.inspector,q.checked_at
                   FROM quality_checks q LEFT JOIN production_batches b ON b.batch_id=q.batch_id
                   LEFT JOIN menus m ON m.menu_code=b.menu_code WHERE 1=1"""
        params: list[Any] = []
        if date:
            query += " AND q.checked_at LIKE ?"
            params.append(f"{date}%")
        if menu_name:
            query += " AND m.menu_name LIKE ?"
            params.append(f"%{menu_name}%")
        query += " ORDER BY q.checked_at DESC"
        with self._connect() as connection:
            return self._rows(connection.execute(query, params).fetchall())

    def batch_trace(self, batch_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            batch = connection.execute(
                """SELECT b.*,m.menu_name,m.meal_date,m.due_at FROM production_batches b
                   JOIN menus m ON m.menu_code=b.menu_code WHERE b.batch_id=?""", (batch_id,)
            ).fetchone()
            readings = connection.execute("SELECT * FROM cooking_readings WHERE batch_id=? ORDER BY recorded_at", (batch_id,)).fetchall()
            checks = connection.execute("SELECT * FROM quality_checks WHERE batch_id=? ORDER BY checked_at", (batch_id,)).fetchall()
        return {"batch": dict(batch) if batch else None, "cooking_readings": self._rows(readings), "quality_checks": self._rows(checks)}

    def cooking_conditions(self, menu_name: str | None, date: str | None) -> list[dict[str, Any]]:
        query = """SELECT r.*,m.menu_name,m.meal_date,b.kettle_no,b.status
                   FROM cooking_readings r JOIN production_batches b ON b.batch_id=r.batch_id
                   JOIN menus m ON m.menu_code=b.menu_code WHERE 1=1"""
        params: list[Any] = []
        if menu_name:
            query += " AND m.menu_name LIKE ?"
            params.append(f"%{menu_name}%")
        if date:
            query += " AND m.meal_date=?"
            params.append(date)
        query += " ORDER BY r.recorded_at DESC"
        with self._connect() as connection:
            return self._rows(connection.execute(query, params).fetchall())

    def recipe_cost(self, menu_name: str | None) -> list[dict[str, Any]]:
        query = """SELECT m.menu_name,r.material_name,r.qty_per_meal,r.unit,r.unit_cost,
                          ROUND(r.qty_per_meal*r.unit_cost,2) AS cost_per_meal
                   FROM recipe_costs r JOIN menus m ON m.menu_code=r.menu_code WHERE 1=1"""
        params: list[Any] = []
        if menu_name:
            query += " AND m.menu_name LIKE ?"
            params.append(f"%{menu_name}%")
        query += " ORDER BY m.menu_name,r.material_name"
        with self._connect() as connection:
            return self._rows(connection.execute(query, params).fetchall())

    def all_batches(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            return self._rows(connection.execute("SELECT * FROM production_batches ORDER BY started_at DESC").fetchall())
