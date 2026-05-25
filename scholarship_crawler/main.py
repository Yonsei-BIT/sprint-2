"""
장학금 크롤러 실행 진입점

사용법:
  python main.py                          # 전체 크롤링
  python main.py --source kosaf           # 특정 사이트만
  python main.py --query                  # 조건 필터링 조회
"""
import asyncio
import argparse
from rich.console import Console
from rich.table import Table

from crawlers import KosafCrawler, DreamsponCrawler, YonseiCrawler
from database import ScholarshipDB

console = Console()


async def run_crawlers(sources: list[str], db: ScholarshipDB):
    all_crawlers = {
        "kosaf": KosafCrawler(),
        "dreamspon": DreamsponCrawler(max_pages=3),
        "yonsei": YonseiCrawler(),
    }

    for name, crawler in all_crawlers.items():
        if sources and name not in sources:
            continue
        console.print(f"\n[bold cyan]크롤링 시작: {name}[/bold cyan]")
        try:
            scholarships = await crawler.crawl()
            saved = db.upsert(scholarships)
            console.print(f"[green]저장 완료: {saved}건[/green]")
        except Exception as e:
            console.print(f"[red]{name} 크롤링 실패: {e}[/red]")


def query_and_print(
    db: ScholarshipDB,
    gpa: float | None,
    income: int | None,
    year: int | None,
    major: str | None,
):
    results = db.query(gpa=gpa, income_bracket=income, year=year, major=major)

    if not results:
        console.print("[yellow]조건에 맞는 장학금이 없습니다.[/yellow]")
        return

    table = Table(title=f"장학금 검색 결과 ({len(results)}건)", show_lines=True)
    table.add_column("출처", style="cyan", width=10)
    table.add_column("장학금명", style="bold", width=30)
    table.add_column("지원 기관", width=15)
    table.add_column("금액", width=15)
    table.add_column("소득분위", width=8)
    table.add_column("성적기준", width=8)
    table.add_column("학년", width=12)
    table.add_column("URL", width=40)

    for s in results:
        years_str = ",".join(str(y) for y in s.target_years) if s.target_years else "전체"
        income_str = f"{s.income_bracket_max}분위↓" if s.income_bracket_max else "-"
        gpa_str = f"{s.gpa_min}↑" if s.gpa_min else "-"
        table.add_row(
            s.source,
            s.name[:28],
            s.organization[:14],
            s.amount_text[:14] or "-",
            income_str,
            gpa_str,
            years_str,
            s.source_url[:38],
        )

    console.print(table)

    # 상세 출력 (첫 3개)
    console.print("\n[bold]─── 상세 정보 (상위 3건) ───[/bold]")
    for s in results[:3]:
        console.print(f"\n[bold cyan]{s.name}[/bold cyan]")
        console.print(f"  기관: {s.organization}")
        console.print(f"  금액: {s.amount_text or '정보없음'}")
        if s.eligibility_text:
            preview = s.eligibility_text[:200].replace("\n", " ")
            console.print(f"  자격: {preview}...")
        if s.required_docs:
            console.print(f"  서류: {', '.join(s.required_docs[:5])}")
        console.print(f"  링크: [link={s.source_url}]{s.source_url}[/link]")


def main():
    parser = argparse.ArgumentParser(description="장학금 크롤러")
    parser.add_argument("--source", nargs="*", choices=["kosaf", "dreamspon", "yonsei"],
                        help="크롤할 사이트 (기본: 전체)")
    parser.add_argument("--query", action="store_true", help="크롤링 없이 DB 조회만")
    parser.add_argument("--reset", action="store_true", help="DB 초기화 후 크롤링")
    parser.add_argument("--gpa", type=float, help="성적 (예: 3.5)")
    parser.add_argument("--income", type=int, help="소득 분위 (예: 4)")
    parser.add_argument("--year", type=int, help="학년 (예: 2)")
    parser.add_argument("--major", type=str, help="전공/단과대 (예: 이공계)")
    parser.add_argument("--db", default="scholarships.db", help="DB 파일 경로")
    args = parser.parse_args()

    db = ScholarshipDB(args.db)

    if args.query:
        query_and_print(db, args.gpa, args.income, args.year, args.major)
    else:
        if args.reset:
            db.clear_all()
            console.print("[yellow]DB 초기화 완료[/yellow]")
        asyncio.run(run_crawlers(args.source or [], db))
        console.print("\n[bold green]크롤링 완료![/bold green]")

        if any([args.gpa, args.income, args.year, args.major]):
            query_and_print(db, args.gpa, args.income, args.year, args.major)


if __name__ == "__main__":
    main()
