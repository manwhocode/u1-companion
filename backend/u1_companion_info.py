"""Version information and user-defined model groups. No printer commands."""
import json,time,uuid,urllib.request
from pathlib import Path
from u1_recovery import atomic

REPO='https://github.com/manwhocode/u1-companion'
_cache={}
_published_at=0

def poll(store):
    global _published_at
    if _published_at and time.monotonic()-_published_at<3600:return
    state=info()
    store.put('fluidd','u1_companion_update_v1',{**state,'updatedAt':time.time()})
    _published_at=time.monotonic()

def info():
    installed=json.loads(Path('/home/lava/fluidd/u1-filaments-ui/addon-status.json').read_text())['version']
    if time.time()-_cache.get('checkedAt',0)>3600:
        try:
            req=urllib.request.Request('https://raw.githubusercontent.com/manwhocode/u1-companion/main/install.sh',headers={'User-Agent':'U1-Companion'})
            with urllib.request.urlopen(req,timeout=3) as response:raw=response.read(65536).decode()
            import re
            latest=re.search(r'^VERSION=(v[0-9A-Za-z.-]+)$',raw,re.M)[1]
            _cache.update(latest=latest,checkedAt=time.time(),error=False)
        except Exception:_cache.update(latest=installed,checkedAt=time.time(),error=True)
    def version(v):
        import re
        return tuple(int(x) for x in re.findall(r'\d+',v))
    return dict(installed=installed,latest=_cache['latest'],updateAvailable=version(_cache['latest'])>version(installed),checkFailed=_cache['error'],repository=REPO)

def models(store,operation,payload):
    path=store.folder/'favorite-models.json'
    data=json.loads(path.read_text()) if path.exists() else {'models':[]}
    if operation=='models_save':
        files=payload.get('files');name=payload.get('name');ident=payload.get('id') or str(uuid.uuid4())
        if not isinstance(name,str) or not 1<=len(name.strip())<=120:raise ValueError('Invalid model name')
        if not isinstance(files,list) or not 1<=len(files)<=100 or any(not isinstance(f,str) or len(f)>512 or not f.lower().endswith('.gcode') or '..' in f.split('/') for f in files):raise ValueError('Invalid G-code files')
        if len(data['models'])>=500 and not any(m['id']==ident for m in data['models']):raise ValueError('Favorite model limit reached')
        data['models']=[m for m in data['models'] if m['id']!=ident]+[{'id':ident,'name':name.strip(),'files':list(dict.fromkeys(files))}]
        atomic(path,data)
    if operation=='models_delete':
        data['models']=[m for m in data['models'] if m['id']!=payload.get('id')];atomic(path,data)
    if operation!='models_stats':return data
    model=next(m for m in data['models'] if m['id']==payload.get('id'))
    jobs=[];seen=set();truncated=False
    for offset in range(0,10000,100):
        page=store.api('/server/history/list?limit=100&start='+str(offset))['jobs']
        for job in page:
            if job.get('job_id') not in seen and job.get('filename') in model['files']:jobs.append(job)
            seen.add(job.get('job_id'))
        if len(page)<100:break
    else:truncated=True
    usage=store.get('fluidd','u1_spool_usage_v1',{})
    records=[r for r in usage.get('records',[]) if r.get('filename') in model['files'] and r.get('state')=='applied']
    grams=sum(float(row.get('grams',0)) for r in records for row in r.get('rows',[]))
    priced=[row for r in records for row in r.get('rows',[]) if row.get('pricePerGram') is not None]
    return dict(model=model,prints=len(jobs),completed=sum(j.get('status')=='completed' for j in jobs),duration=sum(float(j.get('print_duration',0)) for j in jobs),grams=grams,cost=sum(float(r.get('grams',0))*float(r['pricePerGram']) for r in priced),priced=bool(priced),truncated=truncated,records=len(records))
