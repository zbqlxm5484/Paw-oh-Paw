"""라벨 맞추기 태스크(pilot20-*)의 골격을 /work/pilot/labels.json 으로 꺼낸다."""

import json

from cvat_sdk.core.auth import ClientAuthParameters, make_client_from_cli

c = make_client_from_cli(ClientAuthParameters(profile="local"))
labels = c.projects.retrieve(1).get_labels()
dog = next(l for l in labels if l.name == "dog")
kp_name = {s.id: s.name for s in dog.sublabels}
attr = {a.id: a.name for a in dog.attributes}
out = {}
for t in c.tasks.list():
    if not t.name.startswith("pilot20-"):
        continue
    frames = [f.name for f in t.get_frames_info()]
    jobs = t.get_jobs()
    rec = {
        "task_id": t.id,
        "assignee": [j.assignee.username if j.assignee else None for j in jobs],
        "state": [j.state for j in jobs],
        "frames": {},
    }
    for s in t.get_annotations().shapes:
        if s.label_id != dog.id:
            continue
        rec["frames"].setdefault(frames[s.frame], []).append(
            {
                "source": s.source,
                "attrs": {attr[a["spec_id"]]: a["value"] for a in s.attributes},
                "kp": {
                    kp_name[e.label_id]: [
                        e.points[0],
                        e.points[1],
                        bool(e.occluded),
                        bool(e.outside),
                    ]
                    for e in s.elements
                },
            }
        )
    out[t.name] = rec
json.dump(out, open("/work/pilot/labels.json", "w", encoding="utf-8"), ensure_ascii=False)
print({k: (v["state"], v["assignee"], len(v["frames"])) for k, v in out.items()})
