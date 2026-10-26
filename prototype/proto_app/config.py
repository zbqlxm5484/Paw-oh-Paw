"""Paw oh Paw 프로토타입 설정값과 고정 목록 (디자인 PawOhPaw_web.html의 상수를 옮김)."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR.parent / "uploads"

MAX_SHOTS = 16                 # 한 회차 영상 수 (4초씩 16개)
ANALYSIS_SEC = 7.0             # 분석 시뮬레이션 시간. 실제 분석은 영상당 20~30초
MODEL = "v1"
VIDEO_EXT = {".mp4", ".mov", ".m4v"}

# 회차 상태: 라벨, 배경색, 글자색
ST = {
    "ok": ("유효", "#E8F3EC", "#2E8B57"),
    "part": ("일부 유효", "#FAF1DF", "#9A6A12"),
    "fail": ("실패", "#F8E7E3", "#C2412D"),
}
STEPS = ["업로드 완료", "반려견 찾는 중", "관절점 찾는 중", "보행 수치 계산 중", "보고서 만드는 중"]

SEX = {"m": "수컷", "f": "암컷", "mn": "중성화 수컷", "fs": "중성화 암컷"}
SIZE = {"S": "소형", "M": "중형", "L": "대형"}
LIMB = {"LF": "왼앞", "RF": "오른앞", "LH": "왼뒤", "RH": "오른뒤"}

BREEDS = ["말티즈", "푸들", "토이 푸들", "포메라니안", "시츄", "치와와", "비숑 프리제", "요크셔테리어", "닥스훈트",
          "미니어처 슈나우저", "웰시코기", "비글", "시바견", "진돗개", "풍산개", "골든 리트리버", "래브라도 리트리버",
          "보더콜리", "프렌치 불독", "퍼그", "사모예드", "시베리안 허스키", "저먼 셰퍼드", "스피츠",
          "이탈리안 그레이하운드", "잭 러셀 테리어", "말라뮤트", "믹스견"]
SMALL_BREEDS = ["말티즈", "푸들", "토이 푸들", "포메라니안", "시츄", "치와와", "비숑 프리제", "요크셔테리어", "닥스훈트",
                "미니어처 슈나우저", "퍼그", "이탈리안 그레이하운드", "잭 러셀 테리어"]
LARGE_BREEDS = ["골든 리트리버", "래브라도 리트리버", "사모예드", "시베리안 허스키", "저먼 셰퍼드", "말라뮤트", "풍산개"]


def auto_size(breed: str, kg) -> str:
    """견종으로 먼저, 모르는 견종이면 체중(10 kg, 25 kg)으로 체급을 정한다."""
    if breed in SMALL_BREEDS:
        return "S"
    if breed in LARGE_BREEDS:
        return "L"
    if breed in BREEDS and breed != "믹스견":
        return "M"
    try:
        w = float(kg)
    except (TypeError, ValueError):
        return "M"
    if not w:
        return "M"
    return "S" if w < 10 else ("M" if w < 25 else "L")
