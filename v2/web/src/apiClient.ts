import {apiPath} from './apiPath';
export class ApiError extends Error {constructor(message:string,public status:number){super(message);this.name='ApiError'}}
export function accessToken(){try{return sessionStorage.getItem('needsfood_access_token')||''}catch{return ''}}
export async function apiRequest<T>(path:string,init:RequestInit={},token=accessToken()):Promise<T>{
 const headers=new Headers(init.headers);if(!headers.has('Authorization')&&token)headers.set('Authorization','Bearer '+token);if(typeof init.body==='string'&&!headers.has('Content-Type'))headers.set('Content-Type','application/json');
 const controller=new AbortController();const abort=()=>controller.abort();init.signal?.addEventListener('abort',abort,{once:true});if(init.signal?.aborted)controller.abort();const timer=setTimeout(abort,90000);
 try{const r=await fetch(apiPath('/api'+path),{...init,headers,credentials:'same-origin',signal:controller.signal});const data=await r.json().catch(()=>null);if(!r.ok)throw new ApiError(typeof data?.detail==='string'?data.detail:`요청 실패 (${r.status})`,r.status);if(!data)throw new ApiError('서버 응답 형식을 확인할 수 없습니다.',502);return data as T}
 catch(e){if(controller.signal.aborted&&!init.signal?.aborted)throw new Error('서버 응답 시간이 초과되었습니다. 연결 상태를 확인하고 다시 시도하세요.');throw e}
 finally{clearTimeout(timer);init.signal?.removeEventListener('abort',abort)}
}
