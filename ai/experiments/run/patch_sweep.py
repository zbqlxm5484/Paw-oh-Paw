from pathlib import Path

p = Path("/work/ssafy/paw_eval/speed.py")
s = p.read_text(encoding="utf-8")
if "skipdet2" not in s:
    anchor = "    _register(STACKS, MMDetMMPose, best_dog)\n"
    assert s.count(anchor) == 1, "setup.sh 를 먼저 실행해야 한다"
    s = s.replace(anchor, anchor + "    _sys.path.insert(0, '/exp/eval_runs')\n"
                                   "    from skipdet2 import register as _register2\n"
                                   "    _register2(STACKS, MMDetMMPose, best_dog)\n")
    p.write_text(s, encoding="utf-8")
print("patched")
