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
