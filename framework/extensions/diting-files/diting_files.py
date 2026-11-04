"""Git-native immutable Diting evidence; Python standard library, no database."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import argparse,hashlib,json,os,re,subprocess,sys,tempfile,uuid,runpy
BATCH=runpy.run_path(str(Path(__file__).resolve().parents[2]/"tools/git_batch.py"))
NAME='gonggong-diting-data'
KINDS={'request','step','message','direction_error','correction','quality_issue','rework','handoff','coverage','request_end','analysis'}
def canonical(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(v):return hashlib.sha256(canonical(v).encode()).hexdigest()
def pairs(items):
    result={}
    for k,v in items:
        if k in result:raise ValueError('Duplicate JSON field: '+k)
        result[k]=v
    return result
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'),object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
def git(repo,*args):return subprocess.run(['git','-C',str(repo),*args],capture_output=True)
def location(repo):
    repo=Path(repo).resolve();r=git(repo,'rev-parse','--show-toplevel')
    if r.returncode or Path(os.fsdecode(r.stdout).strip()).resolve()!=repo:raise ValueError('Existing Git repository root required; no directory created')
    data=repo/NAME
    if data.is_symlink() or (hasattr(data,'is_junction') and data.is_junction()):raise ValueError('Linked dataset forbidden')
    return repo,data
def atomic_new(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.diting-pending-',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8',newline='\n') as f:f.write(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
        os.link(tmp,path)
    finally:Path(tmp).unlink(missing_ok=True)
def init(repo):
    repo,data=location(repo)
    try:module=Path(__file__).resolve().relative_to(repo).as_posix()
    except ValueError:raise ValueError('Integrate this module into the target repository before initializing data')
    committed=git(repo,'show','HEAD:'+module)
    if committed.returncode or committed.stdout!=Path(__file__).read_bytes():raise ValueError('Module must be committed in target repository before dataset initialization')
    if data.exists():raise ValueError('Dataset already exists; refusing overwrite')
    data.mkdir()
    atomic_new(data/'dataset.json',{'schema_version':1,'dataset_id':str(uuid.uuid4()),'origin_framework':'gonggong','name':NAME,'storage':'immutable_event_json','created_at':datetime.now(timezone.utc).isoformat()})
    (data/'.gitattributes').write_text('* text eol=lf\n',encoding='utf-8',newline='\n')
    (data/'README.md').write_text('# 谛听需求生产数据\n\n本目录是需求产出，必须随需求合入 Git。每个事件独立 JSON；不得忽略、覆盖或删除历史记录。共工同步不得触碰此目录。规则和工具位于共工 extensions/diting-files。\n',encoding='utf-8',newline='\n')
    return {'directory':str(data),'created':True,'git_committed':False,'records':0}
def event(v):
    required={'schema_version','event_id','tenant_id','request_id','kind','occurred_at','source_ref','agent','payload','evidence_refs'}
    if not isinstance(v,dict) or not required<=v.keys() or set(v)-required-{'supersedes','sha256'}:raise ValueError('Invalid event envelope')
    for key in ['event_id','tenant_id','request_id']+(['supersedes'] if 'supersedes' in v else []):
        if not isinstance(v[key],str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,95}',v[key]):raise ValueError('Invalid path/identity: '+key)
    if v['schema_version']!=1 or v['kind'] not in KINDS:raise ValueError('Unsupported event schema/kind')
    if not isinstance(v['occurred_at'],str) or datetime.fromisoformat(v['occurred_at'].replace('Z','+00:00')).tzinfo is None:raise ValueError('Timezone timestamp required')
    if not isinstance(v['source_ref'],str) or not v['source_ref'].strip() or not isinstance(v['payload'],dict):raise ValueError('Source and payload required')
    a=v['agent']
    if not isinstance(a,dict) or set(a)!={'id','version','definition_sha256','origin'} or any(not isinstance(x,str) or not x.strip() for x in a.values()) or not re.fullmatch('[a-f0-9]{64}',a['definition_sha256']):raise ValueError('Actual agent snapshot required')
    refs=v['evidence_refs']
    if not isinstance(refs,list) or any(not isinstance(x,str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,95}',x) for x in refs) or len(set(refs))!=len(refs):raise ValueError('Invalid evidence references')
    body={k:x for k,x in v.items() if k!='sha256'};d=digest(body)
    if 'sha256' in v and v['sha256']!=d:raise ValueError('Event checksum mismatch')
    return {**body,'sha256':d}
def files(data):
    found=[]
    def fail(e):raise e
    for base,dirs,names in os.walk(data,onerror=fail,followlinks=False):
        for name in dirs+names:
            p=Path(base)/name
            if p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()):raise ValueError('Linked dataset path forbidden')
        found.extend(Path(base)/n for n in names)
    return sorted(found)
def load(repo, historical=False, cache=None):
    repo,data=location(repo)
    expected_name,expected_origin=NAME,'gonggong'
    if historical:
        data=repo/'olympus-hermes-data'
        expected_name,expected_origin='olympus-hermes-data','olympus'
        if data.is_symlink() or (hasattr(data,'is_junction') and data.is_junction()):raise ValueError('Linked historical dataset forbidden')
    allfiles=files(data);meta=read(data/'dataset.json')
    if meta.get('schema_version')!=1 or meta.get('name')!=expected_name or meta.get('origin_framework')!=expected_origin:raise ValueError('Invalid dataset manifest')
    uuid.UUID(meta['dataset_id']);records={}
    for p in allfiles:
        rel=p.relative_to(data).as_posix()
        if rel in {'dataset.json','README.md','.gitattributes'}:continue
        if not rel.startswith('events/') or not rel.endswith('.json'):raise ValueError('Unexpected/uncommitted temporary data file: '+rel)
        # Cache only successful event validation, scoped to a live caller session.
        # Exact bytes, never timestamps, decide reuse. Graph checks always run.
        content=p.read_bytes(); key_path=str(p.resolve())
        previous=cache.get(key_path) if cache is not None else None
        if previous is not None and previous[0]==content:
            raw,v=previous[1],previous[2]
        else:
            raw=json.loads(content.decode('utf-8'),object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
            v=event(raw)
            if cache is not None:cache[key_path]=(content,raw,v)
        if 'sha256' not in raw:raise ValueError('Stored checksum required')
        expected=f"events/{v['tenant_id']}/{v['request_id']}/{v['event_id']}.json"
        key=(v['tenant_id'],v['event_id'])
        if rel!=expected or key in records:raise ValueError('Event path/identity collision')
        records[key]=v
    graph(records)
    return repo,data,meta,records,allfiles
def graph(records):
    successors={}
    for key,v in records.items():
        refs=list(v['evidence_refs'])
        if 'supersedes' in v:
            parent=(v['tenant_id'],v['supersedes'])
            if parent in successors:raise ValueError('Concurrent correction fork')
            successors[parent]=key;refs.append(v['supersedes'])
            if parent not in records or records[parent]['request_id']!=v['request_id']:raise ValueError('Invalid predecessor')
        for rid in refs:
            if (v['tenant_id'],rid) not in records:raise ValueError('Missing evidence in tenant')
    visiting=set();done=set()
    def visit(key):
        if key in visiting:raise ValueError('Cyclic evidence')
        if key in done:return
        visiting.add(key);v=records[key]
        for ref in v['evidence_refs']+([v['supersedes']] if 'supersedes' in v else []):visit((v['tenant_id'],ref))
        visiting.remove(key);done.add(key)
    for key in records:visit(key)
    return successors
def merged_records(repo,records):
    records=dict(records)
    historical=Path(repo)/'olympus-hermes-data/dataset.json'
    if historical.is_file():
        _,_,_,history,_=load(repo,historical=True)
        for key,value in history.items():
            if key in records and records[key]!=value:raise ValueError('Conflicting cross-source event identity')
            records[key]=value
    graph(records)
    return records

def record(repo,input_path):
    repo,data,meta,records,_=load(repo);v=event(read(input_path));key=(v['tenant_id'],v['event_id'])
    combined=merged_records(repo,records)
    if key in combined and key not in records:
        if combined[key]!=v:raise ValueError('Conflicting cross-source event identity')
        return {'state':'recorded_file','idempotent':True,'historical_read_only':True,'git_committed':False}
    if key in records:
        if records[key]!=v:raise ValueError('Same identity with different content')
        return {'state':'recorded_file','idempotent':True,'git_committed':False}
    records[key]=v;graph(records)
    target=data/'events'/v['tenant_id']/v['request_id']/(v['event_id']+'.json')
    atomic_new(target,v)
    return {'state':'recorded_file','path':str(target),'sha256':v['sha256'],'git_committed':False}
def git_check(repo,committed=False,cache=None):
    repo,data,meta,records,allfiles=load(repo,cache=cache);problems=[]
    combined=dict(records)
    if (repo/'olympus-hermes-data/dataset.json').is_file():
        _,_,_,history,historyfiles=load(repo,historical=True,cache=cache)
        allfiles+=historyfiles
        for key,value in history.items():
            if key in combined and combined[key]!=value:raise ValueError('Conflicting cross-source event identity')
            combined[key]=value
    graph(combined)
    names={BATCH['encoded'](p,repo):p for p in allfiles}
    ignored=BATCH['ignored'](repo,list(names))
    tracked=BATCH['tracked'](repo)
    head=BATCH['objects'](repo,'HEAD',[NAME,'olympus-hermes-data'])
    for name,p in names.items():
        rel=os.fsdecode(name)
        if name in ignored:problems.append('ignored: '+rel)
        if name not in tracked:problems.append('untracked: '+rel)
        if committed and (name not in head or head[name]!=p.read_bytes()):
            problems.append('not committed current bytes: '+rel)
    for name in head:
        if not (repo/os.fsdecode(name)).is_file():problems.append('deleted history: '+os.fsdecode(name))
    if problems:raise ValueError('; '.join(problems))
    if cache is not None:
        present={str(p.resolve()) for p in allfiles}
        for key in set(cache)-present:del cache[key]
    return {'git_state':'committed' if committed else 'tracked','files':len(allfiles),'records':len(records),'remote_merge_verified':False}
def analyze(repo,tenant):
    repo,data,meta,records,allfiles=load(repo)
    sources=[{'dataset_id':meta['dataset_id'],'origin':meta['origin_framework'],'mode':'current'}]
    if (repo/'olympus-hermes-data/dataset.json').is_file():
        _,_,old,history,_=load(repo,historical=True)
        sources.append({'dataset_id':old['dataset_id'],'origin':old['origin_framework'],'mode':'read_only_historical'})
        for key,value in history.items():
            if key in records and records[key]!=value:raise ValueError('Conflicting cross-source event identity')
            records[key]=value
    superseded=graph(records)
    selected=[v for (t,_),v in sorted(records.items()) if t==tenant]
    active=[v for v in selected if (tenant,v['event_id']) not in superseded]
    try:status=git_check(repo,True)['git_state']
    except ValueError:status='not_fully_committed'
    return {'sources':sources,'dataset_id':meta['dataset_id'],'origin':'gonggong','tenant':tenant,'consumer_compatibility':['diting','gonggong'],'snapshot_sha256':digest(selected),'git_state':status,'coverage':'unknown','events':len(selected),'current_events':len(active),'by_kind':dict(Counter(v['kind'] for v in active)),'records':selected,'superseded_event_ids':sorted(k[1] for k in superseded if k[0]==tenant),'usage_totals':'not_inferred_from_event_counts'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['init','record','validate','analyze','git-check']);p.add_argument('--repo',required=True);p.add_argument('--input');p.add_argument('--tenant');p.add_argument('--require-committed',action='store_true');a=p.parse_args()
    try:
        if a.command=='init':result=init(a.repo)
        elif a.command=='record':
            if not a.input:raise ValueError('--input required')
            result=record(a.repo,a.input)
        elif a.command=='analyze':
            if not a.tenant:raise ValueError('--tenant required')
            result=analyze(a.repo,a.tenant)
        elif a.command=='git-check':result=git_check(a.repo,a.require_committed)
        else:
            _,_,meta,records,_=load(a.repo);records=merged_records(a.repo,records);result={'valid':True,'dataset_id':meta['dataset_id'],'records':len(records)}
        print(json.dumps(result,ensure_ascii=False,allow_nan=False))
    except (ValueError,OSError,KeyError,TypeError,RecursionError) as e:p.exit(1,str(e)+'\n')
