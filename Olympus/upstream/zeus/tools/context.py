"""Load the invariant core and agent; include organization procedure only on demand."""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1]
def build(organize=False):
    m=json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'))
    files=[m['core'],m['agent']]
    if organize:files.append(m['on_demand_skill'])
    return '\n\n'.join((ROOT/f).read_text(encoding='utf-8').strip() for f in files)+'\n',files
if __name__=='__main__':
    if sys.argv[1:] not in ([],['--organize']):
        sys.exit('Usage: context.py [--organize]')
    print(build(bool(sys.argv[1:] ))[0],end='')
