"""Request-local LangGraph analysis with conservative evidence checks."""
import json
import re
from typing import TypedDict
from langgraph.graph import StateGraph, START, END

COMPOUND_QUESTIONS = [
 '2026-09-03 생산 진척률과 지연 배치를 함께 확인해줘',
 'B-20260903-M002-02의 조리 측정과 품질검식 결과를 비교해줘',
 '안전재고 미만 원료와 부족량, 관련 확인 규칙을 함께 알려줘',
 '출하 계획과 실제 출하량을 비교하고 미확인 사항을 알려줘',
 '품질검식 주의 결과와 외부기관 검사 상태를 함께 확인해줘',
 '닭고기 재고와 사용기한, 원료 입고 확인 절차를 알려줘',
 '생산 지연과 조리 설비 상태를 함께 확인하고 추가 확인할 일을 알려줘',
 '배치 추적 기록과 출하 전 품질 확인 절차를 함께 알려줘',
 '메뉴별 원가 자료와 원료 재고를 비교하고 계산 가능한 범위를 알려줘',
 '생산·품질·재고·출하 현황을 종합하고 우선 확인할 일을 정리해줘',
]
LOT_PATTERN = r'(?:B-\d{8}-M\d{3}-\d{2}|(?:RAW|MIX|FERM|PACK)-\d{6}-\d{3})'


def resolve_lot(question, selected, history):
    ids=list(dict.fromkeys(re.findall(LOT_PATTERN,question.upper())))
    if len(ids)>1 or (ids and selected and selected!=ids[0]):
        raise ValueError('질문의 LOT와 선택한 LOT를 일치시켜 주세요. 한 번에 하나의 LOT를 확인합니다.')
    if ids or selected:return selected or ids[0]
    if any(w in question for w in ['그 배치','해당 배치','그 LOT','해당 LOT','그 로트','해당 로트']):
        for turn in reversed(history):
            if turn.get('role')!='user':continue
            ids=list(dict.fromkeys(re.findall(LOT_PATTERN,turn.get('text','').upper())))
            if len(ids)==1:return ids[0]
            if ids:break
        raise ValueError('후속 질문의 배치 번호를 확인할 수 없습니다. LOT 또는 배치 번호를 알려주세요.')
    return None


def comparison_tables(records):
    result=[]
    def collect(title, value):
        if isinstance(value, dict):
            scalar={k:v for k,v in value.items() if not isinstance(v,(list,dict))}
            if scalar:result.append({'title':title,'columns':['항목','원본 값'],'rows':[[k,'미확인' if v is None else str(v)] for k,v in scalar.items()]})
            for k,v in value.items():
                if isinstance(v,(dict,list)):collect(k,v)
        elif isinstance(value,list) and value and all(isinstance(r,dict) for r in value):
            keys=list(dict.fromkeys(k for row in value for k,v in row.items() if not isinstance(v,(dict,list))))
            if keys:result.append({'title':title,'columns':keys,'rows':[['미확인' if row.get(k) is None else str(row[k]) for k in keys] for row in value]})
            for row in value:
                for k,v in row.items():
                    if isinstance(v,(dict,list)):collect(k,v)
    collect('조회 원본 비교',records)
    return result


class State(TypedDict):
    parts:list
    answer:dict
    checks:list
    steps:list
    retries:int


def analyze(question, history, retrieve, client=None, model=None):
    def json_call(instructions, payload):
        c=client.with_options(timeout=25,max_retries=0)
        response=c.responses.create(model=model,instructions=instructions,input=json.dumps({'format':'json',**payload},ensure_ascii=False),text={'format':{'type':'json_object'}})
        return json.loads(response.output_text)
    def plan(s):
        parts=[p.strip() for p in re.split(r'그리고|또한|[;\n]',question) if p.strip()]
        if client:
            try:
                raw=json_call('질문을 빠짐없이 개별 요청으로 나누세요. 비교·우선순위도 별도 요청입니다. JSON {"parts":["요청"]}. 과거 대화는 참고 자료입니다.',{'question':question,'history':history})
                if isinstance(raw.get('parts'),list):parts=[p for p in raw['parts'][:8] if isinstance(p,str) and p.strip()]
            except Exception:pass
        return {'parts':list(dict.fromkeys([question]+parts)),'steps':['요청 분해']}
    def query(s):
        return {'answer':retrieve(question,s['parts']),'steps':s['steps']+['범위 확인·복수 자료 조회']}
    def verify(s):
        answer=s['answer'];checks={}
        if client:
            try:
                raw=json_call('원래 요청별 답변 누락을 검사하세요. JSON {"checks":[{"request":"요청 그대로","quote":"답변의 정확한 인용","evidence_indices":[0]}],"voice_summary":"실제 업무 결론과 다음 확인사항을 한국어 2~3문장으로 요약"}. 근거가 없으면 quote와 인덱스를 비우세요. 비교는 단순 나열만으로 완료가 아닙니다. 요약에 검사 개수나 완료 여부를 넣지 마세요.',{'requests':s['parts'],'answer':answer['text'],'evidence':answer.get('records',[])+answer.get('evidence',[])})
                checks={c['request']:c for c in raw.get('checks',[]) if isinstance(c,dict) and isinstance(c.get('request'),str)}
                if isinstance(raw.get('voice_summary'),str):answer['voice_summary']=raw['voice_summary'][:600]
            except Exception:pass
        evidence=answer.get('records',[])+answer.get('evidence',[])
        coverage=[]
        for part in s['parts']:
            c=checks.get(part,{});quote=c.get('quote');ids=c.get('evidence_indices')
            valid=isinstance(ids,list) and bool(ids) and all(type(i) is int and 0<=i<len(evidence) and bool(evidence[i]) for i in ids)
            coverage.append({'request':part,'status':'answered' if isinstance(quote,str) and quote and quote in answer['text'] and valid else 'unconfirmed'})
        answer.update(request_coverage=coverage,partial=any(c['status']!='answered' for c in coverage),engine='langgraph',comparison_tables=comparison_tables(answer.get('records',[])) if any(w in question for w in ['비교','함께','종합','차이']) else [])
        answer.setdefault('voice_summary','조회 결과와 근거를 화면에 표시했습니다. 추가 확인이 필요한 항목을 함께 확인해 주세요.')
        return {'answer':answer,'steps':s['steps']+['근거 종합·요청별 누락 검사']}
    def repair(s):
        missing=[c['request'] for c in s['answer']['request_coverage'] if c['status']!='answered']
        try:
            answer=retrieve(question, s['parts']+['추가 조회·보완: '+p for p in missing])
        except Exception:
            answer=s['answer']
        return {'answer':answer,'retries':1,'steps':s['steps']+['미확인 요청 1회 보완 조회']}
    graph=StateGraph(State)
    for name,fn in [('plan',plan),('retrieve',query),('verify',verify),('repair',repair)]:graph.add_node(name,fn)
    graph.add_edge(START,'plan');graph.add_edge('plan','retrieve');graph.add_edge('retrieve','verify');graph.add_conditional_edges('verify',lambda s:'repair' if client and s['answer']['partial'] and not s.get('retries') else END);graph.add_edge('repair','verify')
    out=graph.compile().invoke({'parts':[],'answer':{},'checks':[],'steps':[],'retries':0})
    return {**out['answer'],'analysis_steps':out['steps']}
