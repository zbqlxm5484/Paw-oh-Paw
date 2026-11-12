"""보고서 미리보기(8절, S15P31A404-195): 입력 JSON 하나로 PDF(또는 HTML만)를 만든다. DB 없이 돈다.

    python -m scripts.make_report <입력.json> <출력.pdf>            # 검사까지 한 뒤 PDF
    python -m scripts.make_report <입력.json> <출력.html> --html    # WeasyPrint 없이 HTML만(검사는 한다)
    python -m scripts.make_report --sample <출력.json>             # 견본 입력 JSON을 만든다(모양 참고용)

입력 모양은 app/report/inputs.py 머리말. 견본은 tests/report_fixtures.py의 sample_input과 같다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.report import ReportCheckError, ReportError
from app.report.checks import ensure_checked, summarize
from app.report.generate import generate_report, render


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="보고서 미리보기")
    parser.add_argument("input", type=Path, nargs="?")
    parser.add_argument("output", type=Path, nargs="?")
    parser.add_argument("--html", action="store_true", help="PDF 대신 HTML만 쓴다")
    parser.add_argument("--sample", type=Path, metavar="OUT.json", help="견본 입력 JSON을 쓴다")
    args = parser.parse_args(argv)

    if args.sample:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from tests.report_fixtures import sample_input  # noqa: PLC0415 - 테스트 견본을 그대로 쓴다

        args.sample.write_text(json.dumps(sample_input(), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"견본 입력: {args.sample.name}")
        return 0
    if args.input is None or args.output is None:
        parser.error("입력 JSON과 출력 경로가 필요합니다")
    try:
        if args.html:
            data = json.loads(args.input.read_text(encoding="utf-8"))
            rendered = render(data)
            ensure_checked(rendered.texts, edition=str(data.get("edition")))
            args.output.write_text(rendered.html, encoding="utf-8")
            print(f"HTML {args.output.name}, 실린 숫자 {len(rendered.numbers)}개")
        else:
            result = generate_report(args.input, args.output, keep_html=True)
            print(
                f"PDF {args.output.name} {result.pdf_bytes} bytes, {result.generation_ms} ms, "
                f"숫자 {len(result.numbers)}개"
            )
    except ReportCheckError as error:
        print(f"검사 실패: {summarize(error.findings)}")
        return 2
    except ReportError as error:
        print(f"실패: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
