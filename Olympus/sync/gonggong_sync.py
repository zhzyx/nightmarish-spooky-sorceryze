"""Deterministic, complete Gonggong -> Olympus distribution rebuild and drift check."""
from pathlib import Path
import argparse,ast,hashlib,io,json,os,subprocess,sys,zipfile
ADAPTERS=['sync/gonggong_sync.py','sync/read_hermes.py','sync/POLICY.md','sync/names.json','sync/sinan_source.py']
REPORTS={'sync/verification.json'}
EXEMPT='extensions/hermes-files/'
def adapters_at(root):
    result={p:(root/p).read_bytes() for p in ADAPTERS}
    extension=inventory(root/EXEMPT)
    if not {'README.md','hermes_files.py','event.schema.json'}<=extension.keys():raise ValueError('Independent Hermes file module missing')
    result.update({EXEMPT+p:b for p,b in extension.items()})
    return result
def encoded(v):return (json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def inventory(root):
    result={}
    def failed(error):raise error
    for base,dirs,files in os.walk(root,followlinks=False,onerror=failed):
        dirs[:]=sorted(d for d in dirs if d not in {'.git','__pycache__'})
        for name in dirs+files:
            p=Path(base)/name
            if p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()):raise ValueError('Linked source/target forbidden: '+str(p))
        for name in sorted(files):
            if name.endswith('.pyc'):continue
            p=Path(base)/name;result[p.relative_to(root).as_posix()]=p.read_bytes()
    return result
def source_root(source):
    p=Path(source).resolve()
    if p.is_file():
        pointer=json.loads(p.read_text(encoding='utf-8'));r=(p.parent/pointer['root']).resolve()
        r.relative_to(p.parent)
        p=r
    if not (p/'framework-manifest.json').is_file():raise ValueError('Upstream unavailable')
    return p
