import sys
from pathlib import Path

root = Path(sys.argv[1]).expanduser().resolve()
p = root / "paw_eval" / "speed.py"
s = p.read_text(encoding="utf-8")
anchor = 'STACKS = {"mmdet-mmpose": MMDetMMPose}\n'
if "skipdet2" not in s:
    assert s.count(anchor) == 1
    hook = anchor + (
        "import sys as _sys\n"
        f"_sys.path.insert(0, {str(root / 'stacks')!r})\n"
        "from skipdet2 import register as _register2\n"
        "_register2(STACKS, MMDetMMPose, best_dog)\n")
    p.write_text(s.replace(anchor, hook), encoding="utf-8")
print("patched")
