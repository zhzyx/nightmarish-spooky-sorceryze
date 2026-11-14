"""Isolated storage/transport faults after a real setup process completes.

Never invents a successful setup result. The original result is preserved before
truncation or moving it out of the host's result path. Native history is untouched.
"""

from pathlib import Path


def collect_snapshot_traces(control):
    """Retain diagnostic bytes even if decoding or the preceding collector fails."""
    import base64
    import hashlib
    import json

    result = {"preparation_tree_traces": [], "preparation_tree_trace_errors": []}
    try:
        paths = sorted(control.glob("snapshot-trees-*.jsonl*"))
    except OSError as error:
        result["preparation_tree_trace_errors"].append({"read_error": type(error).__name__})
        return result
    for path in paths:
        is_trace = path.name.endswith(".jsonl")
        if not is_trace and not path.name.endswith(".jsonl.error"):
            continue
        entry = {"name": path.name}
        result["preparation_tree_traces" if is_trace else "preparation_tree_trace_errors"].append(entry)
        try:
            raw = path.read_bytes()
        except OSError as error:
            entry["read_error"] = type(error).__name__
            continue
        entry.update(
            bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), raw_base64=base64.b64encode(raw).decode("ascii")
        )
        try:
            if is_trace:
                entry["records"] = [json.loads(line) for line in raw.decode("utf8").splitlines()]
            else:
                entry["text"] = raw.decode("ascii")
        except (ValueError, UnicodeError, RecursionError) as error:
            entry["parse_error"] = type(error).__name__
    return result


def snapshot_git(batch, folder):
    """Observe real Git tree outputs without changing arguments or stdout."""
    real_git = batch.shutil.which("git")
    assert real_git
    script = """import base64,hashlib,json,os,subprocess,sys
from pathlib import Path
git=REAL_GIT
result=subprocess.run([git,*sys.argv[1:]],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
trace=os.environ.get('NATIVE_PREPARATION_TREE_TRACE')
if trace and sys.argv[1:]==['write-tree'] and result.returncode==0:
    try:
        target=Path(trace); previous=[]
        if target.exists(): previous=[json.loads(line) for line in target.read_text(encoding='utf8').splitlines()]
        tree=result.stdout.decode('ascii').strip(); record={'tree':tree,'cwd':os.getcwd()}
        listing=subprocess.run([git,'ls-tree','-r','-z',tree],capture_output=True,check=True).stdout
        record['tree_listing']={'sha256':hashlib.sha256(listing).hexdigest(),'bytes':len(listing)}
        if len(listing)<=2*1024*1024:
            record['tree_listing']['raw_base64']=base64.b64encode(listing).decode('ascii')
        else:
            record['tree_listing']['omitted_reason']='diagnostic_size_limit'
        if previous:
            before=previous[-1]['tree']
            delta=subprocess.run([git,'diff','--raw','--no-abbrev','-z',before,tree],capture_output=True,check=True)
            record['previous_tree']=before; record['raw_diff']=delta.stdout.decode('utf8')
        with target.open('a',encoding='utf8',newline='\\n') as stream:
            stream.write(json.dumps(record,ensure_ascii=True)+'\\n'); stream.flush()
    except Exception as error:
        try: Path(trace+'.error').write_text(type(error).__name__,encoding='ascii')
        except OSError: pass
sys.stdout.buffer.write(result.stdout); sys.stderr.buffer.write(result.stderr)
sys.exit(result.returncode)
""".replace("REAL_GIT", repr(real_git))
    compile(script, "native-preparation-git-observer", "exec")
    directory = Path(folder) / "snapshot-git-observer"
    directory.mkdir()
    return batch.fixture_program(directory / "git", script)


