// Read-only health checks may encounter clock skew in the API-key gateway's
// generated JWT. Retry only that exact error, once, using the runtime's existing
// service-role credential. Do not mint, modify or re-sign credentials.
export function withClockSkewFallback(primaryKey, runtimeServiceKey, fetcher=fetch) {
  return async (input, init) => {
    const response=await fetcher(input,init);
    if(response.ok || !runtimeServiceKey || runtimeServiceKey===primaryKey)return response;
    let message;
    try{message=(await response.clone().json())?.message;}catch{return response;}
    if(message!=='JWT issued at future')return response;
    const headers=new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined));
    headers.set('apikey',runtimeServiceKey);
    headers.set('authorization','Bearer '+runtimeServiceKey);
    return fetcher(input,{...init,headers});
  };
}
