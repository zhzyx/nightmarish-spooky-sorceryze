"""Verify local package integrity. Does not authenticate host/user authority."""
from pathlib import Path
import hashlib,json,sys,subprocess

def local(root,p):
    if not isinstance(p,str) or Path(p).is_absolute() or any(c in p for c in '\0\r\n'):
        raise ValueError('Invalid framework path')
    f=(root/p).resolve();f.relative_to(root.resolve())
    if not f.is_file():raise ValueError('Missing file: '+p)
    return f

def fingerprint(root,paths,hashes=None):
    if len(paths)!=len(set(paths)):raise ValueError('Duplicate candidate file')
    records=[{'path':p,'sha256':(hashes[p] if hashes is not None else hashlib.sha256(local(root,p).read_bytes()).hexdigest())} for p in sorted(paths)]
    return hashlib.sha256(''.join(x['path']+'\0'+x['sha256']+'\n' for x in records).encode()).hexdigest(),records

def verify(root,candidate=False):
    import runpy
    hashes=runpy.run_path(str(root/'tools/package_integrity.py'))['check'](root,return_inventory=True)
    read=lambda p:json.loads(local(root,p).read_text(encoding='utf-8'))
    m=read('framework-manifest.json');lock=read('foundation.lock.json')
    if hashes['FOUNDATION.md']!=lock['sha256']:raise ValueError('Frozen foundation changed')
    for source in m['upstream_files']:
        if hashes[source['path']]!=source['sha256']:raise ValueError('Upstream changed')
    ids=[a['id'] for a in m['agents']]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate agent identity')
    actual={p.parent.name for p in (root/'agents').glob('*/agent.json')}
    if actual!=set(ids):raise ValueError('Unregistered/missing agent')
    for a in m['agents']:
        meta=read(a['manifest'])
        for key in ['id','version','entry','governance_root','admission_pass']:
            if meta[key]!=a[key]:raise ValueError('Agent metadata mismatch: '+key)
        if meta['kind']!='independent_agent' or meta['governance_root']!='yuanheng' or meta['path_base']!='framework_root':raise ValueError('Invalid agent governance')
        for key in ['entry','foundation','agent_template','review_skill','context_loader']:local(root,meta[key])
        for p in meta['supporting_skills']:local(root,p)
        digest,_=fingerprint(root,a['candidate_files'],hashes)
        if digest!=a['candidate_digest']:raise ValueError('Candidate content changed: '+a['id'])
    skills=[s['path'] for s in m['skills']]+['upstream/yuanheng/skills/yuanheng-organize/SKILL.md']
    actual_skills={p.relative_to(root).as_posix() for p in root.rglob('SKILL.md')}
    if actual_skills!=set(skills):raise ValueError('Unexpected/missing skill entry')
    for s in skills:local(root,s)
    # This is a fresh, private parent-to-child snapshot, never a disk cache or permit.
    report_check=subprocess.run(['node',str(local(root,'tools/verify_metadata.mjs')),str(root.resolve()),'candidate' if candidate else 'formal'],input=json.dumps(hashes),capture_output=True,text=True,encoding='utf-8',timeout=120)
    if report_check.returncode:raise ValueError(report_check.stderr.strip() or 'Metadata check failed')
    return {'framework_version':m['version'],'agents':ids,'skills_including_upstream':len(skills),'foundation_unchanged':True,'mode':'candidate' if candidate else 'approved_file_integrity','host_authority_authenticated':False}

if __name__=='__main__':
    try:
        if sys.argv[1:] not in ([],['--candidate']):raise ValueError('Usage: verify_framework.py [--candidate]')
        print(json.dumps(verify(Path(__file__).resolve().parents[1],'--candidate' in sys.argv),ensure_ascii=False))
    except (ValueError,KeyError,OSError,TypeError) as error:
        print(str(error),file=sys.stderr);sys.exit(1)