def install(batch, env, folder, mode):
    if mode not in {"malformed-result", "cold-running", "cancel-missing", "baseline", "config-race", "observe"}:
        return
    if mode in {"baseline", "observe"}:
        env["NATIVE_PREPARATION_GIT"] = str(snapshot_git(batch, folder))
    script = """import hashlib,json,os,subprocess,sys,time
from pathlib import Path
node=NODE
def publish(path,value):
    temporary=path.with_name(path.name+'.'+str(os.getpid())+'.tmp')
    temporary.write_text(json.dumps(value),encoding='utf8'); os.replace(temporary,path)
if Path(sys.argv[1]).name=='runner.mjs' and MODE=='config-race':
    raw_request=Path(sys.argv[2]).read_bytes(); request=json.loads(raw_request)
    if any(w.get('repairOf') for w in request['workers']):
        assert hashlib.sha256(raw_request).hexdigest()==sys.argv[4]
        config=Path(request['config']); before=config.read_bytes(); assert hashlib.sha256(before).hexdigest()==request['configSha256']
        value=json.loads(before); value['codex']+='-changed-after-native-verification'
        publish(config,value)
        process=subprocess.Popen([node,*sys.argv[1:]],stdout=subprocess.PIPE,stderr=subprocess.PIPE); stdout,stderr=process.communicate()
        sys.stdout.buffer.write(stdout); sys.stderr.buffer.write(stderr)
        control=Path(os.environ['NATIVE_PREPARATION_CONTROL']); (control/'original-repair-config.json').write_bytes(before)
        publish((control/'config-race-result.json'),{'actual_runner_pid':process.pid,'exit':process.returncode,'stderr':stderr.decode('utf8'),'request_sha256':hashlib.sha256(raw_request).hexdigest(),'config_before':request['configSha256'],'config_after':hashlib.sha256(config.read_bytes()).hexdigest()})
        sys.exit(process.returncode)
setup=Path(sys.argv[1]).name=='setup.mjs'
if setup and MODE=='observe':
    control=Path(os.environ['NATIVE_PREPARATION_CONTROL'])
    os.environ['PATH']=str(Path(os.environ['NATIVE_PREPARATION_GIT']).parent)+os.pathsep+os.environ['PATH']
    os.environ['NATIVE_PREPARATION_TREE_TRACE']=str(control/('snapshot-trees-'+str(os.getpid())+'.actual.jsonl'))
if setup and MODE=='baseline':
    control=Path(os.environ['NATIVE_PREPARATION_CONTROL']); seed=control/'seed.json'
    os.environ['PATH']=str(Path(os.environ['NATIVE_PREPARATION_GIT']).parent)+os.pathsep+os.environ['PATH']
    trace=control/('snapshot-trees-'+str(os.getpid()))
    os.environ['NATIVE_PREPARATION_TREE_TRACE']=str(trace)+'.seed.jsonl'
    if not seed.exists():
        process=subprocess.Popen([node,*sys.argv[1:]]); seed_exit=process.wait(); assert seed_exit==0
        seeded=json.loads(Path(sys.argv[3]).read_bytes()); assert seeded['state']=='ready'
        references={key:{'path':seeded[key],'sha256':hashlib.sha256(Path(seeded[key]).read_bytes()).hexdigest()} for key in ['receipt','config']}
        request=json.loads(Path(sys.argv[2]).read_bytes());uid=Path(request['workspace'])/'samples/project/baseline-probe.gd.uid'
        uid.write_text('uid://fixture951baseline\\n',encoding='utf8')
        tracked=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=request['workspace']).decode('utf8').split('\\0'); assert 'samples/project/baseline-probe.gd.uid' in tracked
        publish(seed,{'seed_pid':process.pid,'seed_exit':seed_exit,'references':references,'uid':{'path':str(uid),'sha256':hashlib.sha256(uid.read_bytes()).hexdigest()}})
    os.environ['NATIVE_PREPARATION_TREE_TRACE']=str(trace)+'.actual.jsonl'
process=subprocess.Popen([node,*sys.argv[1:]]); code=process.wait()
if Path(sys.argv[1]).name=='setup.mjs' and MODE not in {'config-race','observe'}:
    target=Path(sys.argv[3]); raw=target.read_bytes(); original=json.loads(raw)
    assert original['state'] in {'ready','blocked'}
    control=Path(os.environ['NATIVE_PREPARATION_CONTROL'])
    archive=control/'actual-setup-result.json'; archive.write_bytes(raw)
    if MODE=='malformed-result': target.write_bytes(raw[:1])
    elif MODE!='baseline': target.unlink()
    publish((control/'fault-result.json'),{'mode':MODE,'wrapper_pid':os.getpid(),'original_sha256':hashlib.sha256(raw).hexdigest(),'original_state':original['state'],'actual_setup_exit':code})
    if MODE=='baseline':
        seeded=json.loads((control/'seed.json').read_bytes())
        unchanged=all(hashlib.sha256(Path(ref['path']).read_bytes()).hexdigest()==ref['sha256'] for ref in [*seeded['references'].values(),seeded['uid']])
        assert original['state']=='blocked' and 'Preparation baseline changed' in original['error'] and unchanged
        publish((control/('baseline-attempt-'+str(os.getpid())+'.json')),{'actual_pid':process.pid,'exit':code,'seed':seeded,'original_references_unchanged':unchanged,'result':original})
    if MODE=='cold-running':
        while True: time.sleep(.05)
sys.exit(code)
""".replace("NODE", repr(env["DESIGN_BATCH_NODE"])).replace("MODE", repr(mode))
    compile(script, "native-preparation-fault-wrapper", "exec")
    env["NATIVE_PREPARATION_NODE"] = str(batch.fixture_program(Path(folder) / "fault-node-951", script))
