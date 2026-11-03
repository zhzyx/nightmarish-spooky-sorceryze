"""Create a review candidate with Diting reporting; never registers or approves it."""
from pathlib import Path
import argparse,json,re,runpy,sys
ROOT=Path(__file__).resolve().parents[1]
def create(root,destination,kind,cid,purpose,version='0.1.0'):
    if kind not in {'agent','skill'} or not re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*',cid) or len(cid)>63:raise ValueError('Use a lowercase component ID under 64 characters')
    if not isinstance(purpose,str) or not purpose.strip():raise ValueError('Purpose is required')
    if not re.fullmatch(r'\d+\.\d+\.\d+',version):raise ValueError('Use a semantic version')
    destination=Path(destination).resolve()
    if destination.exists():raise ValueError('Destination exists; refusing overwrite')
    entry='SKILL.md' if kind=='skill' else 'AGENT.md'
    if kind=='skill':text='---\nname: '+cid+'\ndescription: '+json.dumps(purpose,ensure_ascii=False)+'\n---\n\n'+purpose.strip()+'\n'
    else:text='# '+cid+'\n\n'+purpose.strip()+'\n\n独立 Agent，始终接受元衡控制；沿用共工治理与实际宿主委托。\n'
    text+='\n进入与交付回查共工 gonggong-check。使用随附 reporting.json，通过宿主绑定的谛听上报入口记录需求、步骤及实际用量；未知保留原因，只有落库回执才算上报。创建完成仍须审查，不产生运行权限。\n'
    meta={'kind':kind,'id':cid,'version':version,'entry':entry,'governance_root':'yuanheng','state':'candidate_pending_review','reporting':'reporting.json','binding_template':'reporting-binding.template.json'}
    destination.mkdir(parents=True)
    (destination/entry).write_text(text,encoding='utf-8')
    (destination/'component.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    api=runpy.run_path(str(root/'tools/diting-report.py'))
    profile=api['make_profile'](root,destination,meta)
    (destination/'reporting.json').write_text(json.dumps(profile,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    policy=json.loads((root/'contracts/diting-reporting.json').read_text(encoding='utf-8'))
    binding={'template':True,**{f:None for f in policy['binding_fields']}}
    (destination/meta['binding_template']).write_text(json.dumps(binding,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    api['check'](root,destination)
    return {'directory':str(destination),'state':'candidate_pending_review','reporting':'configured_not_connected','approval_granted':False}
def refresh(root,directory,version):
    owner=Path(directory).resolve();api=runpy.run_path(str(root/'tools/diting-report.py'))
    meta_file=api['inside'](owner,'component.json');meta=json.loads(meta_file.read_text(encoding='utf-8'))
    if meta.get('state')!='candidate_pending_review' or meta.get('governance_root')!='yuanheng':raise ValueError('Refresh only applies to governed review candidates')
    expected_entry={'agent':'AGENT.md','skill':'SKILL.md'}.get(meta.get('kind'))
    if not expected_entry or meta.get('entry')!=expected_entry or meta.get('reporting')!='reporting.json':raise ValueError('Refresh requires generated component file layout')
    if not version or not re.fullmatch(r'\d+\.\d+\.\d+',version) or version==meta['version']:raise ValueError('Explicit changed version required')
    target=api['inside'](owner,meta['reporting']);api['inside'](owner,meta['entry'])
    if target==meta_file:raise ValueError('Reporting profile cannot overwrite component metadata')
    meta['version']=version
    profile=api['make_profile'](root,owner,meta)
    meta_file.write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    target.write_text(json.dumps(profile,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    api['check'](root,owner)
    return {'directory':str(owner),'version':version,'state':'candidate_pending_review','approval_granted':False}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--framework-root',default=str(ROOT));p.add_argument('--kind',choices=['agent','skill']);p.add_argument('--id');p.add_argument('--purpose');p.add_argument('--version');p.add_argument('--out');p.add_argument('--refresh');a=p.parse_args()
    sys.stdout.reconfigure(encoding='utf-8');sys.stderr.reconfigure(encoding='utf-8')
    try:
        if a.refresh:result=refresh(Path(a.framework_root).resolve(),a.refresh,a.version)
        else:
            if not all((a.kind,a.id,a.purpose,a.out)):raise ValueError('Creation requires --kind --id --purpose --out')
            result=create(Path(a.framework_root).resolve(),a.out,a.kind,a.id,a.purpose,a.version or '0.1.0')
        print(json.dumps(result,ensure_ascii=False))
    except (ValueError,KeyError,TypeError,OSError) as e:print(str(e),file=sys.stderr);sys.exit(1)
