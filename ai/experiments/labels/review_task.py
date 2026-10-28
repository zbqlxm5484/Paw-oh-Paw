"""시험 라벨 100장 검수 태스크를 만들고(팀원 점을 시작점으로), 백업 zip 으로 내보낸다 (10-26).
docker compose run --rm autolabel python diag/review_task.py
"""

import os
import time

import cvat_sdk.models as models
from cvat_sdk.core.auth import ClientAuthParameters, make_client_from_cli
from cvat_sdk.core.proxies.tasks import ResourceType

NAME = "review100-hjw"
SRC = "/work/frames_review/review100"
XML = "/work/dump/review100_annotations.xml"
OUT = "/work/dump/검수_시험라벨100_review100.zip"
client = make_client_from_cli(ClientAuthParameters(profile="local"))
if any(t.name == NAME for t in client.tasks.list()):
    raise SystemExit(f"{NAME} 이미 있음")
files = sorted(os.path.join(SRC, f) for f in os.listdir(SRC) if f.endswith(".jpg"))
task = client.tasks.create_from_data(
    spec=models.TaskWriteRequest(name=NAME, project_id=1, segment_size=500),
    resources=files,
    resource_type=ResourceType.LOCAL,
    data_params={"image_quality": 95, "sorting_method": "lexicographical"},
)
print("task", task.id, task.size, flush=True)
task.import_annotations("CVAT 1.1", XML)
ann = task.get_annotations()
print("shapes", len(ann.shapes), "첫 장 점", len(ann.shapes[0].elements), flush=True)
time.sleep(2)
task.download_backup(OUT)
print("->", OUT)
