/** Resolve the API beside the deployed entrypoint, including /work/:id deep links. */
export function apiPath(path:string):string{
 const script=document.querySelector<HTMLScriptElement>('script[type="module"][src]');
 const asset=script?new URL(script.src,location.href).pathname:'';
 const marker=asset.includes('/assets/')?'/assets/':asset.includes('/src/')?'/src/':null;
 const base=marker?asset.slice(0,asset.indexOf(marker)+1):new URL('.',location.href).pathname;
 return base+path.replace(/^\//,'');
}
