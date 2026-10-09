"""니즈푸드 V2 facade: 최신 제조 Cockpit UX/API 계약만 참조하고 급식 데이터를 사용한다."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from needs_agent import ManufacturingAgent, NeedsFoodRepository, NeedsFoodToolRegistry
QUESTION_GROUPS = {
    "생산·품질": [
        "2026-09-03 생산 현황과 진척률을 알려줘",
        "2026-09-03 지연된 생산 배치를 알려줘",
        "B-20260903-M002-02 배치의 조리 측정값을 확인해줘",
        "B-20260903-M001-01 배치의 품질·검식 결과를 확인해줘",
        "안전재고 미만 원료와 부족량을 알려줘",
        "닭고기 원료 재고와 사용기한을 확인해줘",
        "2026-09-03 외부기관 검사 상태를 알려줘",
        "출하 대기 중인 메뉴와 수량을 알려줘",
        "오늘 들어온 원료와 입고 수량·현재 재고를 알려줘",
        "오늘 출하계획과 실제 출하량의 차이를 알려줘",
    ],
    "문서·규칙": [
        "니즈푸드 제조 지식문서에서 원료 입고 절차를 찾아줘",
        "생산 지연 시 담당자 확인 규칙은 뭐야?",
        "검식 주의 결과를 전체 배치 합격으로 볼 수 있어?",
        "외부기관 검사 대기 시 확인할 사항은?",
        "출하 전 품질 확인 절차를 알려줘",
        "원료 재고 부족 규칙과 담당자는?",
        "배치 LOT 추적에 필요한 기록은?",
        "조리조건과 품질검식 결과를 함께 확인하는 방법은?",
        "니즈푸드 승인 배합표가 없을 때 어떻게 처리해?",
        "등록 문서와 데모 데이터의 차이를 알려줘",
    ],
}

class NeedsFoodV2Repository:
    TABLES = {"menus":"메뉴 계획", "production_batches":"생산 배치", "cooking_readings":"조리 측정", "quality_checks":"품질·검식", "inventory":"원료 재고", "shipments":"출하", "equipment_events":"설비 이벤트", "rules":"확인 규칙", "knowledge_documents":"지식 문서"}
    def __init__(self, database_path: str | Path): self.inner = NeedsFoodRepository(database_path)
    def __getattr__(self, name: str): return getattr(self.inner, name)
    def _connect(self): return self.inner._connect()
    def dashboard(self):
        k = self.inner.dashboard()
        return {"planned_meals": k["planned_meals"], "actual_meals": k["actual_meals"], "completion_rate": k["completion_rate"], "delayed_batches": k["delayed_batches"], "quality_alerts": k["quality_alerts"], "stock_shortages": k["stock_shortages"], "demo_data": True, "as_of": "2026-09-03"}
    def all_lots(self):
        with self._connect() as con:
            rows = self.inner._rows(con.execute("""SELECT b.batch_id AS lot_id,NULL AS parent_lot_id,'급식 생산' AS process,m.menu_name AS product_name,
                       b.actual_qty AS quantity,'식' AS unit,NULL AS quantity_kg,NULL AS supplier,NULL AS origin,b.status,b.started_at AS created_at
                       FROM production_batches b JOIN menus m ON m.menu_code=b.menu_code ORDER BY b.started_at DESC""").fetchall())
        return rows
    def lot_trace(self, lot_id):
        with self._connect() as con:
            row = con.execute("""SELECT b.batch_id AS lot_id,NULL AS parent_lot_id,'급식 생산' AS process,m.menu_name AS product_name,
                       b.actual_qty AS quantity,'식' AS unit,NULL AS quantity_kg,b.status,b.started_at AS created_at,b.planned_qty,m.due_at,b.kettle_no
                       FROM production_batches b JOIN menus m ON m.menu_code=b.menu_code WHERE b.batch_id=?""", (lot_id,)).fetchone()
        return [dict(row)] if row else []
    def fermentation_status(self, lot_id):
        rows = self.process_measurements(lot_id)
        return [{"lot_id": r["lot_id"], "product_name": r["product_name"], "status": r["equipment_status"], "temperature": r["temperature"], "ph": None, "salinity": None, "acidity": None, "abnormal_risk": None, "remaining_hours": None, "predicted_at": r["recorded_at"]} for r in rows]
    def ccp_deviations(self, date):
        rows = self.inner.quality_summary(date, None)
        return [{"lot_id": r["batch_id"], "ccp_name": r["check_type"], "result": r["result"], "value": None, "unit": None, "defect_type": r["issue"], "checked_at": r["checked_at"]} for r in rows if r["result"] not in {"적합", "정상", "합격"}]
    def inventory_status(self, item, shortage_only):
        rows = self.inner.inventory_status(item, shortage_only)
        return [{"item_code": r["material_code"], "item_name": r["material_name"], "category": "원료",
                 "quantity": r["quantity"], "unit": r["unit"], "safety_stock": r["safety_stock"],
                 "quantity_kg": r["quantity"] if r["unit"] == "kg" else None,
                 "safety_stock_kg": r["safety_stock"] if r["unit"] == "kg" else None,
                 "updated_at": r["updated_at"], "stock_status": r["status"]} for r in rows]
    def shipment_readiness(self, lot_id):
        query = """SELECT s.shipment_id,s.menu_code AS lot_id,s.planned_qty,s.shipped_qty,s.due_at,s.shipped_at,s.status AS approval_status,
                   m.menu_name AS product_name,'식' AS unit FROM shipments s JOIN menus m ON m.menu_code=s.menu_code"""
        params = ()
        if lot_id:
            query += " WHERE s.shipment_id=?"; params = (lot_id,)
        with self._connect() as con: rows = self.inner._rows(con.execute(query + " ORDER BY s.shipment_id", params).fetchall())
        return [{**r, "lot_status": r["approval_status"], "abnormal_risk": None, "ccp_alerts": 0, "ccp_records": 0, "evidence_status": "급식 출하 데모 기록"} for r in rows]
    def claim_trace(self, claim_id): return {"claim": None, "lot_trace": []}
    def process_measurements(self, lot_id):
        rows = self.inner.cooking_conditions(None, None)
        if lot_id: rows = [r for r in rows if r["batch_id"] == lot_id]
        return [{"lot_id": r["batch_id"], "process": "조리", "equipment_id": r["equipment_id"], "temperature": r["temperature"], "salinity": None, "ph": None, "acidity": None, "weight_kg": None, "equipment_status": r["status"], "recorded_at": r["recorded_at"], "product_name": r["menu_name"]} for r in rows]
    def knowledge_documents(self):
        rows = self.inner.browse_table("knowledge_documents", 100, 0)["rows"]
        return [{**row, "content": row.get("body", row.get("content", ""))} for row in rows]
    def table_inventory(self):
        return [{"table": name, "label": label, "exists": True, "count": self.inner.browse_table(name, 1, 0)["total"]} for name, label in self.TABLES.items()]
    def table_records(self, table, limit=50, offset=0):
        if table not in self.TABLES: raise ValueError("조회할 수 없는 테이블입니다.")
        return self.inner.browse_table(table, limit, offset)["rows"]

class NeedsFoodV2ToolRegistry(NeedsFoodToolRegistry):
    # These legacy tool names are mapped to food-service records in V2.
    FOOD_SERVICE_DESCRIPTIONS = {
        "get_lot_trace": "급식 생산 배치의 실적을 조회한다. 수량 단위는 식이며 전체 원료 LOT 계보는 제공하지 않는다.",
        "get_fermentation_status": "급식 조리 측정 상태를 조회한다. 발효 예측이 아니며 pH·염도·예측값은 미확인이다.",
        "get_ccp_deviations": "급식 품질·검식의 주의 결과를 조회한다. 승인된 CCP 판정을 대신하지 않는다.",
        "get_inventory_status": "급식 원료 재고와 안전재고 부족을 원본 unit 단위로 조회한다. 입고량이나 사용가능 재고를 확정하지 않는다.",
        "get_shipment_readiness": "급식 출하 계획·실적을 식 단위로 조회한다. 출하 승인을 실행하지 않는다.",
        "get_claim_trace": "클레임 연결 여부를 확인한다. 현재 급식 어댑터에 연결된 클레임 계보는 없다.",
        "get_process_measurements": "급식 생산 배치의 조리 온도와 설비 상태를 조회한다. 발효 측정값은 제공하지 않는다.",
    }

    def __init__(self, repository: NeedsFoodV2Repository):
        super().__init__(repository.inner); self.repository = repository
        self.handlers.update({"get_lot_trace": repository.lot_trace, "get_fermentation_status": repository.fermentation_status, "get_ccp_deviations": repository.ccp_deviations, "get_inventory_status": repository.inventory_status, "get_shipment_readiness": repository.shipment_readiness, "get_claim_trace": repository.claim_trace, "get_process_measurements": repository.process_measurements})

    @property
    def definitions(self):
        return [{**definition, "description": self.FOOD_SERVICE_DESCRIPTIONS.get(definition["name"], definition["description"])}
                for definition in super().definitions]

    def execute(self, name, arguments):
        payload = json.loads(super().execute(name, arguments))
        if payload.get("status") == "ok" and name in self.FOOD_SERVICE_DESCRIPTIONS:
            payload.update(demo_data=True, source="니즈푸드 급식 MES/Data Hub · 샘플",
                           as_of="2026-09-03", retrieved_at=datetime.now(timezone.utc).isoformat())
        return json.dumps(payload, ensure_ascii=False, default=str)

def lot_snapshot(repository: NeedsFoodV2Repository, lot_id: str) -> dict[str, Any]:
    lot = next((row for row in repository.all_lots() if row["lot_id"] == lot_id), {})
    trace = repository.lot_trace(lot_id); ids = {row["lot_id"] for row in trace}
    return {"lot": lot, "trace": trace, "fermentation": [r for r in repository.fermentation_status(None) if r.get("lot_id") in ids], "ccp": [r for r in repository.ccp_deviations(None) if r.get("lot_id") in ids], "shipments": repository.shipment_readiness(lot_id) if lot_id.startswith("PACK-") else []}

class PostgresRepository(NeedsFoodV2Repository): pass
def create_repository(database_path: str, database_url: str | None = None): return NeedsFoodV2Repository(database_path)
