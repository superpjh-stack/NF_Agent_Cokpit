"""Replaceable MES/Data Hub query facade with SQLite demo data."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from .knowledge import KnowledgeMixin
from .kimchi import scale_formulation


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
                CREATE TABLE IF NOT EXISTS kimchi_products (
                    product_code TEXT PRIMARY KEY, product_name TEXT NOT NULL,
                    product_type TEXT, status TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS kimchi_formulations (
                    formulation_id TEXT PRIMARY KEY, product_code TEXT NOT NULL,
                    revision TEXT NOT NULL, effective_date TEXT NOT NULL,
                    weight_basis TEXT NOT NULL, batch_quantity REAL NOT NULL,
                    approval_status TEXT NOT NULL, source_document TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS kimchi_formulation_items (
                    formulation_id TEXT NOT NULL, line_no INTEGER NOT NULL,
                    material_code TEXT NOT NULL, material_name TEXT NOT NULL,
                    quantity REAL NOT NULL, unit TEXT NOT NULL,
                    PRIMARY KEY (formulation_id, line_no)
                );
                CREATE TABLE IF NOT EXISTS kimchi_material_lots (
                    material_lot TEXT PRIMARY KEY, material_code TEXT NOT NULL,
                    material_name TEXT NOT NULL, received_quantity REAL NOT NULL,
                    remaining_quantity REAL NOT NULL, reserved_quantity REAL NOT NULL,
                    hold_quantity REAL NOT NULL, unit TEXT NOT NULL,
                    expiry_date TEXT, quality_status TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS kimchi_production_lots (
                    production_lot TEXT PRIMARY KEY, product_code TEXT NOT NULL,
                    formulation_id TEXT NOT NULL, production_date TEXT NOT NULL,
                    target_quantity REAL NOT NULL, weight_basis TEXT NOT NULL,
                    actual_output REAL, status TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS kimchi_lot_inputs (
                    production_lot TEXT NOT NULL, material_lot TEXT NOT NULL,
                    actual_quantity REAL NOT NULL, unit TEXT NOT NULL,
                    PRIMARY KEY (production_lot, material_lot)
                );
                CREATE TABLE IF NOT EXISTS kimchi_process_records (
                    record_id TEXT PRIMARY KEY, production_lot TEXT NOT NULL,
                    process_step TEXT NOT NULL, standard_value TEXT,
                    measured_value TEXT, source_document TEXT,
                    recorded_at TEXT, operator TEXT, disposition TEXT
                );
                CREATE TABLE IF NOT EXISTS kimchi_packaging_lots (
                    packaging_lot TEXT PRIMARY KEY, production_lot TEXT NOT NULL,
                    package_spec TEXT, package_count INTEGER, packed_quantity REAL,
                    shipped_to TEXT, shipment_status TEXT
                );
                CREATE TABLE IF NOT EXISTS kimchi_quality_results (
                    result_id TEXT PRIMARY KEY, production_lot TEXT NOT NULL,
                    packaging_lot TEXT, check_type TEXT NOT NULL, item_name TEXT NOT NULL,
                    standard_value TEXT, measured_value TEXT, source_document TEXT,
                    checked_at TEXT, result TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS kimchi_lots (
                    lot_id TEXT PRIMARY KEY, parent_lot_id TEXT, process TEXT NOT NULL,
                    product_name TEXT NOT NULL, quantity_kg REAL NOT NULL,
                    supplier TEXT, origin TEXT, status TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS kimchi_process_measurements (
                    measurement_id INTEGER PRIMARY KEY, lot_id TEXT NOT NULL,
                    process TEXT NOT NULL, equipment_id TEXT NOT NULL,
                    salinity REAL, ph REAL, temperature REAL, acidity REAL,
                    weight_kg REAL, equipment_status TEXT NOT NULL, measured_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS kimchi_ccp_checks (
                    check_id INTEGER PRIMARY KEY, lot_id TEXT NOT NULL, ccp_name TEXT NOT NULL,
                    result TEXT NOT NULL, value REAL, unit TEXT, defect_type TEXT,
                    checked_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS kimchi_fermentation_predictions (
                    prediction_id INTEGER PRIMARY KEY, lot_id TEXT NOT NULL,
                    model_name TEXT NOT NULL, predicted_grade TEXT NOT NULL,
                    remaining_hours REAL, abnormal_risk REAL NOT NULL,
                    model_status TEXT NOT NULL, predicted_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS kimchi_inventory (
                    item_code TEXT PRIMARY KEY, item_name TEXT NOT NULL, category TEXT NOT NULL,
                    quantity_kg REAL NOT NULL, safety_stock_kg REAL NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS kimchi_shipments (
                    shipment_id TEXT PRIMARY KEY, lot_id TEXT NOT NULL, customer TEXT NOT NULL,
                    destination TEXT NOT NULL, quantity_kg REAL NOT NULL,
                    approval_status TEXT NOT NULL, shipped_at TEXT
                );
                CREATE TABLE IF NOT EXISTS kimchi_claims (
                    claim_id TEXT PRIMARY KEY, shipment_id TEXT NOT NULL, claim_type TEXT NOT NULL,
                    detail TEXT NOT NULL, received_at TEXT NOT NULL, status TEXT NOT NULL
                );
                """
            )
            if connection.execute("SELECT COUNT(*) FROM menus").fetchone()[0] == 0:
                self._seed(connection)
            self._seed_kimchi_demo(connection)

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

    @staticmethod
    def _seed_kimchi_demo(connection: sqlite3.Connection) -> None:
        """최신 임진강김치 에이전트의 가상 V1 데이터. 실제 운영 데이터로 사용하지 않는다."""
        if connection.execute("SELECT COUNT(*) FROM kimchi_lots").fetchone()[0] != 0:
            return
        connection.executemany("INSERT INTO kimchi_lots VALUES (?,?,?,?,?,?,?,?,?)", [
            ("RAW-260901-001", None, "원재료 입고", "배추", 11000, "공급처 A", "연천", "사용완료", "2026-09-01 07:20"),
            ("SORT-260901-001", "RAW-260901-001", "선별", "배추", 10500, None, None, "완료", "2026-09-01 09:00"),
            ("SALT-260901-001", "SORT-260901-001", "세척·절임", "절임배추", 10100, None, None, "완료", "2026-09-01 10:30"),
            ("MIX-260902-001", "SALT-260901-001", "양념·혼합", "율무 포기김치", 9900, None, None, "완료", "2026-09-02 08:40"),
            ("FERM-260902-001", "MIX-260902-001", "발효·숙성", "율무 포기김치", 9800, None, None, "숙성중", "2026-09-02 10:10"),
            ("PACK-260903-001", "FERM-260902-001", "포장", "율무 포기김치", 9600, None, None, "출하검토", "2026-09-03 09:00"),
            ("FERM-260903-002", None, "발효·숙성", "율무 총각김치", 4200, None, None, "이상검토", "2026-09-03 07:30"),
            ("RAW-260904-002", None, "원재료 입고", "무", 5200, "공급처 B", "파주", "검사완료", "2026-09-04 06:50"),
            ("SALT-260904-002", "RAW-260904-002", "세척·절임", "절임무", 4900, None, None, "진행중", "2026-09-04 08:20"),
            ("PACK-260904-002", "SALT-260904-002", "포장", "율무 총각김치", 4600, None, None, "대기", "2026-09-04 13:10"),
        ])
        connection.executemany("INSERT INTO kimchi_process_measurements VALUES (?,?,?,?,?,?,?,?,?,?,?)", [
            (1, "SALT-260901-001", "세척·절임", "SALTING-01", 2.4, 5.8, 12.2, None, 10100, "정상", "2026-09-01 16:30"),
            (2, "FERM-260902-001", "발효·숙성", "AGING-01", 2.1, 4.35, 4.2, 0.62, 9800, "정상", "2026-09-03 10:20"),
            (3, "PACK-260903-001", "포장", "PACK-01", None, None, 6.1, None, 9600, "정상", "2026-09-03 10:30"),
            (4, "FERM-260903-002", "발효·숙성", "AGING-02", 1.6, 3.72, 8.8, 0.91, 4200, "온도주의", "2026-09-03 10:25"),
        ])
        connection.executemany("INSERT INTO kimchi_ccp_checks VALUES (?,?,?,?,?,?,?,?)", [
            (1, "MIX-260902-001", "혼합·덤퍼 CCP", "적합", 9900, "kg", None, "2026-09-02 09:50"),
            (2, "PACK-260903-001", "금속검출 CCP", "적합", 0, "NG", None, "2026-09-03 10:40"),
            (3, "FERM-260903-002", "혼합·덤퍼 CCP", "주의", 1, "건", "배합 확인 필요", "2026-09-03 08:20"),
        ])
        connection.executemany("INSERT INTO kimchi_fermentation_predictions VALUES (?,?,?,?,?,?,?,?)", [
            (1, "FERM-260902-001", "RF+SVR+XGBoost+LSTM Ensemble", "A 예상", 6.5, 0.12, "시제품 데모", "2026-09-03 10:30"),
            (2, "FERM-260903-002", "RF+SVR+XGBoost+LSTM Ensemble", "C 위험", 14.0, 0.78, "시제품 데모", "2026-09-03 10:30"),
        ])
        connection.executemany("INSERT INTO kimchi_inventory VALUES (?,?,?,?,?,?)", [
            ("R001", "배추", "원재료", 14500, 10000, "2026-09-03 10:00"), ("R002", "율무", "원재료", 720, 800, "2026-09-03 10:00"),
            ("F001", "율무 포기김치", "완제품", 9600, 5000, "2026-09-03 10:30"), ("F002", "율무 총각김치", "완제품", 3800, 3000, "2026-09-03 10:30"),
        ])
        connection.executemany("INSERT INTO kimchi_shipments VALUES (?,?,?,?,?,?,?)", [
            ("SHP-260903-001", "PACK-260903-001", "울타리몰", "미국", 3200, "승인대기", None),
            ("SHP-260902-004", "PACK-260903-001", "국내 거래처 A", "대한민국", 1800, "승인", "2026-09-03 08:30"),
        ])
        connection.execute("INSERT INTO kimchi_claims VALUES (?,?,?,?,?,?)", ("CLM-260903-01", "SHP-260902-004", "숙성 편차", "도착 후 산미 편차 문의", "2026-09-03 09:20", "분석중"))

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

    def kimchi_readiness(self, product_name: str = "임진감김치") -> dict[str, Any]:
        with self._connect() as connection:
            product = connection.execute("SELECT * FROM kimchi_products WHERE product_name=?", (product_name,)).fetchone()
            formulation = None
            item_count = 0
            if product:
                formulation = connection.execute(
                    "SELECT * FROM kimchi_formulations WHERE product_code=? ORDER BY effective_date DESC, revision DESC LIMIT 1",
                    (product["product_code"],),
                ).fetchone()
                if formulation:
                    item_count = connection.execute("SELECT COUNT(*) FROM kimchi_formulation_items WHERE formulation_id=?", (formulation["formulation_id"],)).fetchone()[0]
        missing = []
        if not product:
            missing.extend(["제품 유형", "제품 코드"])
        elif not product["product_type"]:
            missing.append("제품 유형")
        if not formulation:
            missing.extend(["승인 배합표 버전", "기준 배치량", "중량 기준", "적용일", "근거 문서"])
        elif formulation["approval_status"] != "승인":
            missing.append("승인 상태의 배합표")
        if formulation and not item_count:
            missing.append("배합 원료 목록")
        return {"product_name": product_name, "ready": not missing, "status": "계산 가능" if not missing else "판정 보류", "missing": missing,
                "formulation": dict(formulation) if formulation else None, "data_scope": "임진감김치 전용 운영 데이터(합성값 없음)"}

    def kimchi_material_requirements(self, formulation_id: str, target_quantity: float, target_basis: str) -> dict[str, Any]:
        with self._connect() as connection:
            formulation = connection.execute(
                "SELECT f.*,p.product_name FROM kimchi_formulations f JOIN kimchi_products p ON p.product_code=f.product_code WHERE f.formulation_id=?",
                (formulation_id,),
            ).fetchone()
            if not formulation:
                raise ValueError("배합표를 찾을 수 없습니다.")
            items = self._rows(connection.execute(
                """SELECT i.*,COUNT(l.material_lot) AS inventory_lot_count,SUM(CASE WHEN l.quality_status='사용가능' THEN
                       CASE WHEN l.remaining_quantity-l.reserved_quantity-l.hold_quantity>0
                            THEN l.remaining_quantity-l.reserved_quantity-l.hold_quantity ELSE 0 END ELSE 0 END) AS available_quantity
                   FROM kimchi_formulation_items i LEFT JOIN kimchi_material_lots l ON l.material_code=i.material_code
                   WHERE i.formulation_id=? GROUP BY i.formulation_id,i.line_no,i.material_code,i.material_name,i.quantity,i.unit ORDER BY i.line_no""",
                (formulation_id,),
            ).fetchall())
        for item in items:
            if not item.pop("inventory_lot_count"):
                item["available_quantity"] = None
        return scale_formulation(dict(formulation), items, target_quantity, target_basis)

    def kimchi_lot_trace(self, production_lot: str) -> dict[str, Any]:
        with self._connect() as connection:
            lot = connection.execute(
                """SELECT l.*,p.product_name,f.revision,f.source_document FROM kimchi_production_lots l
                   JOIN kimchi_products p ON p.product_code=l.product_code
                   JOIN kimchi_formulations f ON f.formulation_id=l.formulation_id WHERE l.production_lot=?""", (production_lot,)).fetchone()
            inputs = self._rows(connection.execute("SELECT i.*,m.material_name,m.expiry_date,m.quality_status FROM kimchi_lot_inputs i JOIN kimchi_material_lots m ON m.material_lot=i.material_lot WHERE i.production_lot=? ORDER BY i.material_lot", (production_lot,)).fetchall())
            processes = self._rows(connection.execute("SELECT * FROM kimchi_process_records WHERE production_lot=? ORDER BY recorded_at,record_id", (production_lot,)).fetchall())
            packages = self._rows(connection.execute("SELECT * FROM kimchi_packaging_lots WHERE production_lot=? ORDER BY packaging_lot", (production_lot,)).fetchall())
            quality = self._rows(connection.execute("SELECT * FROM kimchi_quality_results WHERE production_lot=? ORDER BY checked_at,result_id", (production_lot,)).fetchall())
        if not lot:
            return {"production_lot": production_lot, "status": "미등록", "trace_complete": False, "missing": ["제조 LOT"]}
        missing = []
        if not inputs: missing.append("원료 LOT 연결")
        if not processes: missing.append("공정 실측 기록")
        if not packages: missing.append("포장 LOT 연결")
        if not quality: missing.append("품질 결과")
        return {"production_lot": dict(lot), "material_inputs": inputs, "process_records": processes,
                "packaging_lots": packages, "quality_results": quality, "trace_complete": not missing,
                "status": "추적 가능" if not missing else "판정 보류", "missing": missing}

    def kimchi_dashboard(self) -> dict[str, Any]:
        with self._connect() as con:
            packed = con.execute("SELECT COALESCE(SUM(quantity_kg),0) FROM kimchi_lots WHERE process='포장'").fetchone()[0]
            ccp = con.execute("SELECT COUNT(*) FROM kimchi_ccp_checks WHERE result!='적합'").fetchone()[0]
            risk = con.execute("SELECT COUNT(*) FROM kimchi_fermentation_predictions WHERE abnormal_risk>=0.5").fetchone()[0]
            shortage = con.execute("SELECT COUNT(*) FROM kimchi_inventory WHERE quantity_kg<safety_stock_kg").fetchone()[0]
            pending = con.execute("SELECT COUNT(*) FROM kimchi_shipments WHERE approval_status='승인대기'").fetchone()[0]
        return {"packed_kg": packed, "ccp_alerts": ccp, "fermentation_risks": risk, "stock_shortages": shortage, "shipment_pending": pending, "demo_data": True, "as_of": "2026-09-04 13:10"}

    def kimchi_lot_trace_latest(self, lot_id: str) -> list[dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute("""WITH RECURSIVE lineage AS (
                SELECT * FROM kimchi_lots WHERE lot_id=?
                UNION SELECT l.* FROM kimchi_lots l JOIN lineage x ON l.lot_id=x.parent_lot_id OR l.parent_lot_id=x.lot_id
            ) SELECT * FROM lineage ORDER BY created_at""", (lot_id,)).fetchall()
        return self._rows(rows)

    def kimchi_fermentation_status(self, lot_id: str | None) -> list[dict[str, Any]]:
        query = """SELECT l.lot_id,l.product_name,l.status,m.salinity,m.ph,m.temperature,m.acidity,
                   p.model_name,p.predicted_grade,p.remaining_hours,p.abnormal_risk,p.model_status,p.predicted_at
                   FROM kimchi_lots l LEFT JOIN kimchi_process_measurements m ON m.lot_id=l.lot_id
                   LEFT JOIN kimchi_fermentation_predictions p ON p.lot_id=l.lot_id WHERE l.process='발효·숙성'"""
        params: tuple[Any, ...] = ()
        if lot_id: query += " AND l.lot_id=?"; params = (lot_id,)
        with self._connect() as con: return self._rows(con.execute(query + " ORDER BY p.abnormal_risk DESC", params).fetchall())

    def kimchi_ccp_deviations(self, date: str | None) -> list[dict[str, Any]]:
        query = "SELECT * FROM kimchi_ccp_checks WHERE result!='적합'"; params: tuple[Any, ...] = ()
        if date: query += " AND checked_at LIKE ?"; params = (f"{date}%",)
        with self._connect() as con: return self._rows(con.execute(query + " ORDER BY checked_at DESC", params).fetchall())

    def kimchi_inventory_status(self, item: str | None, shortage_only: bool = False) -> list[dict[str, Any]]:
        query = "SELECT *,CASE WHEN quantity_kg<safety_stock_kg THEN '부족' ELSE '정상' END AS stock_status FROM kimchi_inventory WHERE 1=1"; params: list[Any] = []
        if item: query += " AND item_name LIKE ?"; params.append(f"%{item}%")
        if shortage_only: query += " AND quantity_kg<safety_stock_kg"
        with self._connect() as con: return self._rows(con.execute(query + " ORDER BY stock_status,item_name", params).fetchall())

    def kimchi_shipment_readiness(self, lot_id: str | None) -> list[dict[str, Any]]:
        query = "SELECT s.*,l.product_name,l.status AS lot_status FROM kimchi_shipments s JOIN kimchi_lots l ON l.lot_id=s.lot_id"; params: tuple[Any, ...] = ()
        if lot_id: query += " WHERE s.lot_id=?"; params = (lot_id,)
        with self._connect() as con: records = self._rows(con.execute(query + " ORDER BY s.shipment_id", params).fetchall())
        all_predictions = self.kimchi_fermentation_status(None)
        with self._connect() as con: checks = self._rows(con.execute("SELECT * FROM kimchi_ccp_checks").fetchall())
        for record in records:
            ids = {row["lot_id"] for row in self.kimchi_lot_trace_latest(record["lot_id"])}
            risks = [r["abnormal_risk"] for r in all_predictions if r["lot_id"] in ids and r["abnormal_risk"] is not None]
            linked = [r for r in checks if r["lot_id"] in ids]
            record.update({"abnormal_risk": max(risks) if risks else None, "ccp_alerts": sum(r["result"] != "적합" for r in linked), "ccp_records": len(linked), "evidence_status": "샘플 기록 조회·담당자 검토 필요" if linked and risks else "검사 또는 예측 미확인"})
        return records

    def kimchi_claim_trace(self, claim_id: str) -> dict[str, Any]:
        with self._connect() as con:
            claim = con.execute("SELECT c.*,s.lot_id,s.customer,s.destination,s.quantity_kg FROM kimchi_claims c JOIN kimchi_shipments s ON s.shipment_id=c.shipment_id WHERE c.claim_id=?", (claim_id,)).fetchone()
        if not claim: return {"claim": None, "lot_trace": []}
        record = dict(claim); return {"claim": record, "lot_trace": self.kimchi_lot_trace_latest(record["lot_id"])}

    def kimchi_process_measurements(self, lot_id: str | None) -> list[dict[str, Any]]:
        query = "SELECT * FROM kimchi_process_measurements WHERE 1=1"; params: tuple[Any, ...] = ()
        if lot_id: query += " AND lot_id=?"; params = (lot_id,)
        with self._connect() as con: return self._rows(con.execute(query + " ORDER BY measured_at DESC", params).fetchall())


# Backward-compatible import location used by the V2 integration tests and
# existing callers. The implementation remains in the dedicated adapter.
from .postgres import PostgresRepository  # noqa: E402  (after base class definition)
