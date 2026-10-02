let accessToken = '';
let refreshing: Promise<any> | null = null;
export function setToken(value: string) { accessToken = value; }
async function send(path: string, init: RequestInit = {}): Promise<any> {
 const headers = new Headers(init.headers);
 if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`);
 if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json');
 return fetch(path, {...init, headers, credentials:'include'});
}
export async function refresh(): Promise<any> {
 if (!refreshing) refreshing = (async () => {
  const res = await send('/api/auth/refresh', {method:'POST'});
  const data = await res.json();
  if (!res.ok) throw new Error('Please sign in again');
  setToken(data.access_token); return data;
 })().finally(() => {refreshing = null;});
 return refreshing;
}
export async function api(path: string, init: RequestInit = {}): Promise<any> {
 let res = await send(path, init);
 if (res.status === 401 && !path.startsWith('/api/auth/')) {
  try { await refresh(); res = await send(path, init); }
  catch {setToken(''); window.dispatchEvent(new Event('session-expired')); throw new Error('Session expired. Please sign in.');}
 }
 const data = await res.json();
 if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : data.detail?.map((e:any)=>e.msg).join('; ') || 'Request failed');
 return data;
}
export function download(name:string, value:any) {
 const url = URL.createObjectURL(new Blob([JSON.stringify(value,null,2)], {type:'application/json'}));
 const a = document.createElement('a'); a.href=url; a.download=name; a.click(); URL.revokeObjectURL(url);
}
