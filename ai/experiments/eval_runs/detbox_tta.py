
import json, sys, time, subprocess
from pathlib import Path
import cv2, numpy as np, torch
from mmdet.apis import init_detector, inference_detector
from mmengine.registry import DefaultScope
import os
root=Path(os.environ.get('CREAMOFF_ROOT', Path.home()/'Desktop/jjh/ssafy'))
paw=root/'paw_eval'
sys.path[:0]=[str(paw),str(Path(__file__).resolve().parents[1]/'cv/screen')]
from predict import MMPose, read_image
from speed import best_dog
from tta_eval import unrotate
out=Path(sys.argv[1])
limit=int(sys.argv[2])
out.mkdir(parents=True,exist_ok=True)
cfg=paw/'models/fs-v4/pose.py'
flip=out/'pose_flip.py'
flip.write_text(f"_base_ = [{cfg.as_posix()!r}]\nmodel = dict(test_cfg=dict(flip_test=True))\n")
load=torch.load
torch.load=lambda *a, **k:load(*a,**{**k,'weights_only':False})
try:
    det=init_detector(str(paw/'models/fs-v4/det.py'),str(paw/'models/fs-v4/det.pth'),device='cuda:0')
finally:
    torch.load=load
models=[MMPose({'config':str(c),'weights':'models/fs-v4/pose.pth'},paw,'cuda:0') for c in (cfg,flip)]
for tag,gt,images in [('jeni','gt_fall.json','keypoints_260820'),('wowwow','gt_ww.json','keypoints_wowwow')]:
    d=json.loads((root/'experiments/cv/data'/gt).read_text(encoding='utf8'))
    by_id={im['id']:im for im in d['images']}
    preds={k:[] for k in ('t0','t2','t4')}
    annotations=d['annotations'][:limit or None]
    start=time.time()
    for index,a in enumerate(annotations,1):
        im=by_id[a['image_id']]
        image=read_image(root/'dataset'/images/im['file_name'])
        with DefaultScope.overwrite_default_scope('mmdet'):
            b=best_dog(inference_detector(det,image),.25)
        if b is None: continue
        box=np.asarray(b,float)
        c=(box[:2]+box[2:])/2
        for tag_t,model,scales,rots in [('t0',models[0],[1],[]),('t2',models[1],[.9,1,1.1],[]),('t4',models[1],[.85,.9,1,1.1,1.15],[8,-8])]:
            points=[]
            for s in scales:
                half=(box[2:]-box[:2])*s/2
                kp,sc=model(image,np.r_[c-half,c+half].tolist())
                if s==1: base_sc=sc[:22]
                points.append(kp[:22])
            for deg in rots:
                matrix=cv2.getRotationMatrix2D(tuple(c),deg,1)
                rotated=cv2.warpAffine(image,matrix,(image.shape[1],image.shape[0]),borderMode=cv2.BORDER_REPLICATE)
                kp,_=model(rotated,box.tolist())
                points.append(unrotate(kp[:22],c,deg))
            preds[tag_t].append(dict(ann_id=a['id'],image_id=a['image_id'],category_id=a.get('category_id',1),keypoints=np.column_stack([np.mean(points,axis=0),base_sc]).ravel().tolist(),score=float(np.mean(base_sc))))
        if index%100==0: print(tag,index,round(time.time()-start),flush=True)
    gt_path=root/'experiments/cv/data'/gt
    if limit:
        d['annotations']=annotations
        d['images']=[by_id[i] for i in {a['image_id'] for a in annotations}]
        gt_path=out/f'{tag}_smoke_gt.json'
        gt_path.write_text(json.dumps(d),encoding='utf8')
    print(tag,'covered',len(preds['t0']),'/',len(annotations),flush=True)
    for k,v in preds.items():
        pred=out/f'{tag}_{k}_pred.json'
        score=out/f'{tag}_{k}_score.json'
        pred.write_text(json.dumps({'predictions':v}),encoding='utf8')
        subprocess.run([sys.executable,'score.py','--gt',str(gt_path),'--pred',str(pred),'--out',str(score)],cwd=paw,check=True)
        result=json.loads(score.read_text(encoding='utf8'))
        metric=result.get('kpi',result)
        print(tag,k,metric['KPI-04']['mae'],metric['KPI-19']['value'],flush=True)

