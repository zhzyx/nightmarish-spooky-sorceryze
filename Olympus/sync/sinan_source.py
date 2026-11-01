"""Reconcile the separately registered Gonggong Sinan module with the active base."""
import json,hashlib,os
from pathlib import Path
def merge(raw,binding):
    f=Path(os.environ.get('GONGGONG_SINAN_FRAMEWORK_SOURCE') or binding['framework']).resolve()
    impl=Path(os.environ.get('GONGGONG_SINAN_IMPLEMENTATION_SOURCE') or binding['implementation']).resolve()
    read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    sha=lambda b:hashlib.sha256(b).hexdigest()
    def local(root,rel):
        p=(root/rel).resolve();p.relative_to(root)
        if not p.is_file():raise ValueError('Missing Sinan source: '+rel)
        return p
    registry=read(f/'framework-manifest.json')
    registered=next((m for m in registry.get('modules',[]) if m['id']=='sinan'),None)
    if not registered:raise ValueError('Sinan is not registered in its source framework')
    module=read(local(f,registered['manifest']))
    admission=read(local(f,registered['admission_pass']))
    approval=read(impl/'review-pass.json')
    if admission['status']!='approved' or approval['status']!='approved':raise ValueError('Sinan source registration is not approved')
    evidence={}
    for label,root,record in [('registration',f,admission),('implementation',impl,approval)]:
        for item in record['subject']['version_or_digest']['files']:
            content=local(root,item['path']).read_bytes()
            if sha(content)!=item['sha256']:raise ValueError('Sinan source evidence changed: '+item['path'])
            evidence[label+'/'+item['path']]=content
    if registered['version']!=module['version'] or module['version']!=approval['subject']['version_or_digest']['version']:raise ValueError('Sinan version mismatch')
    base=json.loads(raw['framework-manifest.json'])
    if sha((f/'FOUNDATION.md').read_bytes())!=base['foundation_sha256']:raise ValueError('Sinan foundation differs from current base')
    module_files=['modules/sinan/module.json','skills/work-order-coordination/SKILL.md','skills/work-order-coordination/runtime-ref.json','specs/work-order-management.md','reviews/sinan-admission.json','reviews/work-order-coordination-admission.json']
    for rel in module_files:
        b=local(f,rel).read_bytes()
        if rel in raw and raw[rel]!=b:raise ValueError('Conflicting Sinan registration in current base: '+rel)
        raw[rel]=b;evidence['registration/'+rel]=b
    for rel in ['coordinator.mjs','registry.json','test/coordinator.test.mjs']:
        raw['modules/sinan/'+rel]=local(impl,rel).read_bytes()
    evidence['registration/framework-manifest.json']=(f/'framework-manifest.json').read_bytes()
    evidence['implementation/review-pass.json']=(impl/'review-pass.json').read_bytes()
    base['modules']=[m for m in base.get('modules',[]) if m['id']!='sinan']+[registered]
    skill=next(s for s in registry['skills'] if s['name']=='work-order-coordination').copy()
    skill.update(version=module['version'],reporting='skills/work-order-coordination/reporting.json')
    base['skills']=[s for s in base['skills'] if s['name']!='work-order-coordination']+[skill]
    spec=next(s for s in registry['specifications'] if s['path']=='specs/work-order-management.md')
    base['specifications']=[s for s in base['specifications'] if s['path']!=spec['path']]+[spec]
    raw['framework-manifest.json']=(json.dumps(base,ensure_ascii=False,indent=2)+'\n').encode()
    return evidence
