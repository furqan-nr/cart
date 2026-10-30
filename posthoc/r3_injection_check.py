import json, os, shutil, subprocess, sys
SITE='/home/claude/r3/venvclean/lib/python3.13/site-packages'
TREE='/home/claude/qiskit/w261'
tests=json.load(open('/tmp/claude-0/regtests.json'))
res={}
def run(site, file, name):
    env=dict(os.environ, PYTHONPATH=f"{site}:{TREE}", QISKIT_PARALLEL='FALSE')
    try:
        p=subprocess.run([sys.executable,'-m','pytest','-q','-p','no:cacheprovider','--import-mode=importlib',
                      f"{TREE}/{file}",'-k',name,'-x','--no-header'],capture_output=True,text=True,env=env,cwd='/tmp',timeout=300)
    except subprocess.TimeoutExpired:
        return 'hang', 'timeout 300 s'
    last=[l for l in p.stdout.splitlines() if l.strip()][-1:] 
    return p.returncode, (last[0] if last else p.stderr[-200:])
for fid, ts in tests.items():
    fs=f'/tmp/claude-0/fsite/{fid}'; shutil.rmtree(fs,ignore_errors=True); os.makedirs(fs)
    shutil.copytree(f'{SITE}/qiskit', f'{fs}/qiskit')
    ov=f'/home/claude/r3/faults_out/{fid}/overlay'
    for root,_,files in os.walk(ov):
        for fn in files:
            src=os.path.join(root,fn); dst=os.path.join(fs,os.path.relpath(src,ov)); shutil.copy2(src,dst)
    for file,name in ts:
        res.setdefault(fid,[]).append(dict(test=name, clean=run(SITE,file,name), fault=run(fs,file,name)))
    shutil.rmtree(fs,ignore_errors=True)
    json.dump(res,open('/tmp/claude-0/regresults_partial.json','w'),indent=1)
    print(fid, [(r['test'][:40], r['clean'][0], r['fault'][0]) for r in res.get(fid,[])], flush=True)
json.dump(res,open('/tmp/claude-0/regresults.json','w'),indent=1)
