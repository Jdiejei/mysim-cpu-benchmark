import subprocess,time,urllib.request,urllib.parse,os
from pathlib import Path

def public_download(repo,tag,name,target):
 target=Path(target);tmp=target.with_name(target.name+'.partial');url='https://github.com/'+repo+'/releases/download/'+urllib.parse.quote(tag,safe='')+'/'+urllib.parse.quote(name,safe='')
 for attempt in range(4):
  try:
   with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'MySimAssetWorker'}),timeout=180) as source,open(tmp,'wb') as dest:
    while True:
     block=source.read(1024*1024)
     if not block:break
     dest.write(block)
   tmp.replace(target);return
  except Exception:
   if attempt==3:raise RuntimeError('Public release asset download failed after bounded retries')
   time.sleep(min(30*(attempt+1),90))

def release_upload(args,mandatory=False):
 deadline=time.monotonic()+(600 if mandatory else 0)
 while True:
  result=subprocess.run(args,capture_output=True)
  if result.returncode==0:return result
  error=result.stderr.decode(errors='replace').lower()
  transient=any(t in error for t in ['rate limit','http 429','http 502','http 503','http 504','connection reset','timeout'])
  if not mandatory:return result
  if not transient or time.monotonic()+60>deadline:raise RuntimeError('Release publication failed after bounded retries; local outputs retained')
  time.sleep(60)