def expected(source,adapters,sinan_source):
    raw=inventory(source);pairs=json.loads(adapters['sync/names.json'])
    original_raw=dict(raw)
    base_hashes={p:sha(b) for p,b in raw.items()}
    namespace={};exec(compile(adapters['sync/sinan_source.py'],'sinan_source.py','exec'),namespace)
    evidence=namespace['merge'](raw,sinan_source)
    def tr(s):
        for a,b in pairs:s=s.replace(a,b)
        return s
    out={}
    for p,b in raw.items():
        if p.startswith('reviews/'):continue
        target=tr(p)
        if target in out or target.startswith('sync/') or target.startswith(EXEMPT):raise ValueError('Mapping/adapter/exemption collision: '+target)
        if p.endswith('provenance.json'):out[target]=b;continue
        try:out[target]=tr(b.decode('utf-8').replace('\r\n','\n')).encode()
        except UnicodeDecodeError:out[target]=b
    out.update(adapters)
    def get(p):return json.loads(out[p])
    def put(p,v):out[p]=encoded(v)
    def append(p,s):out[p]+=s.encode()
    # Explicitly enumerated distribution adapter hooks, never silent arbitrary patches.
    def patch(p,old,new):
        s=out[p].decode()
        if s.count(old)!=1:raise ValueError('Upstream hook changed; adapter review required: '+p)
        out[p]=s.replace(old,new).encode()
    patch('tools/verify_framework.py','def verify(root,candidate=False):','def verify(root,candidate=False):\n    __import__("runpy").run_path(str(root/"sync/gonggong_sync.py"))["check"](root)')
    patch('tools/agent-context.mjs',"import fs from 'node:fs';","import fs from 'node:fs';\nimport {execFileSync} from 'node:child_process';")
    patch('tools/agent-context.mjs','  root=fs.realpathSync(root);',"  root=fs.realpathSync(root);\n  execFileSync(process.env.OLYMPUS_PYTHON || 'python', [path.join(root,'sync/gonggong_sync.py'),'check','--root',root], {stdio:'pipe'});")
    append('AGENTS.md','\n上游强制同步和赫尔墨斯数据共享以 sync/POLICY.md 为准。启用前须重新全量核对有效共工源；发现偏差或缺源不得执行。\n')
    for p in ['specs/data-feedback.md','specs/reporting.md','agents/hermes/references/optimization.md','agents/hermes/references/storage.md']:
        append(p,'\n共工可按框架根 sync/POLICY.md 只读使用赫尔墨斯数据优化；用户已持续授权有效共工更新的完整同步。此前“单独指令”要求仍适用于自行提出和实施框架修改，不阻断已批准上游同步。数据读取工具为 sync/read_hermes.py，历史快照不改写。\n')
        append(p,'\n用户明确豁免：无数据库时使用独立 extensions/hermes-files 模块，在目标 Git 仓库的 olympus-hermes-data 记录需求产出并随需求合入。该模块和数据不受共工同步覆盖；赫尔墨斯与共工使用同一文件分析入口。尚无目标仓库时只交付规则与工具，不创建生产数据。文件状态不冒充 SQLite 回执。\n')
    append('agents/hermes/AGENT.md','\n文件数据模式：按 extensions/hermes-files/README.md（框架根相对路径）记录、校验并检查 Git 合入。该模式独立运行，不依赖数据库；数据目录位于目标仓库根，严禁随框架同步覆盖。\n')
    append('AGENTS.md','\n明确豁免：extensions/hermes-files 及目标 Git 仓库中的 olympus-hermes-data 独立维护，不由共工覆盖。需求交付须包含文件数据及 Git 合入检查；仅豁免此模块，其他框架继续全量同步。\n')
    out['README.md']=('# 奥林匹斯：共工的同步分发框架\n\n共工为唯一上游；除名称映射及明确的分发接入外，不允许框架行为偏差。赫尔墨斯数据可由共工只读用于优化。详见 [同步与数据共享规则](sync/POLICY.md)。\n\n本包为同步后候选，尚需独立准入；原批准原件见 source-history.zip。不存在后台自动部署服务。运行数据须存放在包外。\n\n').encode()+out['README.md']
    out['README.md']=('# 独立豁免：赫尔墨斯文件数据源\n\n[规则与命令](extensions/hermes-files/README.md)：无数据库记录需求数据，目标 Git 仓库内独立命名为 olympus-hermes-data，作为需求产出合入。模块与数据均不被共工同步覆盖；待合入目标仓库后再创建真实数据目录。\n\n').encode()+out['README.md']
    # Keep distinct skill identity where original Agent and skill shared one name.
    p='skills/nike/reporting.json';v=get(p);v['component']['id']='nike';put(p,v)
    out['skills/nike/SKILL.md']=out['skills/nike/SKILL.md'].decode().replace('忒弥斯','尼刻').replace('Themis','Nike').encode()
    m=get('framework-manifest.json');m['status']='synchronized_candidate_pending_independent_admission'
    # Registered upstream module, namespace-adapted locally; no fabricated approval.
    module=get('modules/ariadne/module.json');module['state']='source_registered_distribution_pending_review';module['path_base']='framework_root';put('modules/ariadne/module.json',module)
    for item in m['modules']:
        if item['id']=='ariadne':item['state']=module['state']
    put('skills/ariadne/runtime-ref.json',{'path_base':'framework_root','framework_root':'.','coordinator':'modules/ariadne/coordinator.mjs','default_registry':'modules/ariadne/registry.json','mode':'source_read_only_with_local_labels_and_command_preparation','external_ledger_format':'.yuanheng/state.json'})
    cfg=get('modules/ariadne/registry.json');cfg['adapter_cli']=None;put('modules/ariadne/registry.json',cfg)
    for p in ['modules/ariadne/coordinator.mjs','modules/ariadne/test/coordinator.test.mjs']:
        out[p]=out[p].decode().replace('.zeus','.yuanheng').encode()
    p='modules/ariadne/test/coordinator.test.mjs'
    out[p]=("import {fileURLToPath} from 'node:url';\n"+out[p].decode().replace("path.resolve('outputs/olympus-workorders/coordinator.mjs')","fileURLToPath(new URL('../coordinator.mjs',import.meta.url))")).encode()
    append('skills/ariadne/SKILL.md','\nThe framework root is ../.. relative to this skill. runtime-ref.json paths are framework-root relative. Use the shared Hermes reporting.json; the file-data exemption remains available. External source ledger format .yuanheng/state.json is preserved. No live sources or CLI are bound by default.\n')
    profile=get('skills/dike/reporting.json');profile['component']={'kind':'skill','id':'ariadne','version':module['version'],'entry':'skills/ariadne/SKILL.md','entry_sha256':sha(out['skills/ariadne/SKILL.md'])};put('skills/ariadne/reporting.json',profile)
    for p in ['reviews/ariadne-admission.json','reviews/ariadne-module-admission.json']:
        put(p,{'template':False,'status':'pending_distribution_review','source_registration':'source-sinan-history.zip','subject':{'id':'ariadne','version':module['version']},'approval':None})
    # Name mapping makes both source admission names distinct through their original paths.
    module['module_admission']='reviews/ariadne-module-admission.json';module['implementation_admission']='reviews/ariadne-admission.json';put('modules/ariadne/module.json',module)
    for item in m['modules']:
        if item['id']=='ariadne':item['admission_pass']=module['module_admission']
    append('README.md','\n## 阿里阿德涅（司南）已登记模块同步\n\n共工主线 v0.9.0 与已登记在另一来源树的司南 0.2.1 合并同步；不回退主线。模块 modules/ariadne，skill skills/ariadne，共 3 个正式 Agent、10 个 skill。上游登记证据在 source-sinan-history.zip；副本指纹准入仍待审。执行 `node modules/ariadne/coordinator.mjs board modules/ariadne/registry.json`；默认没有真实账本或源 CLI。\n')
    append('specs/module-system.md','\n已同步共工登记模块：阿里阿德涅 ariadne，契约 modules/ariadne/module.json，专项 specs/work-order-management.md，skill skills/ariadne。任务范围不限开发，不新增 Agent；源登记证据保留在 source-sinan-history.zip。\n')
    m['distribution_sync']={'policy':'sync/POLICY.md','checker':'sync/gonggong_sync.py','data_reader':'sync/read_hermes.py','upstream':'gonggong','full_verification_required':True}
    m['distribution_sync']['exemptions']=[{'id':'hermes-file-data','module_root':EXEMPT,'data_root':'<target-git-root>/olympus-hermes-data','sync_behavior':'preserve_existing_module_bytes_never_touch_dataset','authority':'explicit_user_instruction_independent_git_file_data_module','reader':'extensions/hermes-files/hermes_files.py','database_required':False,'initialize_only_after_target_repository_integration':True}]
    lock=get('foundation.lock.json');lock.update(sha256=sha(out['FOUNDATION.md']),source_sha256=sha(raw['FOUNDATION.md']),authority='explicit_user_instruction_complete_upstream_sync_and_namespace_mapping',namespace_only_change=True);put('foundation.lock.json',lock);m['foundation_sha256']=lock['sha256']
    template=get('templates/review-pass.json')
    template['baseline'].update(foundation_sha256=lock['sha256'],foundation_version=lock['version'],zeus_version=m['zeus_version'],policy_version=m['version'])
    put('templates/review-pass.json',template)
    for record in m['upstream_files']:record['sha256']=sha(out[record['path']])
    for s in m['skills']:s['state']='synchronized_candidate_pending_review'
    for p in list(out):
        if not p.endswith('.json'):continue
        v=get(p)
        if isinstance(v,dict) and 'component' in v and 'dependencies' in v and 'entry_sha256' in v['component']:
            v['component']['entry_sha256']=sha(out[v['component']['entry']])
            for dep in v['dependencies']:v['dependencies'][dep]=sha(out[dep])
            put(p,v)
    for a in m['agents']:
        a['state']='synchronized_candidate_pending_independent_admission'
        a['candidate_files']=sorted(set(a['candidate_files']+list(adapters)))
        records=[{'path':p,'sha256':sha(out[p])} for p in a['candidate_files']]
        a['candidate_digest']=sha(''.join(x['path']+'\0'+x['sha256']+'\n' for x in records).encode())
        put(a['admission_pass'],{'template':False,'status':'pending_independent_review','subject':{'id':a['id'],'version_or_digest':{'version':a['version'],'candidate_digest':a['candidate_digest'],'candidate_files':records}},'approval':None,'reason':'Upstream approval preserved as historical evidence; independent admission must bind this candidate.'})
    put('framework-manifest.json',m)
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:
        for p,b in sorted(original_raw.items()):z.writestr(zipfile.ZipInfo(p,date_time=(1980,1,1,0,0,0)),b)
    out['source-history.zip']=buffer.getvalue()
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p,b in sorted(evidence.items()):z.writestr(zipfile.ZipInfo(p,date_time=(1980,1,1,0,0,0)),b)
    out['source-sinan-history.zip']=archive.getvalue()
    put('sync/state.json',{'upstream_version':json.loads(raw['framework-manifest.json'])['version'],'source_files':base_hashes,'sinan_registered_source_files':{p:sha(b) for p,b in sorted(evidence.items())},'adapter_files':{p:sha(b) for p,b in adapters.items()},'scope':'active_framework_plus_registered_sinan_module','admission':'pending_independent_review'})
    return out
