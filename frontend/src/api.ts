export type Citation={document_id:string;title:string;chunk_id:string;excerpt:string;score:number};
export type Answer={answer:string;citations:Citation[];conversation_id:string;trace_id:string;grounded:boolean;latency_ms:number};
export async function ask(question:string,department:string):Promise<Answer>{
  const response=await fetch("/api/v1/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question,filters:department==="all"?{}:{department}})});
  if(!response.ok) throw new Error(await response.text());
  return response.json();
}
export async function upload(file:File,department:string){
  const body=new FormData();body.append("file",file);body.append("department",department);
  const response=await fetch("/api/v1/documents",{method:"POST",body});
  if(!response.ok) throw new Error(await response.text());
  return response.json();
}
