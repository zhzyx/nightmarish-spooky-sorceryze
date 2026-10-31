"""Verify Olympus upstream parity and requirement data delivery."""
from pathlib import Path
import argparse,json,os,subprocess,sys

def main():
    p=argparse.ArgumentParser();p.add_argument('--source');p.add_argument('--require-committed',action='store_true');a=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1',PYTHONIOENCODING='utf-8')
    if a.source:env['GONGGONG_FRAMEWORK_SOURCE']=str(Path(a.source).resolve())
    commands=[
        [sys.executable,str(root/'Olympus/tools/verify_framework.py'),'--candidate'],
        [sys.executable,str(root/'Olympus/extensions/hermes-files/hermes_files.py'),'git-check','--repo',str(root)]+(['--require-committed'] if a.require_committed else [])
    ]
    results=[]
    for command in commands:
        r=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',env=env)
        if r.returncode:raise ValueError(r.stderr.strip() or r.stdout.strip())
        results.append(json.loads(r.stdout))
    print(json.dumps({'workspace':'Olympus','checks':results,'agent_admission':'pending_independent_review'},ensure_ascii=False))

if __name__=='__main__':
    try:main()
    except (ValueError,OSError) as e:print(str(e),file=sys.stderr);sys.exit(1)
