import runpy, sys, subprocess, time, json
from pathlib import Path
root=Path(sys.argv[1]).resolve(); out=Path(sys.argv[2]); shot=len(sys.argv)>3
calls=[]; real=subprocess.run
def record(*a,**kw):
 calls.append(a[0]);return real(*a,**kw)
subprocess.run=record
sys.path.insert(0,str(root/'scripts'));sys.argv=[str(root/'scripts/selftest.py')]+(['--shots'] if shot else [])
t=time.perf_counter()
try:runpy.run_path(str(root/'scripts/selftest.py'),run_name='__main__')
except SystemExit as e:rc=e.code
out.write_text(json.dumps({'exit':rc,'seconds':round(time.perf_counter()-t,3),'subprocess_count':len(calls),'commands':calls},ensure_ascii=False,indent=2))
