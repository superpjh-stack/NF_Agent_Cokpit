from types import SimpleNamespace

import pytest

from needs_agent import ManufacturingAgent, NeedsFoodRepository, NeedsFoodToolRegistry


class FakeResponses:
    def __init__(self):
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if len(self.requests) == 1:
            call = SimpleNamespace(type="function_call", name="get_production_delays", arguments='{"date":"2026-09-03"}', call_id="call_1")
            return SimpleNamespace(id="resp_1", output_text="", output=[call])
        return SimpleNamespace(id="resp_2", output_text="KETTLE-04 배치가 지연 상태입니다.", output=[])


class FakeVectorStores:
    def create(self, name):
        return SimpleNamespace(id="vs_1")


class FakeClient:
    def __init__(self):
        self.responses = FakeResponses()
        self.vector_stores = FakeVectorStores()


def test_agent_executes_needs_food_tool(tmp_path):
    registry = NeedsFoodToolRegistry(NeedsFoodRepository(tmp_path / "needs.db"))
    agent = ManufacturingAgent(FakeClient(), factory_tools=registry)
    answer = agent.ask("오늘 지연된 솥은?")
    assert answer.data_tools == ["get_production_delays"]
    assert "KETTLE-04" in answer.text


def test_agent_rejects_blank_question(tmp_path):
    registry = NeedsFoodToolRegistry(NeedsFoodRepository(tmp_path / "needs.db"))
    with pytest.raises(ValueError):
        ManufacturingAgent(FakeClient(), factory_tools=registry).ask("  ")
