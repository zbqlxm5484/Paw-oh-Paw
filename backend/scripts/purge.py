"""전체 파기: python -m scripts.purge --all (명세 7절 보관과 파기, 15.9, S15P31A404-199).

과제가 끝난 뒤 모든 기관의 반려견 자료(DB 행과 파일)를 지우고 purge_log에 기록을 남긴다. 기관·담당자 계정·디바이스
코드는 남긴다. 여러 기관을 한꺼번에 지우는 ALL은 API로 열지 않고 서버에서 이 스크립트로만 한다. backend 폴더에서
실행한다.

    python -m scripts.purge --all            # 지울 양만 센다(dry run). 아무것도 지우지 않는다
    python -m scripts.purge --all --execute  # 실제로 지운다. 확인 문구 PURGE를 입력해야 한다(--yes면 묻지 않는다)

지운 뒤에는 파기 기록 ID와 행·파일 수·바이트를 출력한다(파기 확인서 D-13에 붙인다). 분석 중인 촬영이 있으면 지우지
않고 끝낸다.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable

from sqlalchemy.exc import DBAPIError

from app.core.config import SettingsError
from app.core.db import SessionLocal
from app.core.errors import AppError
from app.models.enums import PurgeScope
from app.services.purge import purge
from app.storage.base import get_storage

CONFIRM_WORD = "PURGE"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m scripts.purge", description="모든 기관의 반려견 자료 파기(ALL)")
    parser.add_argument("--all", action="store_true", required=True, help="모든 기관의 반려견 자료를 대상으로 한다")
    parser.add_argument("--execute", action="store_true", help="실제로 지운다. 없으면 지울 양만 센다")
    parser.add_argument("--yes", action="store_true", help="--execute 때 확인 문구를 묻지 않는다")
    return parser


def run(argv: list[str] | None = None, *, ask: Callable[[str], str] = input) -> int:
    """스크립트 본체. ask는 확인 문구를 받는 함수(테스트에서 바꿔 끼운다)."""
    args = _parser().parse_args(argv)
    if args.execute and not args.yes:
        answer = ask(f"모든 기관의 반려견 자료를 지웁니다. 계속하려면 {CONFIRM_WORD}를 입력하세요: ")
        if answer.strip() != CONFIRM_WORD:
            print("취소했습니다. 아무것도 지우지 않았습니다", file=sys.stderr)
            return 1
    try:
        with SessionLocal() as session, session.begin():
            result = purge(session, get_storage(), PurgeScope.ALL.value, dry_run=not args.execute)
    except AppError as error:
        print(f"지우지 못했습니다: {error.code.value}", file=sys.stderr)
        return 1
    except SettingsError as error:
        print(error, file=sys.stderr)
        return 1
    except DBAPIError as error:
        print(
            f"DB 오류로 지우지 못했습니다({type(error.orig).__name__}). DATABASE_URL과 DB 실행 여부를 확인하세요",
            file=sys.stderr,
        )
        return 1

    label = "지울 양(dry run, 아무것도 지우지 않음)" if result.dry_run else "지운 양"
    print(f"{label}: 행 {result.rows}개, 파일 {result.files}개, {result.bytes} bytes")
    if result.purge_log_id is not None:
        print(f"파기 기록 ID: {result.purge_log_id}")
    return 0


def main(argv: list[str] | None = None) -> int:
    return run(argv)


if __name__ == "__main__":
    sys.exit(main())
