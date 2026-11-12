"""분석 API 저장소 전체 파기: python purge.py --all (팀 서비스 scripts/purge.py와 짝, 백엔드 명세 7절·15.9)

과제가 끝난 뒤 분석 API가 남긴 모든 작업(올린 영상, 작업 상태, 결과, 관절점 파일)과 analyses.jsonl을 지운다.
팀 서비스 파기만 하면 같은 영상과 결과가 여기 남으므로 함께 돌린다. analysis_api 폴더에서 실행한다.

    python purge.py --all            # 지울 양만 센다(dry run). 아무것도 지우지 않는다
    python purge.py --all --execute  # 실제로 지운다. 확인 문구 PURGE를 입력해야 한다(--yes면 묻지 않는다)

분석 중인 작업이 있으면 지우지 않고 끝낸다. 분석 API를 끈 뒤 돌리는 것이 안전하다.
관절점 파일(data/tracks/)과 models.yaml은 지우지 않는다. 이름이 작업 ID(UUID) 모양인 폴더와 analyses.jsonl만 지우므로,
ANALYSIS_STORAGE_DIR를 잘못 줘도 다른 폴더는 남는다(남긴 개수를 알린다).
"""
import argparse
import os
import sys
from pathlib import Path
from typing import Callable, Optional

import store

HERE = Path(__file__).resolve().parent
CONFIRM_WORD = "PURGE"


def storage_dir() -> Path:
    return Path(os.environ.get("ANALYSIS_STORAGE_DIR", HERE.parent / "data" / "analysis_api"))


def run(argv: Optional[list] = None, *, ask: Callable[[str], str] = input, root: Optional[Path] = None) -> int:
    parser = argparse.ArgumentParser(prog="python purge.py", description="분석 API 저장소 전체 파기")
    parser.add_argument("--all", action="store_true", required=True, help="모든 작업을 대상으로 한다")
    parser.add_argument("--execute", action="store_true", help="실제로 지운다. 없으면 지울 양만 센다")
    parser.add_argument("--yes", action="store_true", help="--execute 때 확인 문구를 묻지 않는다")
    args = parser.parse_args(argv)
    root = root or storage_dir()

    stats = store.purge_stats(root)
    if stats["unfinished"]:
        print(f"분석 중인 작업이 {stats['unfinished']}개 있어 지우지 않았습니다. 분석 API를 끈 뒤 다시 실행하세요",
              file=sys.stderr)
        return 1
    if stats["others"]:
        print(f"작업 폴더가 아닌 것 {stats['others']}개는 지우지 않습니다(이름이 작업 ID 모양이 아님). "
              f"ANALYSIS_STORAGE_DIR가 맞는지 확인하세요: {root}", file=sys.stderr)
    if not args.execute:
        print(f"지울 양(dry run, 아무것도 지우지 않음): 작업 {stats['jobs']}개, 파일 {stats['files']}개, {stats['bytes']} bytes")
        return 0
    if not args.yes:
        answer = ask(f"분석 API 저장소({root})의 모든 작업을 지웁니다. 계속하려면 {CONFIRM_WORD}를 입력하세요: ")
        if answer.strip() != CONFIRM_WORD:
            print("취소했습니다. 아무것도 지우지 않았습니다", file=sys.stderr)
            return 1
    try:
        done = store.purge_all(root)
    except OSError as error:
        print(f"다 지우지 못했습니다: {error}. 권한이나 사용 중인 파일을 확인하고 다시 실행하세요", file=sys.stderr)
        return 1
    print(f"지운 양: 작업 {done['jobs']}개, 파일 {done['files']}개, {done['bytes']} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(run())
