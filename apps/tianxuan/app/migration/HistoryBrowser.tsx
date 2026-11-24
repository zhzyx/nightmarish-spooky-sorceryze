"use client";

import { useEffect, useState } from "react";
import { authHeaders } from "@/lib/auth";
import styles from "./page.module.css";

type Summary = { source_id: string; kind: string; title?: string; path?: string };
type Row = Summary & { content: Record<string, unknown>; relations: string[]; truncated?: boolean };
type Page<T> = { items: T[]; total: number };
type Detail = { record: Row; comments: Page<Row>; reverse: Page<Summary>; document?: { text?: string } };
type Commit = { oid: string; subject: string; author: string };
type History = { items: Commit[]; next_offset: number | null };
type Query = Record<string,string>;
const size = 10;

function useRead<T>(url: string, actor: string) {
  const [result, setResult] = useState<{url: string; data?: T; failed?: boolean}>();
  useEffect(() => {
    if (!url) return;
    const request = new AbortController();
    fetch(url, { headers: authHeaders(actor), cache: "no-store", signal: request.signal })
      .then(async r => { if (!r.ok) throw Error(); return await r.json() as T; })
      .then(data => { if (!request.signal.aborted) setResult({ url, data }); })
      .catch(() => { if (!request.signal.aborted) setResult({ url, failed: true }); });
    return () => request.abort();
  }, [actor,url]);
  return result?.url === url ? result : undefined;
}

function FullBody({base,actor,zh}: {base:string;actor:string;zh:boolean}) {
  const [offset,setOffset]=useState<number>();
  const length=16384;
  const result=useRead<{text:string;next_offset:number|null;total:number}>(offset===undefined?"":base+"&offset="+offset+"&limit="+length,actor);
  if(offset===undefined) return <button onClick={()=>setOffset(0)}>{zh?"分页阅读完整正文":"Read full text in pages"}</button>;
  return <div>{result?.data && <><pre className={styles.body}>{result.data.text}</pre>
    <div className={styles.paging}><button disabled={offset===0} onClick={()=>setOffset(Math.max(0,offset-length))}>{zh?"上一段":"Previous section"}</button>
    <span>{offset+1} / {result.data.total}</span><button disabled={result.data.next_offset==null} onClick={()=>setOffset(result.data?.next_offset??offset)}>{zh?"下一段":"Next section"}</button></div></>}
    {result?.failed && <p role="alert">{zh?"无法读取正文。":"Could not read full text."}</p>}</div>;
}

