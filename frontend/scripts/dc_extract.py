import sys,re,json,base64,zlib,gzip,os
src,out=sys.argv[1],sys.argv[2]; os.makedirs(out,exist_ok=True)
s=open(src,encoding='utf-8',errors='replace').read()
def block(t):
    m=re.search(r'<script type="__bundler/%s"[^>]*>(.*?)</script>'%t,s,re.S); return m.group(1) if m else None
for t in ['page_order','ext_resources','template']:
    b=block(t); open(os.path.join(out,t+'.txt'),'w',encoding='utf-8').write(b or '')
    print(t, len(b or ''), (b or '')[:300].replace('\n',' '))
man=json.loads(block('manifest'))
print('manifest type',type(man).__name__, len(man))
items=man.items() if isinstance(man,dict) else enumerate(man)
idx=[]
for k,v in items:
    data=base64.b64decode(v['data']) if isinstance(v.get('data'),str) else b''
    if v.get('compressed'):
        try: data=gzip.decompress(data)
        except Exception:
            data=zlib.decompress(data,-15) if data[:2]!=b'x\x9c' else zlib.decompress(data)
    ext={'text/html':'.html','text/css':'.css','application/javascript':'.js','text/javascript':'.js','image/png':'.png','image/webp':'.webp','video/mp4':'.mp4','font/woff2':'.woff2','image/svg+xml':'.svg','image/jpeg':'.jpg'}.get(v.get('mime'),'')
    name=str(k)+ext; open(os.path.join(out,name),'wb').write(data)
    idx.append((name,v.get('mime'),len(data),v.get('name') or v.get('path')))
for i in sorted(idx,key=lambda x:-x[2]): print(i)
