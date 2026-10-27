import math

T13, ILIAC = 2, 13
PAIRS = {
    "front": ([3, 4, 5, 6, 7], [8, 9, 10, 11, 12]),
    "hind": ([14, 15, 16, 17], [18, 19, 20, 21]),
}


def body_len(kp):
    return math.hypot(kp[T13][0] - kp[ILIAC][0], kp[T13][1] - kp[ILIAC][1]) or 1.0


def swapped(kp, left, right):
    out = [list(p) for p in kp]
    for a, b in zip(left, right):
        out[a], out[b] = list(kp[b]), list(kp[a])
    return out


def pair_cost(prev, cur, left, right, L):
    s = 0.0
    for i in left + right:
        s += math.hypot(cur[i][0] - prev[i][0], cur[i][1] - prev[i][1])
    return s / (len(left) + len(right)) / L


def segments(frames):
    seg = []
    for i, f in enumerate(frames):
        if f is None:
            if seg:
                yield seg
            seg = []
        else:
            seg.append(i)
    if seg:
        yield seg


def correct(frames, penalty=0.02, pairs=("front", "hind")):
    out = [None if f is None else [list(p) for p in f["kp"]] for f in frames]
    flips = {k: [0] * len(frames) for k in pairs}
    for name in pairs:
        left, right = PAIRS[name]
        for seg in segments(frames):
            opts = [(out[i], swapped(out[i], left, right)) for i in seg]
            cost = [0.0, penalty]
            back = []
            for t in range(1, len(seg)):
                L = body_len(out[seg[t]])
                new, ptr = [], []
                for s in (0, 1):
                    c = [cost[p] + pair_cost(opts[t - 1][p], opts[t][s], left, right, L) for p in (0, 1)]
                    p = 0 if c[0] <= c[1] else 1
                    new.append(c[p] + (penalty if s else 0.0))
                    ptr.append(p)
                cost, back = new, back + [ptr]
            s = 0 if cost[0] <= cost[1] else 1
            states = [s]
            for ptr in reversed(back):
                s = ptr[s]
                states.append(s)
            states.reverse()
            for i, s in zip(seg, states):
                if s:
                    out[i] = swapped(out[i], left, right)
                    flips[name][i] = 1
    return out, flips
