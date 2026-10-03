"""임진감김치 승인 배합의 보수적인 환산 로직."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


def _positive_decimal(value: Any, label: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{label}은 숫자여야 합니다.") from exc
    if not number.is_finite() or number <= 0:
        raise ValueError(f"{label}은 0보다 커야 합니다.")
    return number


def scale_formulation(
    formulation: dict[str, Any],
    items: list[dict[str, Any]],
    target_quantity: Any,
    target_basis: str,
) -> dict[str, Any]:
    """승인 배합을 동일 중량 기준으로 환산한다. 수율은 여기서 추정하지 않는다."""
    if formulation.get("approval_status") != "승인":
        raise ValueError("승인 상태의 배합표만 환산할 수 있습니다.")
    if not formulation.get("revision") or not formulation.get("effective_date"):
        raise ValueError("배합표 개정번호와 적용일이 필요합니다.")
    basis = str(formulation.get("weight_basis") or "").strip()
    if not basis or target_basis.strip() != basis:
        raise ValueError(f"목표량 중량 기준은 승인 배합의 '{basis or '미등록'}'와 같아야 합니다.")
    base = _positive_decimal(formulation.get("batch_quantity"), "기준 배치량")
    target = _positive_decimal(target_quantity, "목표 생산량")
    if not items:
        raise ValueError("승인 배합 원료가 등록되지 않았습니다.")
    factor = target / base
    rows = []
    total = Decimal("0")
    for item in items:
        if item.get("unit") != "kg":
            raise ValueError(f"{item.get('material_name', '원료')} 단위가 kg이 아닙니다. 확인된 환산계수가 필요합니다.")
        standard = _positive_decimal(item.get("quantity"), f"{item.get('material_name', '원료')} 기준량")
        required = (standard * factor).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        available_value = item.get("available_quantity")
        available = Decimal(str(available_value)) if available_value is not None else None
        shortage = max(required - available, Decimal("0")) if available is not None else None
        rows.append({
            "material_code": item.get("material_code"),
            "material_name": item.get("material_name"),
            "standard_quantity_kg": float(standard),
            "required_quantity_kg": float(required),
            "available_quantity_kg": float(available) if available is not None else None,
            "shortage_quantity_kg": float(shortage) if shortage is not None else None,
            "inventory_status": "미확인" if available is None else ("부족" if shortage else "충분"),
        })
        total += required
    return {
        "product_name": formulation.get("product_name"),
        "formulation_id": formulation.get("formulation_id"),
        "revision": formulation.get("revision"),
        "effective_date": formulation.get("effective_date"),
        "weight_basis": basis,
        "base_quantity_kg": float(base),
        "target_quantity_kg": float(target),
        "scale_factor": float(factor),
        "rounding": "원료별 0.001 kg 반올림(ROUND_HALF_UP)",
        "required_total_kg": float(total),
        "rounding_difference_kg": float(total - target),
        "yield_applied": False,
        "items": rows,
    }
