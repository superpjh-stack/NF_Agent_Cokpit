from io import BytesIO
import pytest
from openpyxl import load_workbook
from fastapi.testclient import TestClient
from v2.api import create_app
from v2.compat import NeedsFoodV2Repository

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    monkeypatch.delenv('V2_REQUIRE_LOGIN',raising=False)
    with TestClient(create_app(NeedsFoodV2Repository(tmp_path/'sample.db'))) as c:yield c

@pytest.mark.parametrize('kind',['production','quality','cooking','inventory','shipments'])
def test_reports(client,kind):
    data={'kind':kind}
    if kind!='inventory':data['business_date']='2026-09-03'
    r=client.post('/api/reports',json=data);assert r.status_code==200,r.text
    report=r.json();assert report['rows'] and 'source_rows' not in report
    rid=report['report_id']
    wb=load_workbook(BytesIO(client.get(f'/api/reports/{rid}/xlsx').content))
    assert wb.active.max_row==len(report['rows'])+5
    assert client.get(f'/api/reports/{rid}/pdf').content.startswith(b'%PDF')
    if kind=='inventory':
        before=report['rows'][0][2]
        with client.app.state.repo._connect() as db:db.execute('UPDATE inventory SET quantity=0')
        wb=load_workbook(BytesIO(client.get(f'/api/reports/{rid}/xlsx').content));assert wb.active['C6'].value==before

def test_date_scope_and_chat(client):
    assert client.post('/api/reports',json={'kind':'production','business_date':'2099-01-01'}).status_code==404
    assert client.post('/api/reports',json={'kind':'inventory','business_date':'2026-09-03'}).status_code==422
    body={'question':'B-20260903-M001-01 일일생산보고서 만들어줘'}
    picker=client.post('/api/chat',json=body).json();assert picker['report_picker']=='production'
    assert picker['report_lot']=='B-20260903-M001-01'
    r=client.post('/api/chat',json={'question':'2026-09-03 일일생산보고서 만들어줘'}).json()
    assert r['report']['business_date']=='2026-09-03'
    for q in ['최근 생산 보고서','9월 3일 품질 보고서']:
        assert client.post('/api/chat',json={'question':q}).status_code==422
    r=client.post('/api/reports',json={'kind':'quality','business_date':'2026-09-03','lot_id':'B-20260903-M001-01'}).json()
    assert all(row[0]=='B-20260903-M001-01' for row in r['rows'])

def test_owner_check(client):
    store=client.app.state.work
    uid=store.add_user('v3-owner','owner','test','operator','long-password-123')
    token,_=store.login('v3-owner','long-password-123','test')
    client.cookies.set('needsfood_user',token)
    r=client.post('/api/reports',json={'kind':'inventory'}).json();rid=r['report_id']
    assert client.get(f'/api/reports/{rid}/xlsx').status_code==200
    client.cookies.clear()
    assert client.get(f'/api/reports/{rid}/xlsx').status_code==404

@pytest.mark.parametrize('mode',['ideas','detective','journey','briefing'])
def test_studio(client,mode):
    r=client.post('/api/studio',json={'mode':mode,'lot_id':'B-20260903-M001-01'})
    assert r.status_code==200,r.text
    data=r.json();assert len(data['pipeline'])==3
    valid={f['id'] for f in data['evidence']}
    for card in data['cards']:
        assert set(card['evidence_ids'])<=valid
        if card['kind']=='creative':assert not card['evidence_ids']

def test_connection_check_reports_missing_key(client):
    result=client.post('/api/connection/check')
    assert result.status_code==503
    assert 'API 키' in result.json()['detail']
