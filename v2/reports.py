"""Needs Food report snapshots with existing session ownership."""
from datetime import date,datetime,timedelta
from zoneinfo import ZoneInfo
from io import BytesIO
from uuid import uuid4
from typing import Literal
import json,re,unicodedata
from xml.sax.saxutils import escape
from fastapi import HTTPException,Request
from fastapi.responses import Response
from pydantic import BaseModel,Field,ConfigDict
TITLES={'production':'일일생산보고서','quality':'품질검식 보고서','cooking':'조리측정 보고서','inventory':'원료재고 보고서','shipments':'출하계획 대비 실적 보고서'}
class ReportInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    kind:Literal['production','quality','cooking','inventory','shipments']
    business_date:date|None=None
    lot_id:str|None=Field(None,max_length=80)

def query(repo,sql,args=()):
    with repo._connect() as db:return [dict(r) for r in db.execute(sql,args).fetchall()]

def initialize(repo):
    with repo._connect() as db:db.execute('CREATE TABLE IF NOT EXISTS v3_report_exports(report_id TEXT PRIMARY KEY,owner_id TEXT,snapshot TEXT NOT NULL)')

def snapshot(repo,body):
    if body.lot_id and not repo.lot_trace(body.lot_id):raise HTTPException(404,'배치를 찾을 수 없습니다.')
    if body.kind!='inventory' and not body.business_date:raise HTTPException(422,'보고서 기준일을 선택하세요.')
    if body.kind in ('inventory','shipments') and body.lot_id:raise HTTPException(422,'원료재고와 출하는 배치별 배분 근거가 없습니다. LOT 조건을 해제해 주세요.')
    if body.kind=='inventory' and body.business_date:raise HTTPException(422,'재고는 현재 등록 스냅샷입니다. 과거 날짜 필터는 지원하지 않습니다.')
    day=body.business_date.isoformat() if body.business_date else None
    notes=['니즈푸드 2026년 9월 가상·미승인 샘플입니다. 실제 운영 현황이나 출하 승인이 아닙니다.','미입력과 0을 구분하며 원본이 없는 수치를 추정하지 않습니다.']
    args=(day,) if day else ()
    if body.kind=='production':
        sql='SELECT b.*,m.menu_name,m.meal_date FROM production_batches b JOIN menus m ON b.menu_code=m.menu_code WHERE m.meal_date=?'
        keys=['batch_id','menu_name','kettle_no','planned_qty','actual_qty','status','started_at','ended_at'];columns=['배치','메뉴','조리솥','계획 식','실적 식','상태','시작','종료']
        notes.append('메뉴의 급식 기준일로 집계한 배치 계획·현재 등록 실적입니다. 시작일/종료일 기준 실적과 다를 수 있으며 진행 중 수량은 확정 실적이 아닙니다.')
    elif body.kind=='quality':
        sql='SELECT q.*,m.menu_name FROM quality_checks q LEFT JOIN production_batches b ON q.batch_id=b.batch_id LEFT JOIN menus m ON b.menu_code=m.menu_code WHERE q.checked_at LIKE ?';args=(day+'%',)
        keys=['batch_id','menu_name','check_type','sample_count','result','issue','checked_at'];columns=['배치','메뉴','검사 유형','검체 수','결과','이슈','검사 시각']
        notes.append('검사시각 기준. 일부 검체의 결과를 전체 배치 합격으로 확대 해석하지 않습니다.')
    elif body.kind=='cooking':
        sql='SELECT c.*,m.menu_name FROM cooking_readings c JOIN production_batches b ON c.batch_id=b.batch_id JOIN menus m ON b.menu_code=m.menu_code WHERE c.recorded_at LIKE ?';args=(day+'%',)
        keys=['batch_id','menu_name','equipment_id','temperature','stir_speed','pressure','motor_speed','recorded_at'];columns=['배치','메뉴','설비','온도 (원본값)','교반 (원본값)','압력 (원본값)','모터 (원본값)','측정시각']
        notes.append('원본 측정 테이블에는 단위·허용기준 필드가 없습니다. 단위·교정·승인 기준을 확인하기 전 자동 적합 판정을 하지 않습니다.')
    elif body.kind=='inventory':
        sql='SELECT * FROM inventory';keys=['material_code','material_name','quantity','unit','safety_stock','expiry_date','updated_at'];columns=['원료코드','원료','현재고','단위','안전재고','사용기한','갱신시각']
        notes.append('입고 이력이 아닌 재고 스냅샷입니다. 예약·보류 수량을 제외한 사용가능량은 미확인입니다. 서로 다른 단위를 합산하지 않습니다.')
    else:
        sql='SELECT s.*,m.menu_name FROM shipments s JOIN menus m ON s.menu_code=m.menu_code WHERE s.due_at LIKE ?';args=(day+'%',)
        keys=['shipment_id','menu_name','planned_qty','shipped_qty','due_at','shipped_at','status'];columns=['출하번호','메뉴','계획 식','누적 출하 식','출하예정','실제출하시각','상태']
        notes.append('출하예정일 기준 계획과 현재 등록된 누적 출하량 비교입니다. 선택 날짜에 실제 출하한 수량 집계가 아닙니다.')
    if body.lot_id:
        sql+=' AND b.batch_id=?';args=(*args,body.lot_id)
    source=query(repo,sql,args)
    if not source:raise HTTPException(404,'해당 날짜·조건의 원본 기록이 없습니다. 다른 날짜로 대체하지 않았습니다.')
    return {'report_id':uuid4().hex,'title':TITLES[body.kind],'kind':body.kind,'lot_id':body.lot_id,'business_date':day,'columns':columns,'rows':[[r.get(k) for k in keys] for r in source],'source_rows':source,'source':'니즈푸드 제조 DB · 가상 샘플','as_of':'2026-09-03 샘플 / 각 행의 기록시각 확인','notes':notes,'created_at':datetime.now(ZoneInfo('Asia/Seoul')).isoformat()}

