from __future__ import annotations

from datetime import datetime
from typing import Any


QUESTION_GROUPS = {
    "지식문서": ["임진감김치 제조에 필요한 승인 자료는?", "배합표를 생산량에 맞춰 환산하는 절차는?", "원료 입고 확인 절차는?", "레시피 변경 승인 절차는?", "김치 LOT 추적에 필요한 기록은?", "내부 검식과 외부기관 검사는 어떻게 다른가?", "조리 편차를 확인하는 기준은?", "원료 대체 검토 시 확인사항은?", "출하 전 확인 절차는?", "SQLite 데이터를 이관하는 절차는?"],
    "공정 DB": ["2026-09-03 데모 생산 현황을 알려줘", "2026-09-03 지연 배치를 알려줘", "닭고기 데모 재고를 확인해줘", "안전재고 미만 원료를 알려줘", "B-20260903-M001-01을 추적해줘", "B-20260903-M002-02의 조리값을 알려줘", "2026-09-03 외부기관 검사 상태는?", "닭갈비 세트의 식당 원가는?", "조회 가능한 DB 테이블과 행 수는?", "출하 테이블의 대기 건을 보여줘"],
    "확인 규칙": ["안전재고 부족 규칙과 담당자는?", "생산 지연 시 확인 규칙은?", "검식 주의 규칙을 알려줘", "외부기관 검사 대기 규칙은?", "출하 대기 시 확인사항은?", "미해결 설비 이벤트 규칙은?", "김치 배합 미등록 시 어떻게 처리해?", "규칙의 승인 상태와 출처는?", "규칙별 담당자를 보여줘", "원료 부족 규칙의 근거 문서를 찾아줘"],
}

WELCOME_MESSAGE = {"role": "assistant", "content": "니즈푸드 제조 현황을 근거와 함께 확인합니다.\n현재 데이터는 2026-09-03 기준 데모입니다. 임진감김치 승인 배합표는 미등록입니다.\n문서·공정 DB·확인 규칙을 선택하거나 질문을 입력하세요.", "sources": [], "evidence": [], "data_tools": [], "created_at": "시작"}


def timestamp() -> str:
    return datetime.now().strftime("%H:%M")


def user_question_history(messages: list[dict[str, Any]], limit: int = 8) -> list[dict[str, str]]:
    return [{"content": str(m.get("content", "")), "created_at": str(m.get("created_at", ""))} for m in reversed(messages) if m.get("role") == "user"][:limit]


def batch_snapshot(repository: Any, batch_id: str) -> dict[str, Any]:
    trace = repository.batch_trace(batch_id)
    batch = trace.get("batch") or {}
    shortages = repository.inventory_status(None, True)
    quality = trace.get("quality_checks") or []
    return {"batch": batch, "readings": trace.get("cooking_readings") or [], "quality": quality, "shortages": shortages}


def risk_label(snapshot: dict[str, Any]) -> tuple[str, str]:
    batch = snapshot["batch"]
    score = (2 if batch.get("status") == "지연" else 0) + len(snapshot["shortages"]) + len([r for r in snapshot["quality"] if r.get("result") not in {"합격", "정상", "적합"}])
    return ("높음", "🔴") if score >= 3 else (("주의", "🟠") if score else ("안정", "🟢"))
