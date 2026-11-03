import ast, hashlib, json, sys, threading
from collections import OrderedDict
from pathlib import Path
from types import SimpleNamespace

root, kit = map(Path, sys.argv[1:])
p = json.loads((kit/'source-provenance.json').read_text())
for f in p['files']:
    assert hashlib.sha256((root/f['label']/f['path']).read_bytes()).hexdigest()==f['sha256']
results=[]
for label in ('base','main','candidate'):
    path=root/label/'src/limit.py'
    tree=ast.parse(path.read_bytes())
    selected=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'take','refund'}]
    assert len(selected)==2
    rows=[]
    for ceiling in (1,2,5):
        for scenario in ('evicted','never-seen','retained','burst-cap','other-kind'):
            buckets=OrderedDict()
            ns=dict(MAX_BUCKETS=ceiling,MAX_IDENTITIES=100,_buckets=buckets,
                    _identities=set(),_requests={'rate_limited':0},_buckets_lock=threading.Lock(),
                    config=SimpleNamespace(_dbg=lambda *a,**k:None),
                    client_ip=lambda request,header:request,time=SimpleNamespace(monotonic=lambda:123.0))
            exec(compile(ast.Module(body=selected,type_ignores=[]),str(path),'exec'),ns)
            for i in range(ceiling+1):
                ns['take'](str(i),'create',6,2)
            before=list(buckets.items())
            expected=before.copy()
            who,kind=str(ceiling),'create'
            if scenario=='evicted':who='0'
            elif scenario=='never-seen':who='missing'
            elif scenario=='other-kind':kind='read'
            elif scenario=='burst-cap':
                ns['refund'](who,kind,6,2)
                before=list(buckets.items())
                expected=before.copy()
            else:expected[-1]=((who,kind),(2.0,123.0))
            ns['refund'](who,kind,6,2)
            after=list(buckets.items())
            rows.append(dict(ceiling=ceiling,scenario=scenario,before=before,expected=expected,after=after,
                             matches=after==expected and len(after)<=ceiling))
    results.append(dict(label=label,matches=sum(x['matches'] for x in rows),cases=len(rows),rows=rows))
(kit/'native-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print([(r['label'],r['matches'],r['cases']) for r in results])
assert results[-1]['matches']==15