export default function HistoryBrowser({project, revision, actor, zh}: {project:string; revision:string; actor:string; zh:boolean}) {
  const t = (a:string,b:string) => zh ? a : b;
  const endpoint = (action:string, args:Query) => "/api/v1/migration/history/"+action+"?"+new URLSearchParams({project,revision,...args});
  const [term,setTerm]=useState(""), [query,setQuery]=useState(""), [offset,setOffset]=useState(0);
  const [id,setId]=useState(""), [related,setRelated]=useState(0);
  const [code,setCode]=useState(false), [path,setPath]=useState(""), [ref,setRef]=useState("");
  const [git,setHistoryQuery]=useState<Query>({}), [gitOffset,setGitOffset]=useState(0), [file,setFile]=useState<Query>();
  const [downloadError,setDownloadError]=useState(false);
  const search=useRead<Page<Summary>>(code?"":endpoint("search",{query,offset:String(offset),limit:String(size)}),actor);
  const detail=useRead<Detail>(!code && id?endpoint("detail",{source_id:id,offset:String(related),limit:String(size)}):"",actor);
  const history=useRead<History>(code?endpoint("commits",{...git,offset:String(gitOffset),limit:String(size)}):"",actor);
  const contents=useRead<{text:string}>(code && file?endpoint("file",file):"",actor);
  const view=(source:string)=>{setId(source);setRelated(0);setDownloadError(false);};
  const record=detail?.data?.record;
  function openRelation(source: string) {
    const commit = /^github:([^/]+\/[^/]+)\/commit\/([0-9a-f]{40}|[0-9a-f]{64})$/i.exec(source);
    if (!commit || !record?.source_id.startsWith("github:"+commit[1]+"/")) {
      view(source);
      return;
    }
    const oid = commit[2];
    setRef(oid);
    setPath("");
    setHistoryQuery({commit: oid});
    setGitOffset(0);
    setFile(undefined);
    setCode(true);
  }
  const navigation=(start:number,more:boolean,go:(n:number)=>void)=><div className={styles.paging}>
    <button disabled={start===0} onClick={()=>go(Math.max(0,start-size))}>{t("上一页","Previous")}</button>
    <span>{Math.floor(start/size)+1}</span><button disabled={!more} onClick={()=>go(start+size)}>{t("下一页","Next")}</button></div>;
  const button=(r:Summary)=><button type="button" onClick={()=>view(r.source_id)}>{r.title || r.path || r.source_id}</button>;
  async function download() {
    setDownloadError(false);
    try {
      const r=await fetch(endpoint("attachment",{source_id:id}),{headers:authHeaders(actor),cache:"no-store"});
      if(!r.ok) throw Error();
      const href=URL.createObjectURL(await r.blob()), anchor=document.createElement("a");
      anchor.href=href;anchor.download="attachment-"+id.split("/").pop();anchor.click();setTimeout(()=>URL.revokeObjectURL(href),1000);
    } catch {setDownloadError(true);}
  }
  return <section className={styles.panel}><h2>{t("历史内容","Historical content")}</h2>
    <div className={styles.paging}><button aria-pressed={!code} onClick={()=>setCode(false)}>{t("来源记录","Source records")}</button>
    <button aria-pressed={code} onClick={()=>setCode(true)}>{t("代码历史","Code history")}</button></div>
    {!code ? <>
      <form onSubmit={e=>{e.preventDefault();setQuery(term.trim());setOffset(0);view("");}}>
        <label>{t("编号、标题或路径","Number, title or path")}<input value={term} onChange={e=>setTerm(e.target.value)} /></label>
        <button>{t("搜索","Search")}</button></form>
      {search?.data && <><ul>{search.data.items.map(r=><li key={r.source_id}>{button(r)} <small>{r.kind}</small></li>)}</ul>
      <p>{search.data.total} {t("条记录","records")}</p>{navigation(offset,offset+size<search.data.total,setOffset)}</>}
      {record && detail?.data && <article><h3>{String(record.content.title || record.content.path || record.source_id)}</h3>
        <small>{record.source_id}</small><pre className={styles.body}>{detail.data.document?.text ?? String(record.content.body ?? JSON.stringify(record.content,null,2))}</pre>
        {record.truncated && <FullBody key={record.source_id} base={endpoint("body",{source_id:record.source_id})} actor={actor} zh={zh} />}
        {record.kind==="attachment" && <button onClick={download}>{t("下载归档附件","Download archived attachment")}</button>}
        {record.relations.length>0 && <><h4>{t("关联来源","Related sources")}</h4><ul>{record.relations.map(r=><li key={r}><button type="button" onClick={()=>openRelation(r)}>{r}</button></li>)}</ul></>}
        <h4>{t("评论","Comments")} ({detail.data.comments.total})</h4>
        {detail.data.comments.items.map(r=><div key={r.source_id}>{button(r)}<pre className={styles.body}>{String(r.content.body ?? "")}</pre>{r.truncated && <FullBody base={endpoint("body",{source_id:r.source_id})} actor={actor} zh={zh} />}</div>)}
        <h4>{t("引用此记录","Referenced by")} ({detail.data.reverse.total})</h4><ul>{detail.data.reverse.items.map(r=><li key={r.source_id}>{button(r)}</li>)}</ul>
        {navigation(related,related+size<Math.max(detail.data.comments.total,detail.data.reverse.total),setRelated)}
      </article>}
    </> : <>
      <form onSubmit={e=>{e.preventDefault();const args:Query={};if(path.trim())args.path=path.trim();if(ref.trim())args.commit=ref.trim();setHistoryQuery(args);setGitOffset(0);setFile(args.path && args.commit?args:undefined);}}>
        <label>{t("仓库内文件路径","Repository file path")}<input value={path} onChange={e=>setPath(e.target.value)} /></label>
        <label>{t("原提交（可选）","Original commit (optional)")}<input value={ref} onChange={e=>setRef(e.target.value)} /></label>
        <button>{t("查看历史","View history")}</button></form>
      {history?.data && <><ul>{history.data.items.map(c=><li key={c.oid}><strong>{c.subject}</strong> <small>{c.author} · {c.oid}</small>
        {git.path ? <button onClick={()=>setFile({commit:c.oid,path:git.path})}>{t("读取此版本","Read this revision")}</button> : <button onClick={()=>setRef(c.oid)}>{t("选择此提交","Select commit")}</button>}</li>)}</ul>
        {history.data.items.length===0 && <p>{t("没有匹配的提交","No matching commits")}</p>}
        {navigation(gitOffset,history.data.next_offset!=null,setGitOffset)}</>}
      {contents?.data && file && <><h3>{file.path}</h3><small>{file.commit}</small><pre className={styles.body}>{contents.data.text}</pre></>}
    </>}
    {(code ? (!history || (file && !contents)) : (!search || (id && !detail))) && <p role="status">{t("正在读取归档…","Reading archive…")}</p>}
    {(code?(history?.failed || contents?.failed):(search?.failed || detail?.failed || downloadError)) && <p role="alert">{t("无法读取所选归档内容。","Could not read the selected archive content.")}</p>}
  </section>;
}
