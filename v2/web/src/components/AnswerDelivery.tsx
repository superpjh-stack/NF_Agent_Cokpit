import type {Answer} from '../types';
import {cargoLabels,deliveryCargo} from './deliveryTheme';
import './AnswerDelivery.css';
export default function AnswerDelivery({answer,question}:{answer:Answer;question:string}){
 // Show only an excerpt of returned text; no extra model call or invented conclusion.
 const text=(answer.summary||answer.voice_summary||answer.text||'').trim();
 const line=text.split(/\n\s*\n/)[0];
 const chars=Array.from(line);const preview=chars.length>200?chars.slice(0,200).join('')+'…':line;
 return <section className="answer-delivery" aria-label="도착한 답변 요약">
  <svg className="answer-parcel" viewBox="0 0 36 36" fill="none" aria-hidden="true"><path d="m7 16 11 5 11-5v13l-11 5-11-5z" fill="#ddc39a"/><path d="M18 21v13" stroke="#b69669"/><path className="answer-parcel-lid" d="m7 16 11-5 11 5-11 5z" fill="#efddbb" stroke="#c6a779" strokeLinejoin="round"/><path className="answer-parcel-spark" d="M18 4v4M8 7l3 3m17-3-3 3" stroke="#8bab75" strokeWidth="1.6" strokeLinecap="round"/></svg>
  <div><span className="answer-delivery-label">답변 도착 <span>· {cargoLabels[deliveryCargo(question)]}</span></span><p className="answer-delivery-preview">{preview||'상세 답변과 근거를 확인하세요.'}</p><small>{answer.demo_data?'샘플 자료 기준 · ':''}답변 요약 · 전체 내용과 근거는 아래에서 확인하세요.</small></div>
 </section>;
}
