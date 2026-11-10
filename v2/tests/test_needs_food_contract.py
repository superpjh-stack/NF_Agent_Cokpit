import json

import httpx
from fastapi.testclient import TestClient

from needs_agent import NeedsFoodRepository
from v2.api import create_app
from v2.compat import NeedsFoodV2Repository


def test_needs_food_workspace_and_demo_question(tmp_path, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('COCKPIT_ACCESS_TOKEN', raising=False)
    with TestClient(create_app(NeedsFoodV2Repository(tmp_path / 'needs.db'))) as client:
        workspace = client.get('/api/workspace')
        assert workspace.status_code == 200
        body = workspace.json()
        assert body['meta']['company'] == '니즈푸드 제조 AI'
        assert body['kpi']['planned_meals'] == 6800
        assert body['lots'][0]['lot_id'].startswith('B-')
        assert len(client.get('/api/documents').json()) == 10

        answer = client.post('/api/chat', json={
            'question': '니즈, 생산 현황과 진척률을 알려줘',
        }).json()
        assert answer['mode'] == 'demo'
        assert '6,800식' in answer['text']
        assert 'get_daily_briefing' in answer['data_tools']


def test_create_app_normalizes_legacy_repository_instances(tmp_path):
    with TestClient(create_app(NeedsFoodRepository(tmp_path / 'legacy.db'))) as client:
        response = client.get('/api/workspace')
        assert response.status_code == 200
        assert response.json()['meta']['company'] == '니즈푸드 제조 AI'


def test_unaddressed_question_is_not_sent_to_agent(tmp_path):
    with TestClient(create_app(NeedsFoodV2Repository(tmp_path / 'needs.db'))) as client:
        answer = client.post('/api/chat', json={'question': '생산 현황을 알려줘'}).json()
        assert answer['ignored'] is True
        assert answer['records'] == []


def test_realtime_uses_needs_food_read_only_tools(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-test-realtime')
    monkeypatch.setenv('COCKPIT_ACCESS_TOKEN', 'needs-code')
    captured = {}

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, **kwargs):
            captured['session'] = json.loads(kwargs['files']['session'][1])
            return httpx.Response(200, text='answer-sdp')

    monkeypatch.setattr('v2.api.httpx.AsyncClient', FakeAsyncClient)
    with TestClient(create_app(NeedsFoodV2Repository(tmp_path / 'needs.db'))) as client:
        response = client.post(
            '/api/realtime/session?lot_id=B-20260903-M001-01',
            content='offer-sdp',
            headers={'Content-Type': 'application/sdp', 'Authorization': 'Bearer needs-code'},
        )
        assert response.status_code == 200
        names = {tool['name'] for tool in captured['session']['tools']}
        assert 'get_daily_briefing' in names
        assert 'get_batch_trace' in names
        assert 'list_tags' not in names
