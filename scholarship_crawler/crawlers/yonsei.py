"""
연세대학교 장학금 공지사항 크롤러
URL: https://www.yonsei.ac.kr/sc/254/subview.do?enc=...
구조: 공지 목록(artclView 링크) → 상세(.board-view, 기간 정보 포함)
"""
import asyncio
import hashlib
import re
from datetime import date
from typing import Optional

from playwright.async_api import async_playwright, Page
from bs4 import BeautifulSoup

from models import Scholarship
from crawlers.base import BaseCrawler

LIST_URL = (
    "https://www.yonsei.ac.kr/sc/254/subview.do"
    "?enc=Zm5jdDF8QEB8JTJGYmJzJTJGc2MlMkY1OCUyRmFydGNsTGlzdC5kbyUzRmZpbmRDbFNlcSUzRDI1NyUyNg%3D%3D"
)
TODAY = date.today()


class YonseiCrawler(BaseCrawler):
    source = "yonsei"

    async def crawl(self) -> list[Scholarship]:
        results: list[Scholarship] = []

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            ctx = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                           "AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
            )
            page = await ctx.new_page()

            detail_links = await self._collect_list(page)
            print(f"[yonsei] 목록 수집: {len(detail_links)}건")

            for title, url in detail_links:
                try:
                    s = await self._parse_detail(page, title, url)
                    if s:
                        results.append(s)
                    await asyncio.sleep(1.0)
                except Exception as e:
                    print(f"[yonsei] 상세 실패 {url}: {e}")

            await browser.close()

        active = [r for r in results if r.is_active]
        print(f"[yonsei] 완료: 전체 {len(results)}건 → 모집중 {len(active)}건")
        return active

    async def _collect_list(self, page: Page) -> list[tuple[str, str]]:
        await page.goto(LIST_URL, timeout=20000, wait_until="networkidle")
        await page.wait_for_timeout(2000)

        links = await page.eval_on_selector_all(
            "a",
            "els => els.map(e => ({text: e.innerText.trim(), href: e.href}))"
        )

        result = []
        seen = set()
        for l in links:
            if "artclView" not in l["href"]:
                continue
            if l["href"] in seen:
                continue
            seen.add(l["href"])

            # 제목 정제: 번호, 날짜, 메타 제거
            title = re.sub(r"^\d+\s*", "", l["text"])
            title = re.sub(r"\s*새글\s*", "", title)
            title = re.sub(r"\s*일반공지\s*", "", title)
            title = re.sub(r"\s*작성일\d+.*", "", title, flags=re.DOTALL)
            title = re.sub(r"\s*기간\d+.*", "", title, flags=re.DOTALL)
            title = re.sub(r"\s*학생지원팀.*", "", title)
            title = re.sub(r"\s+", " ", title).strip()

            if title and len(title) > 4 and self.is_scholarship_notice(title):
                result.append((title, l["href"]))

        return result

    async def _parse_detail(self, page: Page, title: str, url: str) -> Optional[Scholarship]:
        await page.goto(url, timeout=20000, wait_until="networkidle")
        await page.wait_for_timeout(1500)

        html = await page.content()
        soup = BeautifulSoup(html, "lxml")

        board = soup.select_one(".board-view") or soup

        # 기간 파싱 (기간: 2026.05.26 ~ 2026.06.12)
        apply_start, apply_end = None, None
        full_text = board.get_text(separator="\n")
        period_m = re.search(
            r"기간\s*[:\n]?\s*"
            r"(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})"
            r"\s*[~\-]\s*"
            r"(?:(\d{4})[.\-])?(\d{1,2})[.\-](\d{1,2})",
            full_text
        )
        if period_m:
            try:
                g = period_m.groups()
                apply_start = date(int(g[0]), int(g[1]), int(g[2]))
                year = int(g[3]) if g[3] else int(g[0])
                apply_end = date(year, int(g[4]), int(g[5]))
            except ValueError:
                pass

        is_active = True
        if apply_end and apply_end < TODAY:
            is_active = False

        # 첨부파일 URL + 인라인 이미지 URL 수집
        attachment_urls = self.extract_attachment_urls(soup, "https://www.yonsei.ac.kr")
        image_urls = self.extract_inline_image_urls(soup, "https://www.yonsei.ac.kr")

        # PDF 추출 + 이미지 Vision 분석 동시 실행
        first_pdf = next((a for a in attachment_urls if a.lower().endswith(".pdf")), "")

        async def _no_img() -> dict:
            return {}

        attachment_text, img_data = await asyncio.gather(
            self.extract_pdf_text(first_pdf),
            self.ai_extract_from_images(image_urls, title, referer=url) if image_urls else _no_img(),
        )

        # 이미지에서 날짜·금액 보완
        if img_data:
            if not apply_start and img_data.get("apply_start") not in (None, "null"):
                try:
                    apply_start = date.fromisoformat(img_data["apply_start"])
                except (ValueError, TypeError):
                    pass
            if not apply_end and img_data.get("apply_end") not in (None, "null"):
                try:
                    apply_end = date.fromisoformat(img_data["apply_end"])
                    is_active = apply_end >= TODAY
                except (ValueError, TypeError):
                    pass

        # 텍스트 + PDF + 이미지 자격 정보를 합쳐 full_content 구성
        full_content = full_text + "\n" + attachment_text
        if img_data and img_data.get("eligibility") not in (None, "null"):
            full_content += "\n[이미지 추출] " + img_data["eligibility"]

        # 통합된 full_content 기준으로 필드 파싱
        gpa_min, gpa_scale = self.parse_gpa(full_content)
        income_max = self._extract_income(full_content)
        years = self.parse_years(full_content)
        amount_text = self._extract_amount(full_content)
        if not amount_text and img_data and img_data.get("amount_text") not in (None, "null"):
            amount_text = img_data["amount_text"]
        docs = self._extract_docs(full_content)

        region = self.parse_region(full_content)
        nationality = self.parse_nationality(full_content)
        enrollment_required = self.parse_enrollment_required(full_content)
        special_tags = self.parse_special_tags(full_content)
        no_duplicate = self.parse_no_duplicate(full_content)
        apply_url = self.extract_apply_url(full_content)

        # AI 요약: 텍스트 + 이미지 통합 내용 기반
        ai_summary = await self.ai_summarize(title, full_content)

        uid = hashlib.md5(url.encode()).hexdigest()[:12]
        return Scholarship(
            id=f"yonsei_{uid}",
            source=self.source,
            source_url=url,
            name=title,
            organization="연세대학교",
            description=full_text[:300],
            amount_text=amount_text,
            gpa_min=gpa_min,
            gpa_scale=gpa_scale,
            enrollment_required=enrollment_required,
            income_bracket_max=income_max,
            target_years=years,
            target_universities=["연세대학교"],
            region_requirement=region,
            nationality=nationality,
            special_tags=special_tags,
            no_duplicate_allowed=no_duplicate,
            eligibility_text=full_content[:2000],
            required_docs=docs,
            apply_start=apply_start,
            apply_end=apply_end,
            is_active=is_active,
            attachment_urls=attachment_urls,
            attachment_text=attachment_text[:3000],
            apply_url=apply_url,
            ai_summary=ai_summary,
        )

    def _extract_income(self, text: str) -> Optional[int]:
        if "소득무관" in text or "소득 무관" in text:
            return 10
        m = re.search(r"(\d+)\s*분위\s*이하", text)
        if m:
            return int(m.group(1))
        if "기초·차상위" in text or "기초차상위" in text:
            return 2
        if "기초생활수급" in text:
            return 1
        return None

    def _extract_amount(self, text: str) -> str:
        m = re.search(
            r"(?:장학금|지원금|장학혜택|선발금액)[^\n]{0,10}[:：]\s*([^\n]{5,60})",
            text
        )
        if m:
            return m.group(1).strip()
        m2 = re.search(r"(\d[\d,]*\s*(?:만원|원)(?:\s*/\s*\d[\d,]*\s*(?:만원|원))?)", text)
        if m2:
            return m2.group(1)
        return ""

    def _extract_docs(self, text: str) -> list[str]:
        m = re.search(
            r"(?:제출\s*서류|구비\s*서류)[^\n]*\n((?:.+\n){1,12})",
            text
        )
        if m:
            return self.parse_docs(m.group(1))
        docs = re.findall(r"[가-힣a-zA-Z]+(?:증명서|확인서|동의서|신청서|서류)", text)
        return list(dict.fromkeys(docs))[:8]
