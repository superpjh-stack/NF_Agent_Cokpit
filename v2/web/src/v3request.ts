import {apiRequest} from './apiClient';
export function request<T>(token:string,path:string,options:RequestInit={}){return apiRequest<T>(path,options,token)}
