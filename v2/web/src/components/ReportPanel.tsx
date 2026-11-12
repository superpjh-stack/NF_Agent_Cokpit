import {useEffect,useRef,useState} from 'react';
import {request} from '../v3request';
import {apiPath} from '../apiPath';
export type ReportKind='production'|'quality'|'cooking'|'inventory'|'shipments';
export type ReportData={title:string;kind:ReportKind;lot_id?:string|null;business_date:string|null;columns:string[];rows:(string|number|null)[][];notes:string[];created_at:string;report_id:string;source:string;as_of:string};
export const reportTitles:Record<ReportKind,string>={'production':'일일생산보고서','quality':'품질검식 보고서','cooking':'조리측정 보고서','inventory':'원료재고 보고서','shipments':'출하계획 대비 실적 보고서'};
export default function ReportPanel({token,kind:initialKind='production',initial,lot}:{token:string;lot?:string|null;kind?:ReportKind;initial?:ReportData}){
 const [kind,setKind]=useState<ReportKind>(initial?.kind||initialKind),[day,setDay]=useState(initial?.business_date||''),[data,setData]=useState(initial),[busy,setBusy]=useState(false),[status,setStatus]=useState(''),[error,setError]=useState('');
 const pending=useRef<AbortController|null>(null);
 useEffect(()=>()=>pending.current?.abort(),[]);
 async function generate(){
  const controller=new AbortController();pending.current=controller;setBusy(true);setError('');setData(undefined);setStatus('원본을 확인하고 보고서를 생성하고 있습니다…');
  const timer=setTimeout(()=>controller.abort(),30000);
  try{const result=await request<ReportData>(token,'/reports',{method:'POST',signal:controller.signal,body:JSON.stringify({kind,lot_id:initial?.lot_id||lot||null,business_date:kind!=='inventory'?day:null})});setData(result);setStatus('보고서 생성 완료. 아래에서 파일을 내려받으세요.')}
  catch(e){setStatus('');setError((e as Error).name==='AbortError'?'생성 대기 시간이 초과되었습니다. 다시 시도하세요.':(e as Error).message)}finally{clearTimeout(timer);setBusy(false);pending.current=null}
 }
 async function download(extension:string){
  if(!data)return;const controller=new AbortController();pending.current=controller;setBusy(true);setError('');setStatus(extension.toUpperCase()+' 파일을 준비하고 있습니다…');const timer=setTimeout(()=>controller.abort(),60000);
  try{const response=await fetch(apiPath(`/api/reports/${data.report_id}/${extension}`),{headers:{Authorization:'Bearer '+token},signal:controller.signal});if(!response.ok){const body=await response.json();throw new Error(body.detail||'다운로드 실패')}const url=URL.createObjectURL(await response.blob());const a=document.createElement('a');a.href=url;a.download=`니즈푸드-${data.title}-${data.business_date||data.as_of}.${extension}`;a.click();setTimeout(()=>URL.revokeObjectURL(url),10000);setStatus('파일 다운로드를 시작했습니다.')}
  catch(e){setStatus('');setError((e as Error).name==='AbortError'?'파일 준비 시간이 초과되었습니다. 다시 시도하세요.':(e as Error).message)}finally{clearTimeout(timer);pending.current=null;setBusy(false)}
 }
 return <section className="report-panel"><h2>양식 보고서</h2><p className="muted">니즈푸드 업무용 기본 양식 · 원본 기준과 미입력 항목을 함께 표시합니다.</p><form className="v3-form" onSubmit={e=>{e.preventDefault();void generate()}}><label>보고서 종류<select value={kind} disabled={busy} onChange={e=>{setKind(e.target.value as ReportKind);setData(undefined);setError('');setStatus('')}}>{Object.entries(reportTitles).map(([k,title])=><option key={k} value={k}>{title}</option>)}</select></label>{kind!=='inventory'&&<label>기준일<input required type="date" disabled={busy} value={day} onChange={e=>setDay(e.target.value)}/></label>}<button className="primary" disabled={busy}>{busy?'처리 중…':'보고서 생성'}</button></form>{status&&<p className="v3-status" role="status">{status}</p>}{error&&<p className="error" role="alert">{error}</p>}{data&&<><div className="report-downloads"><button disabled={busy} onClick={()=>void download('xlsx')}>Excel 다운로드</button><button disabled={busy} onClick={()=>void download('pdf')}>PDF 다운로드</button></div><h3>{data.title}</h3><p className="muted">생성 {new Date(data.created_at).toLocaleString('ko-KR')} · ID {data.report_id}<br/>출처 {data.source} · 기준일 {data.business_date||data.as_of}</p>{data.notes.map(n=><p key={n}>{n}</p>)}<p>{data.rows.length.toLocaleString()}행 · 화면은 처음 100행, 다운로드는 전체 기록</p><div className="table-scroll"><table><thead><tr>{data.columns.map(c=><th key={c}>{c}</th>)}</tr></thead><tbody>{data.rows.slice(0,100).map((row,i)=><tr key={i}>{row.map((c,j)=><td key={j}>{c??'미입력'}</td>)}</tr>)}</tbody></table></div></>}</section>
}
