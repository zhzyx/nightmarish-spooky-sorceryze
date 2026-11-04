"""Verify exact installed bytes. A lock is not approval or host authorization."""
from pathlib import Path
import argparse, hashlib, json

def inventory(root):
    root=Path(root).resolve(); files={}
    for p in sorted(root.rglob('*')):
        if '__pycache__' in p.parts or p.suffix=='.pyc':continue
        if p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()):raise ValueError('Linked framework path')
        if p.is_file() and p != root/'package-lock.json':
            files[p.relative_to(root).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    return files

def check(root, *, return_inventory=False):
    root=Path(root).resolve()
    lock=json.loads((root/'package-lock.json').read_text(encoding='utf-8'))
    if lock.get('schema_version')!=1 or lock.get('path_base')!='framework_root':raise ValueError('Invalid package lock')
    actual=inventory(root); expected=lock['files']
    drift=sorted(p for p in set(actual)|set(expected) if actual.get(p)!=expected.get(p))
    if drift:raise ValueError('Local package drift: '+', '.join(drift[:20]))
    if return_inventory:return actual
    return {'local_integrity':True,'files':len(actual),'external_source_required':False,'authority_authenticated':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',default=str(Path(__file__).resolve().parents[1]));args=parser.parse_args()
    try:print(json.dumps(check(args.root)))
    except (OSError,ValueError,KeyError,TypeError) as error:parser.exit(1,str(error)+'\n')
