set -euo pipefail
bash /exp/run/setup.sh > /dev/null 2>&1
cd /work/ssafy/paw_eval
DEV="${1:-cpu}"
python /exp/train/make_meta.py --out /exp/train/creamoff46.py
mkdir -p /data/train_set
ln -sfn /ssafy/dataset/keypoints_260820/images /data/train_set/images
python /exp/train/pad_coco.py --src /ssafy/dataset/keypoints_260820/annotations.json --out /data/train_set/annotations_46.json --drop-untouched
python - "$DEV" <<'PY'
import json, sys
d = json.load(open("/data/train_set/annotations_46.json", encoding="utf-8"))
keep = {im["id"] for im in d["images"][:16]}
d["images"] = [im for im in d["images"] if im["id"] in keep]
d["annotations"] = [a for a in d["annotations"] if a["image_id"] in keep]
json.dump(d, open("/data/train_set/annotations_46.json", "w", encoding="utf-8"), ensure_ascii=False)
print("smoke subset:", len(d["images"]), "images", len(d["annotations"]), "annotations (파이프라인 점검용, 결과로 쓰지 않음)")

from mmengine.config import Config
from mmengine.runner import Runner
import torch
cfg = Config.fromfile("/exp/train/ft_base.py")
cfg.work_dir = "/tmp/ft_smoke"
cfg.train_cfg = dict(by_epoch=True, max_epochs=1, val_interval=1000)
cfg.train_dataloader.batch_size = 4
cfg.train_dataloader.num_workers = 0
cfg.train_dataloader.persistent_workers = False
cfg.default_hooks.logger.interval = 1
if sys.argv[1] == "cpu":
    cfg.device = "cpu"
_load = torch.load
torch.load = lambda *a, **k: _load(*a, **{**k, "weights_only": False})
runner = Runner.from_cfg(cfg)
runner.train()
m = runner.model
print("norm_eval:", m.backbone.norm_eval, "| head out:", m.head.out_channels)
bn = [mod for mod in m.backbone.modules() if isinstance(mod, torch.nn.BatchNorm2d)]
print("backbone BN in train mode after training:", sum(b.training for b in bn), "of", len(bn))
PY
ls -la /tmp/ft_smoke | tail -3
