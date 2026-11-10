import json
import os
import sys
import tomllib
from pathlib import Path
from statistics import median

import cv2

root=Path(os.environ.get('CREAMOFF_ROOT', Path.home()/'Desktop/jjh/ssafy'))
paw=root/'paw_eval'
delivery=root/'deliver_1105'
out=Path(sys.argv[1])
sys.path[:0]=[str(paw),str(delivery/'plus')]
import skipdet2  # noqa: E402
import speed  # noqa: E402

cfg_path=delivery/'models/creamoff-b4-wise05team-tta.toml'
cfg=tomllib.loads(cfg_path.read_text(encoding='utf-8'))
cfg['stack']['det_config']=str(paw/'models/fs-v4/det.py')
cfg['stack']['det_weights']=str(paw/'models/fs-v4/det.pth')
cfg['config']=str(out/'pose_flip.py')
stacks=dict(speed.STACKS)
skipdet2.register(stacks,speed.MMDetMMPose,speed.best_dog)
enhanced=stacks[cfg['stack']['backend']](cfg,cfg_path.parent,'cuda:0')
plain=speed.MMDetMMPose({**cfg,'config':str(paw/'models/fs-v4/pose.py')},cfg_path.parent,'cuda:0')
path=speed.load_videos(str(paw/'speed_videos.txt'),str(root/'dataset/videos'))[0]
capture=cv2.VideoCapture(path)
fps=capture.get(cv2.CAP_PROP_FPS)
capture.release()
frames=speed.read_frames(path)

def variant(name):
    if name=='t0':
        return plain
    enhanced.scales=[0.9,1.0,1.1] if name=='t2' else [0.85,0.9,1.0,1.1,1.15]
    enhanced.rots=[] if name=='t2' else [8.0,-8.0]
    return enhanced

names=['t0','t2','t4']
for name in names:
    variant(name).warm(frames)
    print('warmed',name,flush=True)
rows={name:[] for name in names}
for r in range(3):
    for name in names[r:]+names[:r]:
        d,p,n=variant(name)(frames)
        row={'detection_s':d,'pose_s':p,'inference_s':d+p,'detections':n}
        rows[name].append(row)
        print(name,r+1,row,flush=True)
assert len({row['detections'] for values in rows.values() for row in values})==1
result={'video':Path(path).name,'fps':fps,'frames':len(frames),'rows':rows,
        'median_s':{name:median(r['inference_s'] for r in rows[name]) for name in names}}
(out/'video_timing.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(result['median_s'],flush=True)

