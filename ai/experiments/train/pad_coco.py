import argparse
import json

N_OUT = 46
N_IN = 22


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--drop-untouched", action="store_true")
    ap.add_argument("--visible-only", action="store_true")
    a = ap.parse_args()
    d = json.load(open(a.src, encoding="utf-8"))
    dropped = kept = 0
    for ann in d["annotations"]:
        k = ann["keypoints"]
        touched = (ann.get("attributes") or {}).get("touched") or [1] * N_IN
        out = []
        for i in range(N_IN):
            x, y, v = k[3 * i], k[3 * i + 1], int(k[3 * i + 2])
            if a.visible_only and v != 2:
                v = 0
            if a.drop_untouched and not touched[i] and v > 0:
                v = 0
                dropped += 1
            kept += v > 0
            out += [x, y, v]
        out += [0, 0, 0] * (N_OUT - N_IN)
        ann["keypoints"] = out
        ann["num_keypoints"] = sum(1 for i in range(N_OUT) if out[3 * i + 2] > 0)
    cat = d["categories"][0]
    cat["keypoints"] = cat["keypoints"][:N_IN] + [f"kp_{i}" for i in range(N_IN, N_OUT)]
    json.dump(d, open(a.out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{a.out}: images {len(d['images'])}, annotations {len(d['annotations'])}, points used {kept}, untouched dropped {dropped}")


if __name__ == "__main__":
    main()
