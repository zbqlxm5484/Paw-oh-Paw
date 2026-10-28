"""fs-v4 관절점 모델 이어 학습 실행부 (Colab·로컬 컨테이너 공용, 10-22).

    python train.py --config ft_creamoff.py --work-dir runs/e1 \
        --cfg-options train_dataloader.dataset.ann_file=/content/data/train46.json \
                      train_dataloader.dataset.data_root=/content/data/img/
    python train.py --strip runs/e1/epoch_10.pth --out runs/e1/pose_e10.pth   # paw_eval 용 가중치만 남기기

--resume 을 주면 work-dir 의 마지막 체크포인트에서 이어 간다(Colab 런타임이 끊겼을 때).
"""

import argparse
import os
import sys


def strip(src, out):
    import torch

    ckpt = torch.load(src, map_location="cpu", weights_only=False)
    keep = {
        "state_dict": ckpt["state_dict"],
        "meta": {
            k: v for k, v in ckpt.get("meta", {}).items() if k in ("dataset_meta", "epoch", "iter")
        },
    }
    torch.save(keep, out)
    print(f"-> {out}")


def main():
    from mmengine.config import Config, DictAction

    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    ap.add_argument("--work-dir")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--cfg-options", nargs="+", action=DictAction)
    ap.add_argument("--strip", help="학습 체크포인트에서 가중치만 남긴다")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.strip:
        return strip(a.strip, a.out)

    from mmengine.runner import Runner
    from mmpose.utils import register_all_modules

    register_all_modules()
    cfg = Config.fromfile(a.config)
    if a.cfg_options:
        cfg.merge_from_dict(a.cfg_options)
    if cfg.get("load_from") and not os.path.isabs(cfg.load_from):  # 설정 파일 기준 상대 경로
        cfg.load_from = os.path.join(os.path.dirname(os.path.abspath(a.config)), cfg.load_from)
    cfg.work_dir = a.work_dir
    cfg.resume = a.resume
    if cfg.model.backbone.get("norm_eval") is not True:
        sys.exit(
            "norm_eval=True 가 아니다. BN 통계가 바뀌어 기준선보다 나빠진다(docs/training/poseFinetune.md)"
        )
    Runner.from_cfg(cfg).train()


if __name__ == "__main__":
    main()
