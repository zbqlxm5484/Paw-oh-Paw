set -euo pipefail
mkdir -p /work/ssafy
mkdir -p /work/ssafy/paw_eval
(cd /ssafy/paw_eval && tar cf - --exclude=.venv --exclude=__pycache__ --exclude='*.json' --exclude=results . ) | (cd /work/ssafy/paw_eval && tar xf -)
ln -sfn /ssafy/dataset /work/ssafy/dataset
ln -sfn /ssafy/model /work/ssafy/model
cd /work/ssafy/paw_eval
cp ../model/pose.pth ../model/det.pth models/fs-v4/
python - <<'PY'
from pathlib import Path
p = Path("speed.py")
s = p.read_text(encoding="utf-8")
anchor = 'STACKS = {"mmdet-mmpose": MMDetMMPose}\n'
assert s.count(anchor) == 1
hook = anchor + (
    "try:\n"
    "    import sys as _sys\n"
    "    _sys.path.insert(0, '/exp/stacks')\n"
    "    from skipdet import register as _register\n"
    "    _register(STACKS, MMDetMMPose, best_dog)\n"
    "except ImportError:\n"
    "    pass\n")
p.write_text(s.replace(anchor, hook), encoding="utf-8")
PY
python -c "import speed; print('stacks:', sorted(speed.STACKS))"