def create(repo,body,user=None):
    data=snapshot(repo,body);initialize(repo)
    with repo._connect() as db:db.execute('INSERT INTO v3_report_exports VALUES (?,?,?)',(data['report_id'],user['id'] if user else None,json.dumps(data,ensure_ascii=False)))
    return {k:v for k,v in data.items() if k!='source_rows'}

def export_xlsx(data):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    wb = Workbook(); ws = wb.active; ws.title = '보고서'
    ws.append(['니즈푸드 · '+data['title']]); ws.append(['기준일', data['business_date'] or data['as_of'], '생성 시각', data['created_at']])
    ws.append(['출처', data['source']]); ws.append([' / '.join(data['notes'])]); ws.append(data['columns'])
    for row in data['rows']: ws.append(row)
    for row in ws:
        for cell in row:
            if isinstance(cell.value, str): cell.data_type = 's'
            cell.font = Font(name='맑은 고딕', size=10)
            cell.alignment = Alignment(vertical='center',wrap_text=True)
    for cell in ws[5]:
        cell.fill = PatternFill('solid', fgColor='173F4B'); cell.font = Font(color='FFFFFF',bold=True)
    width = max(len(data['columns']),4)
    ws.merge_cells(start_row=1,start_column=1,end_row=1,end_column=width)
    ws.merge_cells(start_row=4,start_column=1,end_row=4,end_column=width)
    ws.row_dimensions[1].height = 32; ws.row_dimensions[4].height = 65
    for i in range(1,width+1): ws.column_dimensions[get_column_letter(i)].width = 30 if i<=2 else 20
    ws.freeze_panes='A6'; ws.auto_filter.ref=f'A5:{get_column_letter(len(data["columns"]))}{ws.max_row}'
    ws.print_title_rows='1:5'; ws.sheet_properties.pageSetUpPr.fitToPage=True
    ws.page_setup.orientation='landscape'; ws.page_setup.paperSize=ws.PAPERSIZE_A4; ws.page_setup.fitToWidth=1; ws.page_setup.fitToHeight=0
    ws.print_options.horizontalCentered=True
    source = wb.create_sheet('원본 스냅샷')
    keys = list(dict.fromkeys(k for row in data['source_rows'] for k in row))
    source.append(keys)
    for row in data['source_rows']: source.append([row.get(k) for k in keys])
    for row in source:
        for cell in row:
            if isinstance(cell.value,str): cell.data_type='s'
    source.freeze_panes='A2'
    buffer=BytesIO(); wb.save(buffer); return buffer.getvalue()

