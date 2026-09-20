import {FormEvent,useState} from "react";
import ReactMarkdown from "react-markdown";
import {BookOpen,Database,FileUp,Send,ShieldCheck,Sparkles} from "lucide-react";
import {Answer,ask,upload} from "./api";

const suggestions=["When must travel claims be filed?","Can I share my OTP with support?","Which claims require manager approval?"];

export default function App(){
  const [question,setQuestion]=useState("");const [department,setDepartment]=useState("all");
  const [result,setResult]=useState<Answer|null>(null);const [loading,setLoading]=useState(false);const [error,setError]=useState("");
  async function submit(e:FormEvent){e.preventDefault();if(!question.trim())return;setLoading(true);setError("");
    try{setResult(await ask(question,department));}catch(e){setError(e instanceof Error?e.message:"Request failed");}finally{setLoading(false);}}
  async function ingest(file:File){setError("");try{await upload(file,department==="all"?"general":department);alert("Document indexed successfully");}catch(e){setError(e instanceof Error?e.message:"Upload failed");}}
  return <div className="shell">
    <aside><div className="brand"><Sparkles size={22}/> ATLAS</div><p className="eyebrow">Enterprise Knowledge</p>
      <nav><button className="active"><BookOpen/>Ask knowledge</button><button><Database/>Sources</button><label className="upload"><FileUp/>Upload document<input type="file" accept=".txt,.md" onChange={e=>e.target.files?.[0]&&ingest(e.target.files[0])}/></label></nav>
      <div className="security"><ShieldCheck/><div><strong>Secure retrieval</strong><span>Tenant isolated · PII protected</span></div></div>
    </aside>
    <main><header><div><p className="eyebrow">Workspace / Copilot</p><h1>Ask your company knowledge</h1></div><div className="status"><i/>Systems operational</div></header>
      <section className="hero"><div className="orb"><Sparkles/></div><h2>What can I help you find?</h2><p>Answers are grounded in approved documents and include source-level citations.</p>
        <form onSubmit={submit}><textarea value={question} onChange={e=>setQuestion(e.target.value)} placeholder="Ask about policies, processes, or internal documentation..." />
          <div className="composer"><select value={department} onChange={e=>setDepartment(e.target.value)}><option value="all">All departments</option><option value="finance">Finance</option><option value="security">Security</option><option value="hr">Human Resources</option></select><button disabled={loading}>{loading?"Searching...":<><Send size={17}/>Ask Atlas</>}</button></div></form>
        <div className="suggestions">{suggestions.map(x=><button key={x} onClick={()=>setQuestion(x)}>{x}</button>)}</div>
      </section>
      {error&&<div className="error">{error}</div>}
      {result&&<section className="answer"><div className="answer-head"><span>Verified answer</span><small>{result.latency_ms} ms · {result.grounded?"Grounded":"Review needed"}</small></div><ReactMarkdown>{result.answer}</ReactMarkdown>
        <h3>Sources</h3><div className="sources">{result.citations.map((c,i)=><article key={c.chunk_id}><b>{i+1}</b><div><strong>{c.title}</strong><p>{c.excerpt}</p><small>Relevance {Math.round(c.score*100)}%</small></div></article>)}</div>
        <footer>Trace ID: {result.trace_id}</footer></section>}
    </main>
  </div>
}
