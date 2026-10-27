set -euo pipefail
bash /exp/run/setup.sh > /dev/null 2>&1
cd /work/ssafy/paw_eval
DEV="${1:-cpu}"
python /exp/train/make_meta.py --out /exp/train/creamoff46.py
python /exp/train/make_train_set.py --out /data/wow_set
python - "$DEV" <<'PY'
import json, sys
d = json.load(open("/data/wow_set/train_46.json", encoding="utf-8"))
keep = {im["id"] for im in d["images"][:24]}
d["images"] = [im for im in d["images"] if im["id"] in keep]
d["annotations"] = [a for a in d["annotations"] if a["image_id"] in keep]
json.dump(d, open("/data/wow_set/smoke_46.json", "w", encoding="utf-8"), ensure_ascii=False)
print("smoke subset (파이프라인 점검용):", len(d["images"]), "images", len(d["annotations"]), "annotations")

from mmengine.config import Config
from mmengine.runner import Runner
import torch
cfg = Config.fromfile("/exp/train/ft_base.py")
cfg.work_dir = "/tmp/ft_smoke_wow"
cfg.train_cfg = dict(by_epoch=True, max_epochs=1, val_interval=1000)
cfg.train_dataloader.batch_size = 4
cfg.train_dataloader.num_workers = 0
cfg.train_dataloader.persistent_workers = False
cfg.train_dataloader.dataset.data_root = "/data/wow_set"
cfg.train_dataloader.dataset.ann_file = "smoke_46.json"
cfg.default_hooks.logger.interval = 1
if sys.argv[1] == "cpu":
    cfg.device = "cpu"
_load = torch.load
torch.load = lambda *a, **k: _load(*a, **{**k, "weights_only": False})
runner = Runner.from_cfg(cfg)
runner.train()
bn = [m for m in runner.model.backbone.modules() if isinstance(m, torch.nn.BatchNorm2d)]
print("BN in train mode:", sum(b.training for b in bn), "of", len(bn))
PY
ls /tmp/ft_smoke_wow | grep -c pth
