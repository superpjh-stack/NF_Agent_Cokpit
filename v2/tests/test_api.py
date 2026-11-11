from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from needs_agent import NeedsFoodRepository
from v2.api import create_app
from v2.compat import NeedsFoodV2Repository


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('COCKPIT_ACCESS_TOKEN', raising=False)
    monkeypatch.delenv('V2_LOCAL_AI_NO_TOKEN', raising=False)
    repo = NeedsFoodRepository(tmp_path / 'v2.db')
    with TestClient(create_app(repo)) as client:
        yield client


@pytest.fixture
def v2_client(tmp_path, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('COCKPIT_ACCESS_TOKEN', raising=False)
    monkeypatch.delenv('V2_LOCAL_AI_NO_TOKEN', raising=False)
    repo = NeedsFoodV2Repository(tmp_path / 'v2-daily-questions.db')
    with TestClient(create_app(repo)) as client:
        yield client


def test_workspace_returns_real_counts_and_no_credentials(client):
    data = client.get('/api/workspace').json()
    assert data['kpi']['planned_meals'] == 6800
    assert len(data['lots']) == 4
    assert len(data['rules']) == 7
    assert not data['meta']['ai_configured']
    assert client.get('/api/health').json()['status'] == 'ok'
    assert not any(k in str(data) for k in ['OPENAI_API_KEY', 'DATABASE_URL', 'COCKPIT_ACCESS_TOKEN'])


def test_lot_and_query_boundaries(client):
    detail = client.get('/api/lots/B-20260903-M001-01').json()
    assert detail['trace'][0]['lot_id'] == 'B-20260903-M001-01'
    assert len(detail['measurements']) == 1
    assert client.get('/api/lots/unknown').status_code == 404
    assert client.get('/api/tables/app_settings').status_code == 400
    assert client.get('/api/tables/production_batches?limit=101').status_code == 422
    assert client.get('/api/tables/production_batches?offset=-1').status_code == 422
    assert client.get('/api/tables/production_batches?limit=2&offset=2').json() != client.get('/api/tables/production_batches?limit=2').json()


def test_demo_chat_retrieves_trace_and_evidence_without_provider(client):
    result = client.post('/api/chat', json={'question': '니즈, B-20260903-M001-01을 원재료까지 추적해줘'}).json()
    assert result['mode'] == 'demo'
    assert result['records'][0]['lot_id'] == 'B-20260903-M001-01'
    assert result['evidence'] and result['searched_documents']
    assert 'get_lot_trace' in result['data_tools']
    assert client.post('/api/chat', json={'question':'  '}).status_code == 422
    assert client.post('/api/chat', json={'question':'x','mode':'write'}).status_code == 422
    assert client.post('/api/chat', json={'question':'x'*2001}).status_code == 422


def test_demo_stock_and_historical_time_disclosure(client):
    result = client.post('/api/chat', json={'question':'니즈, 오늘 닭고기 재고 부족량은?'}).json()
    assert '60kg' in result['text']
    assert '오늘의 실시간 기록은 없습니다' in result['text']
    assert result['records'][0]['item_name'] == '닭고기'


def test_today_inbound_is_not_guessed_from_inventory_snapshot(v2_client):
    result = v2_client.post('/api/chat', json={'question':'니즈, 오늘 들어온 재고는 어떻게돼?'}).json()
    assert result['mode'] == 'demo'
    assert '입고 이력 테이블이 연결되지 않아 확인할 수 없습니다' in result['text']
    assert '2026-09-03 06:30' in result['text']
    assert '쌀 1,850kg' in result['text'] and '닭고기 240kg' in result['text']
    assert '오늘 입고량' in result['text']
    assert len(result['records']) == 4
    assert 'get_inventory_status' in result['data_tools']
    assert any(doc['document_id'] == 'NF-KB-004' for doc in result['evidence'])


def test_today_shipment_plan_and_actual_are_summed_in_meals_without_ai(v2_client):
    result = v2_client.post('/api/chat', json={
        'question':'니즈, 오늘 출하계획 및 실제 출하량은 어떻게 돼?', 'mode':'ai'
    }).json()
    assert result['mode'] == 'demo'
    assert '최신 데모 기록일 2026-09-03 기준 계획 6,800식 · 실제 출하 3,975식 · 미출하 2,825식' in result['text']
    assert '소고기미역국 세트: 계획 4,000식 · 실제 출하 3,975식' in result['text']
    assert '닭갈비 세트: 계획 2,800식 · 실제 출하 0식' in result['text']
    assert len(result['records']) == 2
    assert 'get_shipment_readiness' in result['data_tools']
    assert any(doc['document_id'] == 'NF-KB-008' for doc in result['evidence'])


def test_revised_inbound_knowledge_updates_an_existing_demo_database(tmp_path):
    database = tmp_path / 'existing-demo.db'
    first = NeedsFoodV2Repository(database)
    with first._connect() as connection:
        connection.execute("UPDATE knowledge_documents SET revision='DEMO-1', body='이전 데모 문서' WHERE document_id='NF-KB-004'")
    refreshed = NeedsFoodV2Repository(database)
    document = next(row for row in refreshed.knowledge_documents() if row['document_id'] == 'NF-KB-004')
    assert document['revision'] == 'DEMO-2'
    assert '입고 이력 테이블' in document['content']


def test_documents_rules_linkage_and_empty_search(client):
    docs = client.get('/api/documents').json()
    ids = {d['document_id'] for d in docs}
    rules = client.get('/api/workspace').json()['rules']
    assert len(docs) == 10
    assert all(r['source_document'] in ids for r in rules)
    assert client.get('/api/documents?q=절임').json()
    assert client.get('/api/documents?q=xyzxyzxyz').json() == []
    assert all('embedding' not in d for d in docs)


def test_paid_api_gate_and_configuration_secrecy(client, monkeypatch):
    assert client.post('/api/chat', json={'question':'니즈, 발효','mode':'ai'}).status_code == 503
    monkeypatch.setenv('OPENAI_API_KEY','sk-test-must-not-leak')
    monkeypatch.setenv('COCKPIT_ACCESS_TOKEN','private-test-code')
    meta = client.get('/api/workspace').json()['meta']
    assert meta['ai_configured']
    assert 'private-test-code' not in str(meta) and 'sk-test-must-not-leak' not in str(meta)
    assert client.post('/api/chat', json={'question':'니즈, 발효','mode':'ai'}, headers={'Host':'production.example'}).status_code == 401
    assert client.post('/api/voice/speak', json={'text':'발효'}, headers={'Authorization':'Bearer wrong','Host':'production.example'}).status_code == 401
    assert client.post('/api/chat/reset').json()['status'] == 'ok'


def test_realtime_voice_session_is_gated_and_uses_verified_lot_context(client, monkeypatch):
    assert client.post('/api/realtime/session', content='offer', headers={'Content-Type':'application/sdp'}).status_code == 503
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-test-realtime-secret')
    monkeypatch.setenv('COCKPIT_ACCESS_TOKEN', 'voice-code')
    captured = {}

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            captured['client'] = kwargs
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return None
        async def post(self, url, **kwargs):
            captured['url'] = url
            captured['request'] = kwargs
            return httpx.Response(200, text='answer-sdp')

    monkeypatch.setattr('v2.api.httpx.AsyncClient', FakeAsyncClient)
    headers = {'Content-Type':'application/sdp', 'Authorization':'Bearer voice-code'}
    response = client.post('/api/realtime/session?lot_id=B-20260903-M001-01', content='offer-sdp', headers=headers)
    assert response.status_code == 200
    assert response.text == 'answer-sdp'
    assert response.headers['content-type'].startswith('application/sdp')
    assert captured['url'] == 'https://api.openai.com/v1/realtime/calls'
    assert captured['request']['headers']['Authorization'] == 'Bearer sk-test-realtime-secret'
    assert 'sk-test-realtime-secret' not in response.text
    session = captured['request']['files']['session'][1]
    assert 'B-20260903-M001-01' in session
    assert 'semantic_vad' in session and 'gpt-realtime-2.1' in session
    assert client.post('/api/realtime/session?lot_id=UNKNOWN', content='offer', headers=headers).status_code == 404
    assert client.post('/api/realtime/session', content='offer', headers={'Content-Type':'application/sdp','Authorization':'Bearer wrong','Host':'production.example'}).status_code == 401


def test_local_development_can_use_server_ai_without_browser_token(client, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-local-test')
    monkeypatch.setenv('V2_LOCAL_AI_NO_TOKEN', '1')
    monkeypatch.delenv('COCKPIT_ACCESS_TOKEN', raising=False)
    captured = {}

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return None
        async def post(self, url, **kwargs):
            captured['authorization'] = kwargs['headers']['Authorization']
            return httpx.Response(200, text='local-answer-sdp')

    monkeypatch.setattr('v2.api.httpx.AsyncClient', FakeAsyncClient)
    meta = client.get('/api/workspace').json()['meta']
    assert meta['ai_configured'] is True
    assert meta['local_dev_ai'] is True
    response = client.post('/api/realtime/session', content='offer', headers={'Content-Type':'application/sdp'})
    assert response.status_code == 200
    assert response.text == 'local-answer-sdp'
    assert captured['authorization'] == 'Bearer sk-local-test'


def test_production_frontend_entrypoint(client):
    assert client.get('/').status_code == 200
    assert '<html lang="ko"' in client.get('/').text
    assert client.get('/api/not-a-route').status_code == 404


def test_postgres_v2_workspace_and_reopen(monkeypatch):
    import os
    import uuid
    from needs_agent.data_hub import PostgresRepository
    admin_url = os.getenv('TEST_POSTGRES_ADMIN_URL')
    if not admin_url:
        pytest.skip('Set TEST_POSTGRES_ADMIN_URL for PostgreSQL integration')
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo
    name = 'needs_food_v2_test_' + uuid.uuid4().hex
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        try:
            url = make_conninfo(admin_url, dbname=name)
            repo = PostgresRepository(url)
            monkeypatch.delenv('V2_REQUIRE_LOGIN', raising=False)
            app = create_app(repo)
            with TestClient(app) as client:
                workspace = client.get('/api/workspace').json()
                assert workspace['meta']['backend'] == 'PostgreSQL + pgvector'
                assert len(client.get('/api/documents').json()) == 10
                assert len(client.get('/api/lots/B-20260903-M001-01').json()['trace']) == 6
                assert client.post('/api/chat', json={'question': '니즈, 율무 재고 부족량'}).json()['records'][0]['item_code'] == 'R002'
                # v2 tables (users, sessions, work, answers, journey events) must work on PostgreSQL too.
                app.state.work.add_user('admin', 'admin', 'factory-a', 'admin', 'test-password-123!')
                assert client.post('/api/auth/login', json={'username': 'admin', 'password': 'wrong'}).status_code == 401
                assert client.post('/api/auth/login', json={'username': 'admin', 'password': 'test-password-123!'}).status_code == 200
                answer = client.post('/api/chat', json={'question': '니즈, CCP 근거를 확인해줘', 'lot_id': 'B-20260903-M001-01'}).json()
                item = client.post('/api/work-items', json={'request_id': str(uuid.uuid4()), 'title': '포장 LOT 검토',
                                                            'lot_id': 'B-20260903-M001-01', 'note': '현장 확인', 'answer_id': answer['answer_id']}).json()
                assert item['snapshot']['answer']['records']
                assert client.get('/api/work-items/' + item['id']).json()['version'] == item['version']
                journey = item['id']
                assert client.post('/api/events', json={'events': [
                    {'event': 'task_saved', 'journey_id': journey, 'device': 'mobile'},
                    {'event': 'task_resumed', 'journey_id': journey, 'device': 'desktop'}]}).status_code == 204
                report = client.get('/api/metrics').json()
                assert report['devices']['mobile']['journey_completion_rate'] == 1
            reopened = PostgresRepository(url)
            assert len(reopened.knowledge_documents()) == 10
            assert len(reopened.get_rules()) == 7
            with reopened._connect() as c:
                assert len(c.execute('SELECT * FROM v2_journey_events').fetchall()) == 2
                assert c.execute('SELECT COUNT(*) FROM v2_work').fetchone()[0] == 1
        finally:
            admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))
