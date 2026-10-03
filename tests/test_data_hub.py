import json

from needs_agent import NeedsFoodRepository, NeedsFoodToolRegistry


def test_dashboard_matches_daily_plan(tmp_path):
    repo = NeedsFoodRepository(tmp_path / "needs.db")
    kpi = repo.dashboard("2026-09-03")
    assert kpi["planned_meals"] == 6800
    assert kpi["delayed_batches"] == 1
    assert kpi["stock_shortages"] == 1


def test_batch_trace_keeps_cooking_and_quality_separate(tmp_path):
    repo = NeedsFoodRepository(tmp_path / "needs.db")
    trace = repo.batch_trace("B-20260903-M001-01")
    assert trace["batch"]["kettle_no"] == "KETTLE-01"
    assert trace["cooking_readings"][0]["temperature"] == 92.4
    assert trace["quality_checks"][0]["check_type"] == "영양사 검식"


def test_quality_distinguishes_external_test(tmp_path):
    repo = NeedsFoodRepository(tmp_path / "needs.db")
    checks = repo.quality_summary("2026-09-03", None)
    assert {row["check_type"] for row in checks} == {"영양사 검식", "외부기관 검사"}


def test_tool_registry_blocks_unknown_tools(tmp_path):
    registry = NeedsFoodToolRegistry(NeedsFoodRepository(tmp_path / "needs.db"))
    result = json.loads(registry.execute("get_inventory_status", '{"item":"닭고기","shortage_only":true}'))
    denied = json.loads(registry.execute("change_recipe", "{}"))
    assert result["data"][0]["status"] == "부족"
    assert "error" in denied


def test_kimchi_is_not_filled_from_catering_demo(tmp_path):
    repo = NeedsFoodRepository(tmp_path / "needs.db")
    readiness = repo.kimchi_readiness()
    assert readiness["status"] == "판정 보류"
    assert "승인 배합표 버전" in readiness["missing"]
    assert repo.browse_table("kimchi_formulations")["total"] == 0


def test_approved_kimchi_formulation_scales_and_marks_unknown_inventory(tmp_path):
    repo = NeedsFoodRepository(tmp_path / "needs.db")
    with repo._connect() as con:
        con.execute("INSERT INTO kimchi_products VALUES (?,?,?,?)", ("K001", "임진감김치", "배추김치", "사용"))
        con.execute("INSERT INTO kimchi_formulations VALUES (?,?,?,?,?,?,?,?)", ("F001", "K001", "R1", "2026-09-20", "완제품량", 100, "승인", "승인배합표-R1"))
        con.executemany("INSERT INTO kimchi_formulation_items VALUES (?,?,?,?,?,?)", [
            ("F001", 1, "M001", "절임배추", 80, "kg"),
            ("F001", 2, "M002", "양념", 20, "kg"),
        ])
        con.execute("INSERT INTO kimchi_material_lots VALUES (?,?,?,?,?,?,?,?,?,?,?)", ("ML-1", "M001", "절임배추", 200, 170, 20, 10, "kg", "2026-10-01", "사용가능", "2026-09-25 09:00"))
    result = repo.kimchi_material_requirements("F001", 200, "완제품량")
    assert result["scale_factor"] == 2.0
    assert result["items"][0]["required_quantity_kg"] == 160.0
    assert result["items"][0]["available_quantity_kg"] == 140.0
    assert result["items"][0]["shortage_quantity_kg"] == 20.0
    assert result["items"][1]["inventory_status"] == "미확인"


def test_kimchi_calculation_rejects_unapproved_or_mismatched_basis(tmp_path):
    repo = NeedsFoodRepository(tmp_path / "needs.db")
    with repo._connect() as con:
        con.execute("INSERT INTO kimchi_products VALUES (?,?,?,?)", ("K001", "임진감김치", "배추김치", "사용"))
        con.execute("INSERT INTO kimchi_formulations VALUES (?,?,?,?,?,?,?,?)", ("F001", "K001", "R1", "2026-09-20", "완제품량", 100, "검토", "검토본"))
        con.execute("INSERT INTO kimchi_formulation_items VALUES (?,?,?,?,?,?)", ("F001", 1, "M001", "절임배추", 100, "kg"))
    import pytest
    with pytest.raises(ValueError, match="승인 상태"):
        repo.kimchi_material_requirements("F001", 200, "완제품량")
    with repo._connect() as con:
        con.execute("UPDATE kimchi_formulations SET approval_status='승인' WHERE formulation_id='F001'")
    with pytest.raises(ValueError, match="중량 기준"):
        repo.kimchi_material_requirements("F001", 200, "원물 투입량")


def test_kimchi_lot_trace_does_not_claim_missing_links(tmp_path):
    repo = NeedsFoodRepository(tmp_path / "needs.db")
    missing = repo.kimchi_lot_trace("KLOT-NOT-FOUND")
    assert missing["trace_complete"] is False
    assert missing["status"] == "미등록"
