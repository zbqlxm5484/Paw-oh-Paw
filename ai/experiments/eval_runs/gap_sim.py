import json
import os

R = os.environ.get("CREAMOFF_ROOT", "C:/Users/SSAFY/Desktop/jjh/ssafy") + "/experiments/results/sweep_1027/"
base = json.load(open(R + "base.track.json", encoding="utf-8"))["videos"]


def simulate(has, k, mode):
    n = len(has)
    keys = sorted(set(range(0, n, k)) | {n - 1})
    found = {j: has[j] for j in keys}
    calls = len(keys)
    for a, b in zip(keys, keys[1:]):
        if b - a <= 1:
            continue
        if found[a] and found[b]:
            for j in range(a + 1, b):
                found[j] = True
        elif not found[a] and not found[b]:
            if mode == "skip":
                for j in range(a + 1, b):
                    found[j] = False
            elif mode == "probe":
                m = (a + b) // 2
                calls += 1
                if has[m]:
                    for j in range(a + 1, b):
                        found[j] = has[j]
                    calls += b - a - 2
                else:
                    for j in range(a + 1, b):
                        found[j] = False
            else:
                for j in range(a + 1, b):
                    found[j] = has[j]
                calls += b - a - 1
        else:
            for j in range(a + 1, b):
                found[j] = has[j]
            calls += b - a - 1
    return sum(bool(found[j]) for j in range(n)), calls


tot_frames = sum(len(v["frames"]) for v in base)
print("영상", len(base), "프레임", tot_frames, "기준 탐지", sum(f is not None for v in base for f in v["frames"]))
print("K  방식   잃은프레임  최악영상(%p)  탐지호출(기준 대비)")
for k in (2, 3, 4, 5, 6, 8):
    for mode in ("skip", "probe", "full"):
        lost, calls, worst = 0, 0, 0.0
        for v in base:
            has = [f is not None for f in v["frames"]]
            f, c = simulate(has, k, mode)
            lost += sum(has) - f
            calls += c
            worst = min(worst, (f - sum(has)) / len(has) * 100)
        print(f"{k}  {mode:5}  {lost:5}  {worst:8.2f}  {calls / tot_frames:.3f}")
