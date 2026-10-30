"""기관·담당자 계정 만들기 (명세 11.2, 11.6, 13.4).

고객 담당자(CLIENT)는 디바이스 코드로 스스로 가입하고(15.4), 크림오프 쪽 ADMIN·STAFF와 시연 계정은 이 스크립트로 만든다.
backend 폴더에서 실행한다.

    python -m scripts.seed --institution-code DEMO --institution-name "데모 병원" \\
        --login-id admin --name 관리자 --role ADMIN

- 비밀번호: --password를 빼면 화면에서 두 번 묻는다(입력이 보이지 않는다).
  --password로 주면 셸 기록에 남으니 시연용 계정에만 쓴다.
- 기관 코드가 이미 있으면 그 기관에 계정을 더한다. 없으면 기관도 만든다(이때 --institution-name 필요).
- 같은 아이디가 어느 기관에든 있으면 아무것도 만들지 않고 끝낸다(아이디는 모든 기관에서 유일하다, 12.2).
- 아이디는 로그인 때 입력 그대로(대소문자 구분) 비교하므로 앞뒤 공백을 허용하지 않는다.
- 기관 코드는 관리 화면 표시용이다(v1.12부터 로그인에 쓰지 않는다).
"""

import argparse
import getpass
import sys
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.core.config import SettingsError
from app.core.db import UNIQUE_VIOLATION, SessionLocal, db_error_code
from app.core.security import PasswordRuleError, hash_password
from app.models import Institution, Staff
from app.models.enums import StaffRole

# 13.4 입력 규칙과 12.2 컬럼 길이
INSTITUTION_CODE_MAX = 20
INSTITUTION_NAME_MAX = 100
LOGIN_ID_MAX = 50
STAFF_NAME_MAX = 50


class SeedError(Exception):
    """입력이 잘못되었거나 이미 있는 계정일 때. 메시지를 그대로 화면에 보여 준다."""


@dataclass(frozen=True)
class SeedResult:
    institution_id: uuid.UUID
    staff_id: uuid.UUID
    institution_created: bool


def _check_text(label: str, value: str, max_len: int) -> None:
    if not value:
        raise SeedError(f"{label}: 비어 있습니다")
    if value != value.strip():
        raise SeedError(f"{label}: 앞뒤에 공백이 있습니다")
    if len(value) > max_len:
        raise SeedError(f"{label}: {max_len}자 이하여야 합니다")


def create_account(
    session: Session,
    *,
    institution_code: str,
    institution_name: str | None,
    login_id: str,
    name: str,
    password: str,
    role: str = StaffRole.CLIENT,
) -> SeedResult:
    """기관(없으면)과 담당자 계정을 만든다. commit은 부르는 쪽이 한다."""
    _check_text("기관 코드", institution_code, INSTITUTION_CODE_MAX)
    _check_text("아이디", login_id, LOGIN_ID_MAX)
    _check_text("이름", name, STAFF_NAME_MAX)
    if institution_name is not None:
        _check_text("기관 이름", institution_name, INSTITUTION_NAME_MAX)
    try:
        staff_role = StaffRole(role)
    except ValueError:
        allowed = ", ".join(StaffRole)
        raise SeedError(f"역할: {allowed} 중 하나여야 합니다") from None
    try:
        # bcrypt는 0.2초쯤 걸린다. DB 작업 전에 끝내서 트랜잭션을 오래 잡지 않는다.
        password_hash = hash_password(password)
    except PasswordRuleError as error:
        raise SeedError(str(error)) from None

    try:
        institution = session.scalars(select(Institution).where(Institution.code == institution_code)).one_or_none()
        institution_created = institution is None
        if institution is None:
            if institution_name is None:
                raise SeedError(f"없는 기관 코드입니다({institution_code}). 새 기관이면 --institution-name을 적으세요")
            institution = Institution(code=institution_code, name=institution_name)
            session.add(institution)
            session.flush()
        elif institution_name is not None and institution_name != institution.name:
            raise SeedError(
                f"같은 기관 코드({institution_code})가 이미 다른 이름으로 있습니다. "
                "--institution-name을 빼면 그 기관에 계정을 더합니다"
            )

        duplicate = session.scalar(select(Staff.id).where(Staff.login_id == login_id))
        if duplicate is not None:
            raise SeedError(f"같은 아이디({login_id})가 이미 있습니다(아이디는 모든 기관에서 유일하다)")

        staff = Staff(
            institution_id=institution.id,
            login_id=login_id,
            password_hash=password_hash,
            name=name,
            role=staff_role.value,
        )
        session.add(staff)
        session.flush()
    except IntegrityError as error:
        # 다른 곳에서 같은 기관 코드·아이디를 동시에 만든 경우
        if db_error_code(error) == UNIQUE_VIOLATION:
            raise SeedError("같은 기관 코드나 아이디가 방금 만들어졌습니다. 다시 실행해 확인하세요") from None
        raise

    return SeedResult(institution_id=institution.id, staff_id=staff.id, institution_created=institution_created)


def _ask_password() -> str:
    first = getpass.getpass("비밀번호: ")
    second = getpass.getpass("비밀번호 다시: ")
    if first != second:
        raise SeedError("두 번 입력한 비밀번호가 다릅니다")
    return first


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m scripts.seed", description="기관·담당자 계정 만들기")
    parser.add_argument("--institution-code", required=True, help="기관 식별 코드 (1~20자, 관리 화면 표시용)")
    parser.add_argument("--institution-name", help="새 기관일 때만 필요 (1~100자)")
    parser.add_argument("--login-id", required=True, help="아이디 (1~50자)")
    parser.add_argument("--name", required=True, help="담당자 이름 (1~50자)")
    parser.add_argument(
        "--role",
        choices=[role.value for role in StaffRole],
        default=StaffRole.CLIENT.value,
        help="ADMIN·STAFF는 크림오프 쪽, CLIENT(기본값)는 고객 기관 담당자(11.6)",
    )
    parser.add_argument("--password", help="빼면 화면에서 묻는다. 8자 이상, UTF-8로 72바이트 이하")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        password = args.password if args.password is not None else _ask_password()
        with SessionLocal() as session, session.begin():
            result = create_account(
                session,
                institution_code=args.institution_code,
                institution_name=args.institution_name,
                login_id=args.login_id,
                name=args.name,
                password=password,
                role=args.role,
            )
    except SeedError as error:
        print(f"만들지 못했습니다: {error}", file=sys.stderr)
        return 1
    except SettingsError as error:
        print(error, file=sys.stderr)
        return 1
    except DBAPIError as error:
        print(
            f"DB 오류로 만들지 못했습니다({type(error.orig).__name__}). DATABASE_URL과 DB 실행 여부, "
            "alembic upgrade head를 했는지 확인하세요",
            file=sys.stderr,
        )
        return 1

    if result.institution_created:
        print(f"기관을 만들었습니다: {args.institution_code}")
    print(f"계정을 만들었습니다: 기관 {args.institution_code} / 아이디 {args.login_id} / 역할 {args.role}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
