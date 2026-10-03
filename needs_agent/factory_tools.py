from __future__ import annotations

import json
from typing import Any, Callable

from .data_hub import NeedsFoodRepository


def _nullable(description: str) -> dict[str, Any]:
    return {"type": ["string", "null"], "description": description}


class NeedsFoodToolRegistry:
    def __init__(self, repository: NeedsFoodRepository) -> None:
        self.repository = repository
        self.handlers: dict[str, Callable[..., Any]] = {
            "get_daily_briefing": repository.daily_briefing,
            "get_production_delays": repository.production_delays,
            "get_inventory_status": repository.inventory_status,
            "get_quality_summary": repository.quality_summary,
            "get_batch_trace": repository.batch_trace,
            "get_cooking_conditions": repository.cooking_conditions,
            "get_recipe_cost": repository.recipe_cost,
            "search_knowledge": repository.search_knowledge,
            "get_rules": repository.get_rules,
            "list_tables": repository.list_tables,
            "browse_table": repository.browse_table,
            "get_kimchi_readiness": repository.kimchi_readiness,
            "calculate_kimchi_materials": repository.kimchi_material_requirements,
            "get_kimchi_lot_trace": repository.kimchi_lot_trace,
            "get_lot_trace": repository.kimchi_lot_trace_latest,
            "get_fermentation_status": repository.kimchi_fermentation_status,
            "get_ccp_deviations": repository.kimchi_ccp_deviations,
            "get_kimchi_inventory_status": repository.kimchi_inventory_status,
            "get_shipment_readiness": repository.kimchi_shipment_readiness,
            "get_claim_trace": repository.kimchi_claim_trace,
            "get_process_measurements": repository.kimchi_process_measurements,
        }

    @property
    def definitions(self) -> list[dict[str, Any]]:
        specs = [
            ("search_knowledge", "절차·배합·검사·기준·승인 질문에는 로컬 지식문서를 검색한다.", {"query": {"type": "string", "description": "검색어"}, "limit": {"type": "integer", "minimum": 1, "maximum": 20}}),
            ("get_rules", "미승인 예시 규칙과 담당자·근거 문서를 조회한다. 실행하지 않는다.", {"query": _nullable("규칙 검색어, 전체이면 null")}),
            ("list_tables", "허용된 DB 테이블 이름과 행 수를 조회한다.", {}),
            ("browse_table", "허용된 DB 테이블을 읽기 전용 조회한다.", {"table_name": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 100}, "offset": {"type": "integer", "minimum": 0}}),
            ("get_daily_briefing", "오늘 생산·출하·지연·재고·품질 현황을 요약한다.", {"date": _nullable("조회일 YYYY-MM-DD, 오늘 데모는 null")}),
            ("get_production_delays", "납기 기준으로 지연 또는 중단된 배치(솥)를 조회한다.", {"date": _nullable("생산일 YYYY-MM-DD, 오늘이면 null")}),
            ("get_inventory_status", "원료 재고와 안전재고 부족 여부를 조회한다.", {"item": _nullable("원료명, 전체이면 null"), "shortage_only": {"type": "boolean", "description": "부족 품목만 조회할지 여부"}}),
            ("get_quality_summary", "영양사 검식과 외부기관 검사 결과를 구분해 조회한다.", {"date": _nullable("검사일 YYYY-MM-DD, 전체이면 null"), "menu_name": _nullable("메뉴명, 전체이면 null")}),
            ("get_batch_trace", "배치(솥)의 작업실적, 조리조건, 검식결과를 조회한다.", {"batch_id": {"type": "string", "description": "정확한 배치 ID"}}),
            ("get_cooking_conditions", "교반기의 온도·속도·압력·모터속도와 배치 상태를 조회한다.", {"menu_name": _nullable("메뉴명, 전체이면 null"), "date": _nullable("생산일 YYYY-MM-DD, 전체이면 null")}),
            ("get_recipe_cost", "Excel 이관을 가정한 메뉴별 재료 사용량과 식당 원가를 조회한다.", {"menu_name": _nullable("메뉴명, 전체이면 null")}),
            ("get_kimchi_readiness", "임진감김치 전용 승인 배합과 계산 준비상태를 확인한다. 급식 데모를 대신 사용하지 않는다.", {"product_name": {"type": "string", "description": "정확한 제품명, 기본 임진감김치"}}),
            ("calculate_kimchi_materials", "승인된 임진감김치 배합을 동일 중량 기준의 목표량으로 환산하고 확인된 사용가능 재고와 부족량을 계산한다.", {"formulation_id": {"type": "string", "description": "승인 배합표 ID"}, "target_quantity": {"type": "number", "exclusiveMinimum": 0, "description": "목표 생산량 kg"}, "target_basis": {"type": "string", "description": "원물 투입량/절임·탈수 후 중량/완제품량 등 승인 배합과 같은 중량 기준"}}),
            ("get_kimchi_lot_trace", "임진감김치 원료 LOT에서 제조 LOT, 포장 LOT, 품질 결과와 출고 연결을 조회한다.", {"production_lot": {"type": "string", "description": "정확한 제조 LOT"}}),
            ("get_lot_trace", "임진감김치 최신 LOT 계보를 원재료부터 포장까지 읽기 전용으로 조회한다.", {"lot_id": {"type": "string", "description": "정확한 LOT ID"}}),
            ("get_fermentation_status", "발효 LOT의 염도·pH·온도·산도와 시제품 예측을 조회한다. 예측을 품질판정으로 확정하지 않는다.", {"lot_id": _nullable("발효 LOT ID, 전체이면 null")}),
            ("get_ccp_deviations", "CCP 주의·부적합 이력을 조회한다. 격리·폐기·출하를 실행하지 않는다.", {"date": _nullable("조회일 YYYY-MM-DD, 전체이면 null")}),
            ("get_kimchi_inventory_status", "임진감김치 원료·완제품 재고와 안전재고 부족을 조회한다.", {"item": _nullable("품목명, 전체이면 null"), "shortage_only": {"type": "boolean", "description": "부족 품목만 조회할지"}}),
            ("get_shipment_readiness", "포장 LOT 출하 검토에 필요한 승인상태·발효위험·CCP 기록을 조회한다.", {"lot_id": _nullable("포장 LOT ID, 전체이면 null")}),
            ("get_claim_trace", "클레임에서 출하 LOT를 원재료·절임·발효까지 역추적한다.", {"claim_id": {"type": "string", "description": "정확한 클레임 ID"}}),
            ("get_process_measurements", "LOT별 염도·pH·온도·산도·중량과 설비상태를 조회한다.", {"lot_id": _nullable("LOT ID, 전체이면 null")}),
        ]
        return [
            {"type": "function", "name": name, "description": description, "strict": True,
             "parameters": {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}}
            for name, description, properties in specs
        ]

    def execute(self, name: str, arguments: str | dict[str, Any]) -> str:
        if name not in self.handlers:
            return json.dumps({"error": f"허용되지 않은 도구: {name}"}, ensure_ascii=False)
        try:
            values = json.loads(arguments) if isinstance(arguments, str) else arguments
            if not isinstance(values, dict):
                raise ValueError("도구 인자는 객체여야 합니다.")
            rows = self.handlers[name](**values)
            kimchi = name.startswith("get_") and (name in {"get_kimchi_readiness", "get_kimchi_lot_trace", "get_lot_trace", "get_fermentation_status", "get_ccp_deviations", "get_kimchi_inventory_status", "get_shipment_readiness", "get_claim_trace", "get_process_measurements"} or name == "calculate_kimchi_materials")
            return json.dumps({"status": "ok", "demo_data": not kimchi,
                               "source": "니즈푸드 임진감김치 운영 데이터" if kimchi else "니즈푸드 MES/Data Hub · 데모",
                               "tool": name, "data": rows, "result": rows}, ensure_ascii=False, default=str)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return json.dumps({"error": str(exc), "tool": name}, ensure_ascii=False)
        except Exception:
            return json.dumps({"status": "error", "error": "데이터 조회에 실패했습니다. 연결 상태를 확인하세요.", "tool": name}, ensure_ascii=False)
