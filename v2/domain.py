import re,json
from v2.compat import NeedsFoodV2ToolRegistry as NeedsFoodToolRegistry, lot_snapshot

def demo_answer(repo, question: str, lot_id: str | None = None):
    """Deterministic lookup with explicit limits; never masquerades as an LLM."""
    evidence = repo.search_knowledge(question)
    tools, records = [], []
    matched = re.search(r'B-\d{8}-M\d{3}-\d{2}', question.upper())
    selected = matched.group() if matched else lot_id
    claim = re.search(r'CLM-\d{6}-\d{2}', question.upper())
    inbound_question = ('입고' in question or '들어온' in question or '반입' in question) and ('오늘' in question or '당일' in question)
    shipment_comparison = ('오늘' in question or '당일' in question) and '출하' in question and ('계획' in question or '실제' in question or '실적' in question or '량' in question)
    if inbound_question:
        records = repo.inventory_status(None, False)
        tools = ['get_inventory_status']
        def stock_value(row, primary, fallback): return row.get(primary, row.get(fallback))
        timestamps = [str(row.get('updated_at') or '') for row in records if row.get('updated_at')]
        latest = max(timestamps) if timestamps else '갱신시각 미기록'
        stock_lines = []
        for row in records:
            name = row.get('item_name') or row.get('material_name') or '품목 미상'
            quantity = stock_value(row, 'quantity', 'quantity_kg')
            unit = row.get('unit') or ('kg' if row.get('quantity_kg') is not None else '단위 미기록')
            if quantity is not None:
                stock_lines.append(f"{name} {quantity:,.0f}{unit}")
        stock_summary = ' · '.join(stock_lines) if stock_lines else '재고 스냅샷도 없습니다.'
        text = (f"오늘 입고량은 입고 이력 테이블이 연결되지 않아 확인할 수 없습니다. "
                f"최신 재고 스냅샷({latest}, 데모) 잔량: {stock_summary}. "
                "이 잔량은 오늘 입고량이나 예약·보류를 제외한 사용가능 재고가 아닙니다.")
    elif shipment_comparison:
        shipment_rows = repo.browse_table('shipments', 100, 0)['rows']
        menu_rows = repo.browse_table('menus', 100, 0)['rows']
        menu_names = {row['menu_code']: row['menu_name'] for row in menu_rows}
        dated_rows = [row for row in shipment_rows if row.get('due_at')]
        latest_day = max((str(row['due_at'])[:10] for row in dated_rows), default='날짜 미기록')
        selected_rows = [row for row in dated_rows if str(row['due_at'])[:10] == latest_day]
        records = [{**row, 'unit': '식', 'product_name': menu_names.get(row.get('menu_code'), row.get('menu_code', '메뉴 미상'))}
                   for row in selected_rows]
        tools = ['get_shipment_readiness']
        planned = sum(int(row.get('planned_qty') or 0) for row in records)
        shipped = sum(int(row.get('shipped_qty') or 0) for row in records)
        remaining = max(0, planned - shipped)
        detail = '\n'.join(
            f"{row['product_name']}: 계획 {int(row.get('planned_qty') or 0):,}식 · 실제 출하 {int(row.get('shipped_qty') or 0):,}식 · 상태 {row.get('status', '미기록')}"
            for row in records
        ) or '출하 기록이 없습니다.'
        text = (f"오늘 날짜의 실시간 출하 자료는 없습니다. 최신 데모 기록일 {latest_day} 기준 "
                f"계획 {planned:,}식 · 실제 출하 {shipped:,}식 · 미출하 {remaining:,}식입니다.\n{detail}")
    elif '생산 현황' in question or '진척률' in question:
        kpi = repo.dashboard(); records = [kpi]; tools = ['get_daily_briefing']
        text = f"계획 {kpi['planned_meals']:,}식 · 실적 {kpi['actual_meals']:,}식 · 진척률 {kpi['completion_rate']}% · 지연 {kpi['delayed_batches']}건입니다."
    elif claim:
        result = repo.claim_trace(claim.group())
        records = result['lot_trace']
        tools = ['get_claim_trace']
        text = f"{claim.group()} 관련 계보 {len(records)}건을 확인했습니다." if result['claim'] else '해당 클레임은 샘플 DB에서 확인되지 않습니다.'
    elif not selected and ('재고' in question or '부족' in question or '닭고기' in question):
        records = repo.inventory_status('닭고기' if '닭고기' in question else None, '부족' in question)
        tools = ['get_inventory_status']
        stock_lines = []
        for row in records[:3]:
            quantity = row.get('quantity', row.get('quantity_kg'))
            safety_stock = row.get('safety_stock', row.get('safety_stock_kg'))
            unit = row.get('unit') or ('kg' if row.get('quantity_kg') is not None else '단위 미기록')
            stock_lines.append(f"{row['item_name']}: 재고 {quantity:,.0f}{unit} · 안전재고 대비 부족 {max(0, safety_stock-quantity):,.0f}{unit}")
        text = '\n'.join(stock_lines) or '조건에 맞는 재고 기록이 없습니다.'
    elif not selected and (('발효' in question and 'CCP' in question.upper()) or '브리핑' in question):
        predictions = repo.fermentation_status(None)
        alerts = repo.ccp_deviations(None)
        risky = [r for r in predictions if (r['abnormal_risk'] or 0) >= .5]
        tools = ['get_fermentation_status', 'get_ccp_deviations']
        records = [*risky, *alerts]
        text = f"조리 측정 주의 {len(risky)}건 · 품질 주의 {len(alerts)}건입니다."
        if risky:
            r = risky[0]
            text += f"\n{r['lot_id']}: 온도 {r['temperature']}℃ · 상태 {r['status']}. 담당자 검토가 필요합니다."
    elif selected:
        records = repo.lot_trace(selected)
        tools = ['get_lot_trace']
        snap = lot_snapshot(repo, selected)
        trace_count = len(records)
        records = [*records, *snap['ccp'], *snap['shipments']]
        text = f"{selected} 생산 배치 기록 {trace_count}건 · 품질 주의 {len(snap['ccp'])}건을 확인했습니다." if records else '해당 배치는 샘플 DB에서 확인되지 않습니다.'
        if records and any(word in question for word in ['조리', 'pH', '온도', '염도', '품질']):
            measurements = repo.process_measurements(selected)
            records.extend(measurements)
            tools.append('get_process_measurements')
            if measurements:
                r = measurements[0]
                text += f"\n최근 조리 측정: 온도 {r['temperature']}℃ · 설비 {r['equipment_id']} · 상태 {r['equipment_status']} ({r['recorded_at']})."
            else:
                text += '\n선택 LOT의 직접 측정 기록은 미확인입니다. 연결된 공정의 상세 기록을 확인하세요.'
    elif '출하' in question:
        records = repo.shipment_readiness(None)
        tools = ['get_shipment_readiness']
        text = f"출하 기록 {len(records)}건 중 승인대기 {sum(r['approval_status'] != '승인' for r in records)}건입니다. 승인 여부는 담당자가 결정합니다."
    elif 'CCP' in question.upper():
        records = repo.ccp_deviations(None)
        tools = ['get_ccp_deviations']
        text = f"샘플 CCP 주의 기록 {len(records)}건입니다. 관련 LOT·발생시각·처분 승인 이력을 확인하세요."
    elif '조리' in question or '위험' in question or '브리핑' in question:
        records = repo.fermentation_status(None)
        tools = ['get_fermentation_status']
        text = f"조리 측정 기록 {len(records)}건입니다. 측정값과 품질 결과를 함께 검토하세요."
    elif '룰' in question or '규칙' in question:
        records = repo.get_rules()
        tools = ['get_rules']
        text = f"검토 규칙 {len(records)}개가 등록되어 있습니다. 모두 미승인 샘플이며 자동 조치를 실행하지 않습니다."
    else:
        text = f"관련 샘플 문서 {len(evidence)}개를 찾았습니다. 아래 근거에서 절차와 담당자를 확인하세요." if evidence else '현재 샘플 DB·문서에서 질문의 답을 확인하지 못했습니다.'
    if '오늘' in question or '현재' in question:
        text = '오늘의 실시간 기록은 없습니다. 아래는 2026년 9월 샘플 조회입니다.\n' + text
    return {'text': text + '\n근거: ' + (', '.join(tools + [d['document_id'] for d in evidence[:2]]) or '일치하는 기록·문서 없음'), 'sources': [d['filename'] for d in evidence], 'evidence': evidence, 'data_tools': tools, 'records': records, 'searched_documents': True, 'mode': 'demo', 'demo_data': True}


class EvidenceRegistry(NeedsFoodToolRegistry):
    def __init__(self, repo):
        super().__init__(repo)
        self.records = []
        self.demo_data = False
        self.documents = []
        self.tools_used = []

    @property
    def definitions(self):
        return [d for d in super().definitions if d['name'] in self.handlers]

    def execute(self, name, arguments):
        self.tools_used.append(name)
        result = super().execute(name, arguments)
        payload = json.loads(result)
        if payload.get('status') == 'ok':
            self.demo_data = self.demo_data or payload.get('demo_data', False)
        if payload.get('status') == 'ok' and name == 'search_knowledge':
            self.documents.extend(payload.get('result') or [])
        if payload.get('status') == 'ok' and name != 'search_knowledge':
            values = payload.get('result')
            rows = values if isinstance(values, list) else [values]
            for row in rows:
                if isinstance(row, dict) and row not in self.records:
                    self.records.append(row)
        return result


