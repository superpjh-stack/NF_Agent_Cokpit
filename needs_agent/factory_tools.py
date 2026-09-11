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
            return json.dumps({"status": "ok", "demo_data": True, "source": "니즈푸드 MES/Data Hub · 데모", "tool": name, "data": rows}, ensure_ascii=False, default=str)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return json.dumps({"error": str(exc), "tool": name}, ensure_ascii=False)
        except Exception:
            return json.dumps({"status": "error", "error": "데이터 조회에 실패했습니다. 연결 상태를 확인하세요.", "tool": name}, ensure_ascii=False)
