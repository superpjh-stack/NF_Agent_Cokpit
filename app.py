from pathlib import Path
import os
from dotenv import load_dotenv
import streamlit as st
from needs_agent.postgres import create_repository

from cockpit_runtime import render_cockpit
from needs_agent import (QUESTION_GROUPS, WELCOME_MESSAGE, ManufacturingAgent, NeedsFoodRepository,
                         NeedsFoodToolRegistry, batch_snapshot, risk_label, timestamp, user_question_history)

BASE_DIR=Path(__file__).parent
load_dotenv(BASE_DIR / ".env")
TODAY="2026-09-03"
@st.cache_resource
def get_repository(url, path):
    return create_repository(path, url)

repository=get_repository(os.getenv("DATABASE_URL", ""), os.getenv("SQLITE_PATH", str(BASE_DIR/"data"/"needs_food_demo.db")))
registry=NeedsFoodToolRegistry(repository)
kpi=repository.dashboard(TODAY)

def agent_factory(client,model,tools): return ManufacturingAgent(client,model=model,factory_tools=tools)

def snapshot(batch_id):
    data=batch_snapshot(repository,batch_id); batch=data["batch"]; risk,icon=risk_label(data)
    approvals=[]
    if batch.get("status")=="지연": approvals.append("생산관리: 배치 지연 대응")
    if data["shortages"]: approvals.append("영양사·자재: 원료 부족 대응")
    if any(r.get("result") not in {"합격","정상","적합"} for r in data["quality"]): approvals.append("품질·영양사: 검식 판정")
    return {"risk":risk,"icon":icon,"primary_label":"메뉴·솥","primary":f"{batch.get('menu_name','-')} · {batch.get('kettle_no','-')}","progress":100*float(batch.get('actual_qty') or 0)/max(float(batch.get('planned_qty') or 1),1),"caption":f"상태 {batch.get('status','-')} · 납기 {batch.get('due_at','-')}","counts":[("조리",len(data["readings"])),("검식",len(data["quality"])),("부족",len(data["shortages"]))],"approvals":approvals,"brief":f"{batch_id}의 레시피, 표준 조리조건과 실제 조리 편차를 알려줘"}

render_cockpit(base_dir=BASE_DIR,page_title="니즈푸드 Agent Cockpit",icon="🍱",title="니즈푸드 AI Agent",subtitle="급식 생산부터 임진감김치 제조 준비까지, 현장 데이터와 문서 근거를 함께 확인합니다.",repository=repository,registry=registry,agent_factory=agent_factory,question_groups=QUESTION_GROUPS,welcome_message=WELCOME_MESSAGE,timestamp=timestamp,history_fn=user_question_history,metrics=[("데모 계획",f"{kpi['planned_meals']:,}식"),("현재 실적",f"{kpi['actual_meals']:,}식"),("진척률",f"{kpi['completion_rate']}%"),("지연 배치",f"{kpi['delayed_batches']}건"),("재고 부족",f"{kpi['stock_shortages']}품목")],entity_label="배치",entity_ids=[r["batch_id"] for r in repository.all_batches()],snapshot_builder=snapshot,knowledge_label="레시피·조리·샘플링·품질 문서",knowledge_base_name="니즈푸드 제조 지식베이스",source_label="니즈푸드 MES/Data Hub",chat_placeholder="레시피 배합·조리조건·투입량·원가에 질문하세요",safety_note="문서·공정 DB·확인 규칙별 추천질문을 제공합니다. 모든 데이터는 데모입니다. 자동 제어·확정 판정·레시피 변경은 사람 승인 없이 실행하지 않습니다.")
