"""견본 PDF 생성과 생성 시간 측정(D-08 견본 보고서, KPI-29 20초, 명세 8절·17.4 BE-15, S15P31A404-200). DB 없이 돈다.

    python -m scripts.report_samples <출력 폴더>                 # 경우 × 판본마다 입력 JSON과 PDF, 생성 시간 표
    python -m scripts.report_samples <출력 폴더> --html           # WeasyPrint 없이 HTML만(검사는 한다)
    python -m scripts.report_samples <출력 폴더> --repeat 3       # 같은 PDF를 3번 만들어 중앙값·최대를 적는다
    python -m scripts.report_samples <출력 폴더> --pool           # 워커처럼 풀(1개)에서 두 판본을 잇따라 만들어
                                                                  # 벽시계 시간을 잰다(주 반복 대기는 빠진다)
    python -m scripts.report_samples <출력 폴더> --case first --case no_passes

경우 목록은 app/report/samples.py(기업 승인 전 제안). 오차 범위는 --tolerance 파일(기본 config/tolerance.yaml) 값이다.
만든 PDF마다 실린 숫자를 입력의 수치 행에서 다시 계산한 값과 대조한다(8절 7번, report/verify.py). 어긋나거나, 기준에
있는 숫자가 실리지 않았거나, 검사에 걸리면 종료 코드 2다. 시간 표는 측정값일 뿐이고 KPI-29 판정은 실제 흐름으로 한다
(docs/report/reportTiming.md).
PDF는 저장소에 넣지 않는다(backend/docs/*.pdf 금지). 결과 표는 docs/report/reportTiming.md에 옮겨 적는다.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from app.report import ReportCheckError, ReportError
from app.report.checks import ensure_checked, summarize
from app.report.generate import generate_report, render
from app.report.samples import EDITIONS, case_names, sample_input
from app.report.verify import compare_numbers, reference_from_result
from app.report.verify import summarize as summarize_numbers
from app.services.tolerance import load_tolerance

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Timing:
    case: str
    edition: str
    pdf_bytes: int
    numbers: int
    runs_ms: tuple[int, ...]

    @property
    def median_ms(self) -> int:
        return int(statistics.median(self.runs_ms))

    @property
    def max_ms(self) -> int:
        return max(self.runs_ms)


def _write_input(out_dir: Path, case: str, edition: str, tolerance: dict[str, float]) -> Path:
    path = out_dir / f"{case}_{edition}.json"
    path.write_text(json.dumps(sample_input(case, edition, tolerance=tolerance), ensure_ascii=False, indent=2), "utf-8")
    return path


def _verify(input_path: Path, numbers) -> None:
    """실린 숫자를 입력의 회차 결과로 만든 기준값과 대조한다(기업 서버가 하는 것과 같은 방식)."""
    data = json.loads(input_path.read_text(encoding="utf-8"))
    verification = compare_numbers(numbers, reference_from_result(data["result"]))
    if not verification.ok or verification.omitted:
        raise ReportError(f"실린 숫자 대조 실패: {summarize_numbers(verification)}")


def _make_html(input_path: Path, output: Path) -> int:
    data = json.loads(input_path.read_text(encoding="utf-8"))
    rendered = render(data)
    ensure_checked(rendered.texts, edition=str(data.get("edition")))
    _verify(input_path, rendered.numbers)
    output.write_text(rendered.html, encoding="utf-8")
    return len(rendered.numbers)


def _make_pdf(input_path: Path, output: Path, repeat: int) -> Timing:
    runs: list[int] = []
    result = None
    for _ in range(repeat):
        result = generate_report(input_path, output, keep_html=True)
        runs.append(result.generation_ms)
    assert result is not None
    _verify(input_path, result.numbers)
    return Timing(input_path.stem.rsplit("_", 1)[0], result.edition, result.pdf_bytes, len(result.numbers), tuple(runs))


def _generate_in_child(input_path: str, output_path: str) -> int:
    """자식 프로세스에서 한 판본을 만든다(워커 app/worker/report.py와 같은 함수)."""
    return generate_report(Path(input_path), Path(output_path)).generation_ms


def _pool_timings(out_dir: Path, cases: list[str]) -> list[tuple[str, int, tuple[int, int]]]:
    """워커처럼 풀 1개에서 한 경우의 두 판본을 잇따라 만들어 (경우, 벽시계 ms, (OWNER ms, VET ms))를 돌려준다."""
    rows: list[tuple[str, int, tuple[int, int]]] = []
    with ProcessPoolExecutor(max_workers=1) as pool:
        for case in cases:
            started = time.perf_counter()
            futures = [
                pool.submit(
                    _generate_in_child,
                    str(out_dir / f"{case}_{edition}.json"),
                    str(out_dir / f"{case}_{edition}_pool.pdf"),
                )
                for edition in EDITIONS
            ]
            owner_ms, vet_ms = (future.result() for future in futures)
            rows.append((case, int((time.perf_counter() - started) * 1000), (owner_ms, vet_ms)))
    return rows


def _print_table(timings: list[Timing], repeat: int) -> None:
    header = "생성 시간 ms" + (f"(중앙값/최대, {repeat}회)" if repeat > 1 else "")
    print(f"\n| 경우 | 판본 | PDF bytes | 숫자 | {header} |")
    print("| --- | --- | --- | --- | --- |")
    for timing in timings:
        cell = f"{timing.median_ms} / {timing.max_ms}" if repeat > 1 else str(timing.runs_ms[0])
        print(f"| {timing.case} | {timing.edition} | {timing.pdf_bytes} | {timing.numbers} | {cell} |")
    worst = max(timings, key=lambda timing: timing.max_ms)
    print(f"\n가장 긴 생성 시간 {worst.max_ms} ms ({worst.case}/{worst.edition}). KPI-29 20초 판정이 아니다")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="견본 PDF 생성과 생성 시간 측정")
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--html", action="store_true", help="PDF 대신 HTML만 쓴다(WeasyPrint 불필요)")
    parser.add_argument("--repeat", type=int, default=1, help="PDF마다 생성 횟수(시간 측정용)")
    parser.add_argument(
        "--pool", action="store_true", help="자식 프로세스 풀(1개)에서 두 판본을 만들어 벽시계 시간도 잰다"
    )
    parser.add_argument("--case", action="append", choices=case_names(), help="이 경우만(여러 번 가능)")
    parser.add_argument("--tolerance", type=Path, default=ROOT / "config" / "tolerance.yaml", help="오차 범위 파일")
    args = parser.parse_args(argv)
    if args.repeat < 1:
        parser.error("--repeat는 1 이상이어야 합니다")

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    tolerance = load_tolerance(args.tolerance)
    cases = args.case or case_names()
    timings: list[Timing] = []
    try:
        for case in cases:
            for edition in EDITIONS:
                input_path = _write_input(out_dir, case, edition, tolerance)
                if args.html:
                    count = _make_html(input_path, out_dir / f"{case}_{edition}.html")
                    print(f"HTML {case}/{edition}: 숫자 {count}개")
                else:
                    timing = _make_pdf(input_path, out_dir / f"{case}_{edition}.pdf", args.repeat)
                    timings.append(timing)
                    print(
                        f"PDF {case}/{edition}: {timing.pdf_bytes} bytes, {timing.runs_ms} ms, 숫자 {timing.numbers}개"
                    )
        if timings:
            _print_table(timings, args.repeat)
        if args.pool and not args.html:
            print("\n| 경우 | 두 판본 벽시계 ms(풀 1개) | OWNER ms | VET ms |")
            print("| --- | --- | --- | --- |")
            rows = _pool_timings(out_dir, cases)
            for case, wall_ms, (owner_ms, vet_ms) in rows:
                print(f"| {case} | {wall_ms} | {owner_ms} | {vet_ms} |")
            worst = max(wall_ms for _, wall_ms, _ in rows)
            print(f"\n풀 벽시계 최대 {worst} ms. 주 반복 대기가 빠진 값이라 KPI-29 20초는 실제 흐름으로 판정한다")
    except ReportCheckError as error:
        print(f"검사 실패: {summarize(error.findings)}", file=sys.stderr)
        return 2
    except ReportError as error:
        print(f"실패: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
