"""Local customization registry and review-candidate exports; never modifies Gonggong."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,re,sys,zipfile

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def local(root,relative):
    p=Path(relative)
    if p.is_absolute() or '..' in p.parts or not relative or '\\' in relative:raise ValueError('Use repository-relative forward-slash paths')
    out=root/p;resolved=out.resolve();resolved.relative_to(root)
    for part in [out,*list(out.parents)[:len(p.parts)-1]]:
        if part.is_symlink() or (hasattr(part,'is_junction') and part.is_junction()):raise ValueError('Linked paths forbidden')
    if not out.exists():raise ValueError('Missing path: '+relative)
    return out
def files(root,folder):
    result={}
    for p in sorted(folder.rglob('*')):
        rel=p.relative_to(root).as_posix()
        if '__pycache__' in p.parts or p.suffix=='.pyc':continue
        local(root,rel)
        if p.is_file():result[rel]=sha(p.read_bytes())
    if not result:raise ValueError('Empty component')
    return result
def registry(root):
    r=read(root/'customizations/registry.json');seen=set();paths=[]
    if r.get('schema_version')!=1 or r.get('owner')!='olympus':raise ValueError('Invalid registry')
    for c in r['components']:
        if not re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*',c['id']) or c['id'] in seen:raise ValueError('Invalid/duplicate component ID')
        seen.add(c['id'])
        if c['ownership']!='olympus_customization':raise ValueError('Invalid ownership')
        if c['path']!='customizations/components/'+c['id'] and not (c['id']=='hermes-file-data' and c['path']=='Olympus/extensions/hermes-files' and c.get('placement')=='legacy_preserved'):raise ValueError('Customization cannot claim shared framework paths')
        for k in ['version','framework_dependency','validation','rollback']:
            if not isinstance(c[k],str) or not c[k].strip():raise ValueError('Missing '+k)
        p=local(root,c['path'])
        if not p.is_dir() or any(p==x or x in p.parents or p in x.parents for x in paths):raise ValueError('Overlapping component ownership')
        paths.append(p);files(root,p)
    return r
def verify_proposal(p):
    digest=p.get('candidate_sha256');body={k:v for k,v in p.items() if k!='candidate_sha256'}
    if p.get('status')!='pending_gonggong_confirmation' or p.get('approval') is not None or digest!=sha(canonical(body).encode()):raise ValueError('Invalid candidate status or fingerprint')
    return p
def validate(root):
    r=registry(root);count=0
    for p in (root/'customizations/feedback').glob('*.json'):verify_proposal(read(p));count+=1
    return {'valid':True,'components':len(r['components']),'feedback_candidates':count,'auto_adoption':False}
def propose(root,cid,pid,details):
    if not re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*',pid):raise ValueError('Invalid proposal ID')
    components=registry(root)['components'];c=next((c for c in components if c['id']==cid),None)
    if not c:raise ValueError('Unregistered customization')
    for k in ['problem','local_scope','generalization','benefit','risks','rollback']:
        if not isinstance(details.get(k),str) or not details[k].strip():raise ValueError('Missing proposal detail: '+k)
    evidence=details.get('evidence')
    if not isinstance(evidence,list) or any(not isinstance(x,str) for x in evidence):raise ValueError('Evidence must be explicit paths')
    records=files(root,local(root,c['path']))
    for p in evidence:
        f=local(root,p)
        if not f.is_file():raise ValueError('Evidence must be individual files')
        records[p]=sha(f.read_bytes())
    p={'schema_version':1,'id':pid,'origin':'olympus','target':'gonggong','status':'pending_gonggong_confirmation','approval':None,'created_at':datetime.now(timezone.utc).isoformat(),'component':c,'framework_baseline':read(root/'Olympus/framework-manifest.json')['version'],'details':details,'files':records}
    p['candidate_sha256']=sha(canonical(p).encode());dest=root/'customizations/feedback'/(pid+'.json');dest.parent.mkdir(exist_ok=True)
    with dest.open('x',encoding='utf-8',newline='\n') as f:json.dump(p,f,ensure_ascii=False,indent=2);f.write('\n')
    return {'candidate':dest.relative_to(root).as_posix(),'status':p['status'],'candidate_sha256':p['candidate_sha256']}
def export(root,pid,dest):
    if not re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*',pid):raise ValueError('Invalid proposal ID')
    path=local(root,'customizations/feedback/'+pid+'.json');p=verify_proposal(read(path));payload={}
    for rel,h in p['files'].items():
        b=local(root,rel).read_bytes()
        if sha(b)!=h:raise ValueError('Candidate snapshot stale; create a new proposal: '+rel)
        payload[rel]=b
    with zipfile.ZipFile(dest,'x',zipfile.ZIP_DEFLATED) as z:
        z.writestr('proposal.json',path.read_bytes())
        for rel,b in payload.items():z.writestr('snapshot/'+rel,b)
    return {'export':str(dest),'candidate_sha256':p['candidate_sha256'],'status':p['status'],'upstream_framework_modified':False}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['validate','propose','export']);p.add_argument('--repo',default='.');p.add_argument('--component');p.add_argument('--id');p.add_argument('--input');p.add_argument('--out');a=p.parse_args();root=Path(a.repo).resolve()
    try:
        if a.command=='validate':r=validate(root)
        elif a.command=='propose':r=propose(root,a.component,a.id,read(Path(a.input)))
        else:r=export(root,a.id,Path(a.out))
        print(json.dumps(r,ensure_ascii=False))
    except (ValueError,OSError,KeyError,TypeError) as e:p.exit(1,str(e)+'\n')
