"""비밀번호 해시 (명세 11.2 security.py, 13.4).

JWT와 서명 URL은 로그인 작업(작업 단위 3)에서 이 파일에 더한다.
"""

import bcrypt

PASSWORD_MIN_CHARS = 8
# bcrypt 5.0은 72바이트를 넘는 비밀번호를 받으면 오류를 낸다. 한글 한 글자는 UTF-8로 3바이트다.
PASSWORD_MAX_BYTES = 72


class PasswordRuleError(ValueError):
    """비밀번호가 13.4 규칙에 맞지 않을 때."""


def check_password_rule(password: str) -> None:
    """계정을 만들 때만 검사한다. 로그인에서는 길이를 검사하지 않는다(13.4)."""
    if len(password) < PASSWORD_MIN_CHARS:
        raise PasswordRuleError(f"비밀번호는 {PASSWORD_MIN_CHARS}자 이상이어야 합니다")
    if len(password.encode("utf-8")) > PASSWORD_MAX_BYTES:
        raise PasswordRuleError(
            f"비밀번호는 UTF-8로 {PASSWORD_MAX_BYTES}바이트 이하여야 합니다(한글 한 글자는 3바이트)"
        )


def hash_password(password: str) -> str:
    """규칙을 검사한 뒤 bcrypt 해시를 돌려준다. DB에는 이 값만 저장한다."""
    check_password_rule(password)
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    """비밀번호가 해시와 맞으면 True. 72바이트를 넘으면 bcrypt를 부르지 않고 False다(13.4)."""
    data = password.encode("utf-8")
    if len(data) > PASSWORD_MAX_BYTES:
        return False
    return bcrypt.checkpw(data, password_hash.encode("ascii"))