def check(root,source=None):
    root=Path(root).resolve();binding=json.loads((root/'sync/binding.json').read_text(encoding='utf-8'))
    location=source or os.environ.get('GONGGONG_FRAMEWORK_SOURCE') or binding['source']
    src=source_root(location);before=inventory(src)
    adapters=adapters_at(root)
    wanted=expected(src,adapters,binding['sinan_source']);actual=inventory(root)
    ignored=REPORTS|{'sync/binding.json'}
    differences=sorted(p for p in set(actual)|set(wanted) if p not in ignored and actual.get(p)!=wanted.get(p))
    if differences:raise ValueError('Framework drift; full sync required: '+', '.join(differences[:20]))
    if before!=inventory(src):raise ValueError('Upstream changed during verification')
    if wanted!=expected(src,adapters,binding['sinan_source']):raise ValueError('Registered module source changed during verification')
    return {'full_parity':True,'parity_scope':'shared_framework_excluding_explicit_hermes_file_exemption','preserved_exemption':EXEMPT,'source_files':len(before),'distribution_files':len(wanted),'upstream_version':json.loads(before['framework-manifest.json'])['version']}
def build(source,out):
    src=source_root(source);dest=Path(out).resolve()
    if dest.exists() or dest==src or src in dest.parents:raise ValueError('Build destination must be a new directory outside source')
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1',PYTHONIOENCODING='utf-8')
    r=subprocess.run([sys.executable,str(src/'tools/verify_framework.py')],capture_output=True,text=True,encoding='utf-8',env=env)
    if r.returncode:raise ValueError('Upstream integrity/admission rejected: '+r.stderr)
    adapter_root=Path(__file__).resolve().parents[1]
    adapters=adapters_at(adapter_root);binding=json.loads((adapter_root/'sync/binding.json').read_text(encoding='utf-8'));content=expected(src,adapters,binding['sinan_source'])
    dest.mkdir(parents=True)
    for p,b in content.items():f=dest/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(b)
    (dest/'sync/binding.json').write_bytes(encoded({'source':str(Path(source).resolve()),'sinan_source':binding['sinan_source'],'purpose':'local_upstream_locator_not_authority'}))
    result=check(dest,source)
    checks=[]
    for command in [[sys.executable,str(dest/'tools/verify_framework.py'),'--candidate'],[sys.executable,str(dest/'tools/check_quality_ownership.py')]]:
        r=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',env=env)
        if r.returncode:raise ValueError('Full verification failed: '+r.stderr)
        checks.append(r.stdout.strip())
    for p in dest.rglob('*.py'):ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
    for p in dest.rglob('*.mjs'):
        r=subprocess.run(['node','--check',str(p)],capture_output=True,text=True,encoding='utf-8',env=env)
        if r.returncode:raise ValueError(r.stderr)
    result.update(checks=checks,python_and_node_syntax='pass',production_admission=False)
    (dest/'sync/verification.json').write_bytes(encoded(result));return result
if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    b=sub.add_parser('build');b.add_argument('--source',required=True);b.add_argument('--out',required=True)
    c=sub.add_parser('check');c.add_argument('--source');c.add_argument('--root',default=str(Path(__file__).resolve().parents[1]))
    a=p.parse_args()
    try:print(json.dumps(build(a.source,a.out) if a.command=='build' else check(a.root,a.source),ensure_ascii=False))
    except (ValueError,OSError,KeyError,TypeError) as e:p.exit(1,str(e)+'\n')
