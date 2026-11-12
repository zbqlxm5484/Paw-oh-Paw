"""pilot20 태스크 job 을 라벨러에게 배정한다: python diag/assign.py pilot20-A gyuwon-label"""

import sys

from cvat_sdk.core.auth import ClientAuthParameters, make_client_from_cli

task_name, username = sys.argv[1], sys.argv[2]
c = make_client_from_cli(ClientAuthParameters(profile="local"))
user = next((u for u in c.users.list() if u.username == username), None)
if user is None:
    raise SystemExit(f"사용자 {username} 없음")
task = next(t for t in c.tasks.list() if t.name == task_name)
for j in task.get_jobs():
    j.update({"assignee": user.id})
    print(task_name, "job", j.id, "→", username)
