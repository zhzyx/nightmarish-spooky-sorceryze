"""Isolated storage/transport faults after a real setup process completes.

Never invents a successful setup result. The original result is preserved before
truncation or moving it out of the host's result path. Native history is untouched.
"""

from pathlib import Path


def install(batch, env, folder, mode):
    if mode not in {"malformed-result", "cold-running", "cancel-missing", "baseline", "config-race"}:
        return
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
if setup and MODE=='baseline':
    control=Path(os.environ['NATIVE_PREPARATION_CONTROL']); seed=control/'seed.json'
    if not seed.exists():
        process=subprocess.Popen([node,*sys.argv[1:]]); seed_exit=process.wait(); assert seed_exit==0
        seeded=json.loads(Path(sys.argv[3]).read_bytes()); assert seeded['state']=='ready'
        references={key:{'path':seeded[key],'sha256':hashlib.sha256(Path(seeded[key]).read_bytes()).hexdigest()} for key in ['receipt','config']}
        request=json.loads(Path(sys.argv[2]).read_bytes());uid=Path(request['workspace'])/'samples/project/baseline-probe.gd.uid'
        uid.write_text('uid://fixture951baseline\\n',encoding='utf8')
        tracked=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=request['workspace']).decode('utf8').split('\\0'); assert 'samples/project/baseline-probe.gd.uid' in tracked
        publish(seed,{'seed_pid':process.pid,'seed_exit':seed_exit,'references':references,'uid':{'path':str(uid),'sha256':hashlib.sha256(uid.read_bytes()).hexdigest()}})
process=subprocess.Popen([node,*sys.argv[1:]]); code=process.wait()
if Path(sys.argv[1]).name=='setup.mjs' and MODE!='config-race':
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