def export_pdf(data):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle
    pdfmetrics.registerFont(UnicodeCIDFont('HYSMyeongJo-Medium'))
    style=ParagraphStyle('ko',fontName='HYSMyeongJo-Medium',fontSize=9,leading=14,wordWrap='CJK')
    p=lambda value: Paragraph(escape(unicodedata.normalize('NFC','미입력' if value is None else str(value))),style)
    buffer=BytesIO(); doc=SimpleDocTemplate(buffer,pagesize=landscape(A4),rightMargin=30,leftMargin=30,topMargin=25,bottomMargin=25)
    story=[p('니즈푸드 · '+data['title']),p('기준일: '+str(data['business_date'] or data['as_of'])+' / 생성: '+data['created_at']),p('출처: '+str(data['source'])),*[p(n) for n in data['notes']],Spacer(1,12)]
    table=LongTable([[p(c) for c in data['columns']]]+[[p(c) for c in r] for r in data['rows']],colWidths=[doc.width/len(data['columns'])]*len(data['columns']),repeatRows=1)
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),'#E6EFF0'),('GRID',(0,0),(-1,-1),.3,'#BCCFD2'),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
    story.append(table)
    def footer(canvas, doc):
        canvas.setFont('HYSMyeongJo-Medium',8); canvas.drawString(30,12,f"{data['report_id']} · {doc.page}")
    doc.build(story,onFirstPage=footer,onLaterPages=footer); return buffer.getvalue()

def chat_request(question,lot):
    if not re.search(r'보고서|실적표',question):return None
    kind='production' if '생산' in question or '실적표' in question else 'quality' if re.search(r'품질|검식',question) else 'cooking' if re.search(r'조리|측정',question) else 'inventory' if '재고' in question else 'shipments' if '출하' in question else None
    if not kind:return None
    if re.search(r'부터|까지|지난|최근|이번|일주일',question):raise ValueError('기간 보고서는 지원하지 않습니다. YYYY-MM-DD 한 날짜를 지정하세요.')
    days=re.findall(r'\d{4}-\d{2}-\d{2}',question)
    if len(days)>1:raise ValueError('보고서는 한 날짜씩 생성하세요.')
    day=date.fromisoformat(days[0]) if days else None
    if not day and any(w in question for w in ['오늘','어제']):day=datetime.now(ZoneInfo('Asia/Seoul')).date()-timedelta(days=1 if '어제' in question else 0)
    if not day and re.search(r'\d+월|\d{4}[./]',question):raise ValueError('날짜는 YYYY-MM-DD 형식으로 입력하세요.')
    return ReportInput(kind=kind,business_date=day,lot_id=lot)

def install(app):
    @app.post('/api/reports')
    def generate(body:ReportInput,request:Request):
        return create(app.state.repo,body,app.state.work.user(request,False))
    @app.get('/api/reports/{report_id}/{extension}')
    def download(report_id:str,extension:str,request:Request):
        if not re.fullmatch(r'[a-f0-9]{32}',report_id) or extension not in ('xlsx','pdf'):raise HTTPException(404,'파일을 찾을 수 없습니다.')
        repo=app.state.repo;initialize(repo)
        rows=query(repo,'SELECT * FROM v3_report_exports WHERE report_id=?',(report_id,))
        if not rows:raise HTTPException(404,'보고서가 없습니다.')
        user=app.state.work.user(request,False)
        if rows[0]['owner_id'] and (not user or user['id']!=rows[0]['owner_id']):raise HTTPException(404,'보고서가 없습니다.')
        data=json.loads(rows[0]['snapshot'])
        content=export_xlsx(data) if extension=='xlsx' else export_pdf(data)
        return Response(content,media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' if extension=='xlsx' else 'application/pdf',headers={'Cache-Control':'no-store','Content-Disposition':f'attachment; filename="needsfood-{report_id}.{extension}"'})
