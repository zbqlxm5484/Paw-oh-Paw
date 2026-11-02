"""차트(8절 만드는 순서 4): matplotlib Figure 객체로 그린다. pyplot을 쓰지 않아 워커 프로세스에 그림이 쌓이지 않는다.

지금은 보행 유형마다 가동 범위(rom_*) 좌우 막대 하나뿐이다(8절 "차트 종류는 최소로"). 결과는 HTML에 바로 넣는
PNG data URI다. 한글 글꼴은 시스템에서 찾고(맑은 고딕, 나눔고딕, Noto CJK), 없으면 수치 코드로 적는다.
범례는 축 위에, 값은 막대 끝에 적고, 그림 높이는 수치 줄 수에 따라 늘린다(한 줄이어도 잘리지 않게).
"""

from __future__ import annotations

import base64
import io
from functools import lru_cache

from matplotlib import font_manager
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties

from app.report.numbers import GaitTable

KOREAN_FONTS = ("Malgun Gothic", "NanumGothic", "Noto Sans CJK KR", "Noto Sans KR", "AppleGothic")
LEFT_COLOR, RIGHT_COLOR = "#4C72B0", "#DD8452"
ROM_PAIRS = (("LF", "RF"), ("LH", "RH"))


@lru_cache(maxsize=1)
def korean_font() -> FontProperties | None:
    """한글을 그릴 수 있는 시스템 글꼴. 없으면 None(그때는 영문 코드로 적는다)."""
    for name in KOREAN_FONTS:
        try:
            path = font_manager.findfont(FontProperties(family=name), fallback_to_default=False)
        except (ValueError, RuntimeError):
            continue
        return FontProperties(fname=path)
    return None


def _sized(font: FontProperties | None, size: float) -> FontProperties | None:
    if font is None:
        return None
    sized = font.copy()
    sized.set_size(size)
    return sized


def rom_chart(table: GaitTable) -> str | None:
    """가동 범위(rom_*)의 왼쪽·오른쪽 막대. 비교할 쌍이 하나도 없으면 None."""
    font = korean_font()
    labels: list[str] = []
    lefts: list[float] = []
    rights: list[float] = []
    for row in table.rows:
        if not row.code.startswith("rom_"):
            continue
        for left_limb, right_limb in ROM_PAIRS:
            left, right = row.cells.get(left_limb), row.cells.get(right_limb)
            if left and right and left.value is not None and right.value is not None:
                labels.append(row.label if font else row.code)
                lefts.append(left.value)
                rights.append(right.value)
    if not labels:
        return None
    small = _sized(font, 8)
    figure = Figure(figsize=(6.4, 1.0 + 0.45 * len(labels)), dpi=120)
    FigureCanvasAgg(figure)
    axis = figure.add_subplot(111)
    positions = list(range(len(labels)))
    height = 0.38
    left_bars = axis.barh([p - height / 2 for p in positions], lefts, height, color=LEFT_COLOR)
    right_bars = axis.barh([p + height / 2 for p in positions], rights, height, color=RIGHT_COLOR)
    for bars, values in ((left_bars, lefts), (right_bars, rights)):
        axis.bar_label(bars, labels=[f"{v:.1f}°" for v in values], padding=3, fontproperties=small)
    axis.set_yticks(positions)
    axis.set_yticklabels(labels, fontproperties=font)
    axis.invert_yaxis()  # 첫 수치가 위, 왼쪽 막대가 오른쪽 막대 위
    axis.set_xlim(0, max(lefts + rights) * 1.2)  # 값 글자가 들어갈 자리
    axis.set_xlabel("각도(°)" if font else "deg", fontproperties=small)
    axis.tick_params(axis="x", labelsize=8)
    axis.legend(
        [left_bars, right_bars],
        ["왼쪽", "오른쪽"] if font else ["L", "R"],
        prop=small,
        loc="lower left",
        bbox_to_anchor=(0, 1.0),
        ncol=2,
        frameon=False,
    )
    for spine in ("top", "right"):
        axis.spines[spine].set_visible(False)
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", bbox_inches="tight", pad_inches=0.08)  # 축 밖 범례까지 담는다
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
