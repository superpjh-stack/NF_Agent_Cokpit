"""V2 food-service records retain their provenance and original units."""
import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from needs_agent.service import AgentAnswer
from v2.api import create_app
from v2.compat import NeedsFoodV2Repository, NeedsFoodV2ToolRegistry


@pytest.fixture
def repo(tmp_path):
    return NeedsFoodV2Repository(tmp_path / 'provenance.db')


@pytest.fixture
def client(repo, monkeypatch):
    for name in ('OPENAI_API_KEY', 'COCKPIT_ACCESS_TOKEN', 'V2_REQUIRE_LOGIN'):
        monkeypatch.delenv(name, raising=False)
    with TestClient(create_app(repo)) as client:
        yield client


@pytest.mark.parametrize('name,arguments', [
    ('get_lot_trace', {'lot_id': 'B-20260903-M001-01'}),
    ('get_fermentation_status', {'lot_id': None}),
    ('get_ccp_deviations', {'date': None}),
    ('get_inventory_status', {'item': None, 'shortage_only': False}),
    ('get_shipment_readiness', {'lot_id': None}),
    ('get_claim_trace', {'claim_id': 'missing'}),
    ('get_process_measurements', {'lot_id': None}),
])
def test_remapped_tools_report_sample_provenance(repo, name, arguments):
    result = json.loads(NeedsFoodV2ToolRegistry(repo).execute(name, arguments))
    assert result['status'] == 'ok'
    assert result['demo_data'] is True
    assert result['source'] == '니즈푸드 급식 MES/Data Hub · 샘플'
    assert result['as_of'] == '2026-09-03'
    assert datetime.fromisoformat(result['retrieved_at']).tzinfo is not None
    assert result['data'] == result['result']


def test_failed_tools_do_not_gain_success_metadata(repo):
    registry = NeedsFoodV2ToolRegistry(repo)
    for name, args in [('unknown', {}), ('get_lot_trace', {'unexpected': 1})]:
        result = json.loads(registry.execute(name, args))
        assert 'error' in result
        assert 'source' not in result


def test_production_counts_are_meals_not_kilograms(client):
    workspace = client.get('/api/workspace').json()
    assert workspace['lots']
    for lot in workspace['lots']:
        assert lot['unit'] == '식'
        assert lot['quantity_kg'] is None
        detail = client.get('/api/lots/' + lot['lot_id']).json()
        assert detail['trace'][0]['quantity'] == lot['quantity']
        assert detail['trace'][0]['unit'] == '식'
    assert all(row['unit'] == '식' for row in workspace['shipments'])


@pytest.mark.parametrize('unit', ['kg', '개', 'L'])
def test_inventory_and_answers_keep_original_units(repo, client, unit):
    with repo._connect() as connection:
        connection.execute('UPDATE inventory SET quantity=12,safety_stock=20,unit=? WHERE material_name=?', (unit, '닭고기'))
    row = repo.inventory_status('닭고기', True)[0]
    assert (row['quantity'], row['safety_stock'], row['unit']) == (12, 20, unit)
    assert row['quantity_kg'] == (12 if unit == 'kg' else None)
    assert row['safety_stock_kg'] == (20 if unit == 'kg' else None)
    answer = client.post('/api/chat', json={'question': '니즈, 닭고기 재고 부족량'}).json()
    assert f'재고 12{unit}' in answer['text']
    assert f'부족 8{unit}' in answer['text']
    inbound = client.post('/api/chat', json={'question': '니즈, 오늘 입고량을 알려줘'}).json()
    assert f'닭고기 12{unit}' in inbound['text']


def test_ai_answer_using_sample_records_remains_sample(client, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    monkeypatch.setenv('COCKPIT_ACCESS_TOKEN', 'test-code')
    def ask(agent, *args, **kwargs):
        result = json.loads(agent.factory_tools.execute('get_lot_trace', {'lot_id': 'B-20260903-M001-01'}))
        assert result['demo_data'] is True
        return AgentAnswer(text='샘플 생산량입니다.', sources=[], evidence=[], response_id=None, data_tools=['get_lot_trace'])
    monkeypatch.setattr('v2.api.ManufacturingAgent.ask', ask)
    response = client.post('/api/chat', headers={'Authorization': 'Bearer test-code'},
                           json={'question': '니즈, 배치 생산량을 알려줘', 'mode': 'ai'})
    assert response.status_code == 200
    assert response.json()['mode'] == 'ai'
    assert response.json()['demo_data'] is True
    assert any(row.get('unit') == '식' for row in response.json()['records'])
