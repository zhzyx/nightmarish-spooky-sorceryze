# Issue #6 模拟验收过程

关联工单：https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/6 。

执行了真实Windows CI编辑器的headless原生页面与按钮链路。仅HTTP模型回复为本机夹具；真实Issue、框架准入和文件回执不替换。四个拒绝场景模型请求均为0，正常与工具场景分别1/2次。初次夹具初始化顺序修正后运行；offline断言按Windows实际WinError2补强，仅重跑该项，其余五项按相同二进制复用。临时事件不导入生产目录。

以下保留已执行过程的源码；仅把机器绝对路径替换为环境变量。原始执行源码SHA256：`407ecf359afbfa6af264ab35c3d41d08e13cd52648140f1002c2166f346fbf45`。设置 OLYMPUS_ACCEPTANCE_WORKSPACE/OUT/EDITOR、OLYMPUS_GH、OLYMPUS_NODE 后可在临时环境复现；ISSUE6_CASES=offline只补验该项。GitHub账号须有读取真实工单权限。不要复制凭据到临时Git。

```python
"""Issue 6: native Windows editor, real intake/admission, loopback model only."""
import hashlib
import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timezone

ROOT = Path(os.environ['OLYMPUS_ACCEPTANCE_WORKSPACE'])
OUT = Path(os.environ['OLYMPUS_ACCEPTANCE_OUT'])
EDITOR = Path(os.environ['OLYMPUS_ACCEPTANCE_EDITOR'])
GH = os.environ['OLYMPUS_GH']
OUT.mkdir(exist_ok=True)
def inventory(folder):
    return {p.relative_to(folder).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file()}
before = inventory(ROOT/'olympus-hermes-data')
report = {'started_at':datetime.now(timezone.utc).isoformat(),'issue':6,'ci_run':41524800849,'artifact':13178384007,'source_commit':'df03887786c13a822551751f11fe565376fef6b5','real_model_calls':False,'cases':[]}
report['binary_sha256'] = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in EDITOR.parent.glob('*.exe')}
selected=os.environ.get('ISSUE6_CASES')
if selected:
    previous=json.loads((OUT/'report.json').read_text(encoding='utf-8'))
    assert previous['binary_sha256']==report['binary_sha256']
    report['cases']=[c for c in previous['cases'] if c['mode']!=selected]
    assert all(c['passed'] for c in report['cases'])
    report['reused_checks_from']=previous['completed_at']
for mode,number,request in [('missing',0,''),('mismatch',6,'wrong-request-id'),('closed',7,'upstream-workflow-upgrade-20261102'),('offline',6,'issue-governance-20261102'),('accepted',6,'issue-governance-20261102'),('tool',6,'issue-governance-20261102')]:
    if selected and mode!=selected: continue
    requests=[]
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append(body)
            msg={'role':'assistant','content':'OLYMPUS_FIXTURE_REPLY'}
            if mode=='tool' and len(requests)==1:
                msg={'role':'assistant','content':'','tool_calls':[{'id':'fixture-tool','type':'function','function':{'name':'list_scripts','arguments':'{}'}}]}
            data=json.dumps({'choices':[{'message':msg,'finish_reason':'tool_calls' if 'tool_calls' in msg else 'stop'}]}).encode()
            self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        def log_message(self,*args): pass
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix='issue6-native-') as tmp:
            root=Path(tmp)
            shutil.copytree(ROOT/'Olympus',root/'Olympus',ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copytree(ROOT/'customizations/components',root/'customizations/components',ignore=shutil.ignore_patterns('__pycache__'))
            (root/'tools').mkdir();shutil.copyfile(ROOT/'tools/olympus_bridge.py',root/'tools/olympus_bridge.py')
            (root/'.github').mkdir()
            for name in ['labels.json','status-labels.json']: shutil.copyfile(ROOT/'.github'/name,root/'.github'/name)
            shutil.copyfile(ROOT/'work-items.json',root/'work-items.json')
            def run(args,**kw): return subprocess.run(args,cwd=root,check=True,capture_output=True,**kw)
            run(['git','init','--quiet']);run(['git','remote','add','origin','https://github.com/zhzyx/nightmarish-spooky-sorceryze.git'])
            run(['git','config','core.autocrlf','false']);run(['git','add','.'])
            run(['git','-c','user.name=Isolated Acceptance','-c','user.email=acceptance@example.invalid','-c','commit.gpgsign=false','commit','--quiet','-m','Isolated original framework and adapter'])
            run([sys.executable,str(root/'Olympus/extensions/hermes-files/hermes_files.py'),'init','--repo',str(root)])
            project=root/'project';project.mkdir()
            (project/'project.godot').write_text('[application]\nconfig/name="Isolated Issue 6 acceptance"\n',encoding='utf-8')
            gd=(ROOT/'tests/editor/olympus_chat_gate.gd').read_text(encoding='utf-8')
            anchor='\tvar backend = dock.find_child("AIBackend", true, false)'
            settings='\tsettings.set_setting("olympus/issue_number", "'+str(number)+'")\n\tsettings.set_setting("olympus/request_id", "'+request+'")\n'
            gd=gd.replace(anchor,settings+anchor)
            gd=gd.replace('if dock.get_meta("olympus_status", "") == "blocked":', 'if dock.get_meta("olympus_status", "") == "blocked":\n\t\t\tfor item in dock.find_children("*", "RichTextLabel", true, false):\n\t\t\t\tprint("ISSUE6_ERROR=", item.get_parsed_text())')
            (project/'gate.gd').write_text(gd,encoding='utf-8')
            env=dict(os.environ,PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1',OLYMPUS_PYTHON=sys.executable,OLYMPUS_NODE=os.environ['OLYMPUS_NODE'],OLYMPUS_GH=GH,OLYMPUS_TEST_WORKSPACE=str(root),OLYMPUS_WORKSPACE=str(root),OLYMPUS_TEST_MODE=mode if mode in ('accepted','tool') else 'rejected',OLYMPUS_TEST_ENDPOINT=f'http://127.0.0.1:{server.server_port}/v1/chat/completions',GONGGONG_FRAMEWORK_SOURCE=str(root/'absent-upstream'))
            env['GH_CONFIG_DIR']=os.environ.get('GH_CONFIG_DIR',str(Path(os.environ['APPDATA'])/'GitHub CLI'))
            for key in ['OPENAI_API_KEY','GODOT_AI_API_KEY']: env.pop(key,None)
            if mode=='offline': env['OLYMPUS_GH']=str(root/'unavailable-gh.exe')
            for key in ['APPDATA','LOCALAPPDATA','XDG_CONFIG_HOME','XDG_DATA_HOME']:
                env[key]=str(root/key);(root/key).mkdir()
            intake=None
            if mode!='missing':
                probe=subprocess.run([sys.executable,str(root/'customizations/components/issue-workorders/issue_gate.py'),'--repo',str(root),'--issue',str(number),'--request-id',request,'--tenant','olympus-workspace','--intake-only'],env=env,capture_output=True,timeout=140)
                reason=probe.stderr.decode('utf-8',errors='replace')
                if mode in ('accepted','tool'):
                    assert probe.returncode==0,reason
                    intake=json.loads(probe.stdout)
                    assert intake['number']==6 and intake['status'] in ('status:in-review','status:in-progress')
                else:
                    expected={'mismatch':'stable request ID does not match','closed':'Issue is not open','offline':'WinError 2'}[mode]
                    if mode=='offline': assert not Path(env['OLYMPUS_GH']).exists()
                    assert probe.returncode!=0 and expected in reason,(mode,reason)
                    intake={'rejected_reason':expected}
            result=subprocess.run([str(EDITOR),'--headless','--editor','--path',str(project),'--script','res://gate.gd'],env=env,cwd=root,capture_output=True,timeout=150)
            (OUT/(mode+'.stdout.log')).write_bytes(result.stdout);(OUT/(mode+'.stderr.log')).write_bytes(result.stderr)
            output=result.stdout.decode('utf-8',errors='replace')
            positive=mode in ('accepted','tool')
            marker='OLYMPUS_CHAT_FIXTURE_ACCEPTED_OK' if positive else 'OLYMPUS_CHAT_FAIL_CLOSED_OK'
            assert result.returncode==0 and marker in output,(mode,result.returncode,output[-1800:],result.stderr[-1800:])
            assert len(requests)==(2 if mode=='tool' else 1 if positive else 0),(mode,len(requests))
            events=[json.loads(p.read_text(encoding='utf-8')) for p in (root/'olympus-hermes-data/events').rglob('*.json')]
            checks={'native_page':True,'model_requests':len(requests),'events':len(events),'intake':intake}
            if not positive:
                expected='Missing host request: request_id' if mode=='missing' else 'Issue intake rejected'
                assert expected in output,(mode,output[-2000:])
            if positive:
                assert all(e['source_ref']=='https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/6' for e in events)
                assert all(e['request_id']=='issue-governance-20261102' for e in events)
                assert any(e['kind']=='request_end' and e['payload']['status']=='completed' for e in events)
                assert any(e['payload'].get('context_accepted') is True for e in events)
                for req in requests:
                    context=req['messages'][0]['content'].lower()
                    assert 'athena' in context and 'zeus' in context and 'isolated_framework_context_fixture' not in context
                if mode=='tool':
                    tool_messages=[m for m in requests[1]['messages'] if m.get('role')=='tool' and m.get('tool_call_id')=='fixture-tool']
                    assert len(tool_messages)==1,requests[1]['messages']
                    tool_result=json.loads(tool_messages[0]['content'])
                    assert isinstance(tool_result.get('paths'),list) and tool_result.get('limit')==500 and 'error' not in tool_result,tool_result
                    assert any(e['payload'].get('phase')=='tool-1-0' and e['payload'].get('status')=='result_returned' for e in events),events
                    checks['tool_result']=tool_result
                assert not list((root/'.olympus-outbox/chat').glob('*.json'))
                run(['git','add','.'])
                run(['git','-c','user.name=Isolated Acceptance','-c','user.email=acceptance@example.invalid','-c','commit.gpgsign=false','commit','--quiet','-m','Isolated simulated acceptance evidence'])
                check=run([sys.executable,str(root/'Olympus/extensions/hermes-files/hermes_files.py'),'git-check','--repo',str(root),'--require-committed'])
                checks['hermes_git_check']=json.loads(check.stdout)
                checks['real_issue_admission_and_receipts']=True
            else: assert not events, (mode,'Rejected binding produced business events')
            report['cases'].append({'mode':mode,'passed':True,**checks})
            print(json.dumps(report['cases'][-1]),flush=True)
    except Exception as error:
        report['cases'].append({'mode':mode,'passed':False,'error':str(error),'stderr':getattr(error,'stderr',b'').decode('utf-8',errors='replace')[-1600:]})
        print(json.dumps(report['cases'][-1]),flush=True)
    finally:
        server.shutdown();server.server_close()
report['production_dataset_unchanged']=inventory(ROOT/'olympus-hermes-data')==before
report['ok']=all(c['passed'] for c in report['cases']) and report['production_dataset_unchanged']
report['completed_at']=datetime.now(timezone.utc).isoformat()
(OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
raise SystemExit(0 if report['ok'] else 1)
```
