export type DeliveryCargo='meal'|'ingredients'|'quality'|'parcel';
/** Decorative keyword routing only; never changes the data query. */
export function deliveryCargo(question:string):DeliveryCargo{
 const quality=/품질|검식|검사|위생|CCP|HACCP|불량/i.test(question);
 const ingredients=/재고|원료|식재료|입고|자재|부족/.test(question);
 const meal=/생산|조리|메뉴|급식|도시락|출하|납품/.test(question);
 if([quality,ingredients,meal].filter(Boolean).length>1)return 'parcel';
 return quality?'quality':ingredients?'ingredients':meal?'meal':'parcel';
}
export const cargoLabels:Record<DeliveryCargo,string>={meal:'도시락',ingredients:'식재료 상자',quality:'검사 체크리스트',parcel:'답변 상자'};
export function CargoMark({kind}:{kind:DeliveryCargo}){
 if(kind==='meal')return <><rect x="4" y="14" width="13" height="10" rx="2" fill="#e3a465"/><path d="M4 17h13m-8 0v6m4-6v6" stroke="#fff2d6" strokeWidth="1.2"/><path d="M8 13h5" stroke="#aa7043" strokeWidth="1.5" strokeLinecap="round"/></>;
 if(kind==='ingredients')return <><rect x="4" y="16" width="13" height="8" rx="1.5" fill="#c4a16c"/><path d="M4 19h13m-10-3v8m7-8v8" stroke="#ecd7ad" strokeWidth="1"/><path d="M8 17c-7-6 2-8 2-1 0-8 9-5 3 1" fill="#6e9c60"/><path d="m13 16 2-5" stroke="#e0a457" strokeWidth="2" strokeLinecap="round"/></>;
 if(kind==='quality')return <><rect x="5" y="12" width="11" height="13" rx="1.5" fill="#f1f3df" stroke="#9bad8f" strokeWidth="1"/><rect x="8" y="11" width="5" height="3" rx="1" fill="#779678"/><path d="m7 18 1.5 1.5L11 16m1 2h2m-7 4h7" stroke="#608965" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/></>;
 return <><rect x="4" y="14" width="13" height="10" rx="2" fill="#c6a36c"/><path d="M10.5 14v4" stroke="#f6e5c3" strokeWidth="2"/></>;
}
