import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

PAW = Path("/work/ssafy/paw_eval")
IMAGES = "/ssafy/dataset/keypoints_260820"
BASE_POSE = PAW / "models/fs-v4/pose.pth"
CV = Path("/exp/cv")
DATA = CV / "data"
RUNS = CV / "runs"
RESULTS = CV / "results.jsonl"


def sh(cmd, log):
    with open(log, "a", encoding="utf-8") as f:
        f.write("$ " + " ".join(map(str, cmd)) + "\n")
        f.flush()
        r = subprocess.run(list(map(str, cmd)), stdout=f, stderr=subprocess.STDOUT, cwd=PAW)
    if r.returncode:
        raise RuntimeError(f"{cmd[1] if len(cmd) > 1 else cmd[0]} 실패, {log}")


def flip_config():
    p = CV / "pose_flip.py"
    if not p.exists():
        p.write_text(f'_base_ = ["{PAW / "models/fs-v4/pose.py"}"]\nmodel = dict(test_cfg=dict(flip_test=True))\n', encoding="utf-8")
    return p


TESTS = {"ww": (DATA / "gt_ww.json", "/ssafy/dataset/keypoints_wowwow"), "pilot": (DATA / "gt_pilot.json", "/ssafy/pilot100_1027")}


def evaluate(weights, test, run_dir, log):
    gt, images = TESTS.get(test, (DATA / f"gt_{test}.json", IMAGES))
    out = {}
    for flip in (0, 1):
        cfg = flip_config() if flip else PAW / "models/fs-v4/pose.py"
        toml = run_dir / f"m_flip{flip}.toml"
        toml.write_text(f'name = "{run_dir.name}"\nbackend = "mmpose"\nconfig = "{cfg}"\nweights = "{weights}"\ndevice = "cuda:0"\n', encoding="utf-8")
        pred = run_dir / f"{test}_flip{flip}.preds.json"
        score = run_dir / f"{test}_flip{flip}.json"
        sh([sys.executable, "predict.py", "--model", toml, "--gt", gt, "--images", images, "--out", pred], log)
        sh([sys.executable, "score.py", "--gt", gt, "--pred", pred, "--out", score], log)
        k = json.loads(score.read_text(encoding="utf-8"))
        k = k.get("kpi", k)
        out[f"flip{flip}"] = {
            "kpi04": k["KPI-04"]["mae"], "kpi04_t": k["KPI-04"]["touched_only"]["mae"],
            "front": k["KPI-21"]["front"]["value"], "hind": k["KPI-21"]["hind"]["value"],
            "pck05": k["KPI-19"]["value"], "pck10": k["KPI-18"]["value"],
        }
        if test in TESTS:
            off = run_dir / f"{test}_flip{flip}.offset.json"
            sh([sys.executable, CV / "offset_analysis.py", "--gt", gt, "--pred", pred, "--out", off], log)
            o = json.loads(off.read_text(encoding="utf-8"))
            out[f"flip{flip}"].update(raw=o["raw_median_of_joints"], residual=o["residual_median_of_joints"])
    return out


def done_ids():
    if not RESULTS.exists():
        return set()
    return {json.loads(l)["id"] for l in RESULTS.read_text(encoding="utf-8").splitlines() if l.strip()}


def run(job):
    run_dir = RUNS / job["id"]
    run_dir.mkdir(parents=True, exist_ok=True)
    log = run_dir / "log.txt"
    t0 = time.time()
    weights = BASE_POSE
    if job.get("train"):
        tr = job["train"]
        args = [sys.executable, CV / "train_cv.py", "--train-json", DATA / tr["data"].format(f=job["fold"]), "--work-dir", run_dir]
        for k, v in tr.items():
            if k == "data":
                continue
            args += [f"--{k}"] + ([*map(str, v)] if isinstance(v, list) else [str(v)])
        sh(args, log)
        weights = run_dir / "final.pth"
    if job.get("wise"):
        src = RUNS / job["wise"]["from"] / "final.pth"
        weights = run_dir / "wise.pth"
        sh([sys.executable, CV / "wise.py", "--base", BASE_POSE, "--ft", src, "--alpha", job["wise"]["alpha"], "--out", weights], log)
    tests = job.get("tests") or [f"f{1 - job['fold']}"]
    evals = {t: evaluate(weights, t, run_dir, log) for t in tests}
    first = tests[0]
    res = {"id": job["id"], "group": job.get("group", ""), "fold_train": job["fold"],
           "fold_test": int(first[1:]) if first.startswith("f") and first[1:].isdigit() else first,
           "desc": job.get("desc", ""), "eval": evals[first], "evals": evals,
           "minutes": round((time.time() - t0) / 60, 1)}
    with open(RESULTS, "a", encoding="utf-8") as f:
        f.write(json.dumps(res, ensure_ascii=False) + "\n")
    if weights != BASE_POSE and job.get("keep_weights", 0) == 0:
        Path(weights).unlink(missing_ok=True)
    print(job["id"], res["eval"]["flip0"], flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("queue")
    a = ap.parse_args()
    done = done_ids()
    for line in Path(a.queue).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        job = json.loads(line)
        if job["id"] in done:
            continue
        try:
            run(job)
        except Exception as e:
            print("FAIL", job["id"], e, flush=True)
            with open(CV / "failed.txt", "a", encoding="utf-8") as f:
                f.write(f"{job['id']}\t{e}\n")


if __name__ == "__main__":
    main()
