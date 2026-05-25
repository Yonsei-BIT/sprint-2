"""
한국장학재단 장학금 공지사항 크롤러
URL: https://www.kosaf.go.kr/ko/notice.do?ctgrId1=0000000002
구조: 목록 테이블(번호/제목/등록일) → 상세 페이지(본문 텍스트)
"""
import asyncio
import hashlib
import re
from datetime import date, datetime
from typing import Optional

from playwright.async_api import async_playwright, Page
from bs4 import BeautifulSoup

from models import Scholarship
from crawlers.base import BaseCrawler

BASE = "https://www.kosaf.go.kr"
LIST_URL = f"{BASE}/ko/notice.do?ctgrId1=0000000002&ctgrId2=&searchStr=&searchType=&page={{page}}&pg="
DETAIL_URL = f"{BASE}/ko/notice.do?mode=view&ctgrId1=0000000002&ctgrId2=&seqNo={{seqNo}}"

TODAY = date.today()


class KosafCrawler(BaseCrawler):
    source = "kosaf"

    def __init__(self, max_pages: int = 3):
        self.max_pages = max_pages

    async def crawl(self) -> list[Scholarship]:
        results: list[Scholarship] = []

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            ctx = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                           "AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
            )
            page = await ctx.new_page()

            items = await self._collect_list(page)
            print(f"[kosaf] 목록 수집: {len(items)}건")

            for item in items:
                try:
                    s = await self._parse_detail(page, item)
                    if s:
                        results.append(s)
                    await asyncio.sleep(1.0)
                except Exception as e:
                    print(f"[kosaf] 상세 실패 seqNo={item['seqNo']}: {e}")

            await browser.close()

        active = [r for r in results if r.is_active]
        print(f"[kosaf] 완료: 전체 {len(results)}건 → 모집중 {len(active)}건")
        return active

    async def _collect_list(self, page: Page) -> list[dict]:
        items: list[dict] = []
        for pg in range(1, self.max_pages + 1):
            await page.goto(LIST_URL.format(page=pg), timeout=20000, wait_until="networkidle")
            await page.wait_for_timeout(2000)
            html = await page.content()
            soup = BeautifulSoup(html, "lxml")

            found = 0
            for a in soup.select("tbody td a[href*='seqNo']"):
                href = a.get("href", "")
                m = re.search(r"seqNo=(\d+)", href)
                if not m:
                    continue
                seq_no = m.group(1)
                title = a.get_text(strip=True)

                # 같은 행에서 날짜 추출
                row = a.find_parent("tr")
                date_text = ""
                if row:
                    tds = row.select("td")
                    for td in tds:
                        t = td.get_text(strip=True)
                        if re.match(r"\d{4}\.\d{2}\.\d{2}", t):
                            date_text = t
                            break

                if not self.is_scholarship_notice(title):
                    continue
                items.append({"seqNo": seq_no, "title": title, "date": date_text})
                found += 1

            print(f"[kosaf] page {pg}: {found}건")
            if found == 0:
                break
            await asyncio.sleep(1.0)

        return items

    async def _parse_detail(self, page: Page, item: dict) -> Optional[Scholarship]:
        url = DETAIL_URL.format(seqNo=item["seqNo"])
        await page.goto(url, timeout=20000, wait_until="networkidle")
        await page.wait_for_timeout(2000)

        html = await page.content()
        soup = BeautifulSoup(html, "lxml")

        # 본문: 작성자/날짜가 있는 행 바로 다음 행의 td
        content = ""
        rows = soup.select("table tr")
        for i, row in enumerate(rows):
            txt = row.get_text()
            if "작성자" in txt and "작성일" in txt:
                # 다음 행이 본문
                if i + 1 < len(rows):
                    content = rows[i + 1].get_text(separator="\n", strip=True)
                break

        if not content:
            content = soup.get_text(separator="\n")

        # 만료 판단: 신청기간 내 마감일 파싱
        apply_start, apply_end = self._extract_period(content)
        is_active = True
        if apply_end and apply_end < TODAY:
            is_active = False

        # 첨부파일
        attachment_urls = self.extract_attachment_urls(soup, BASE)
        attachment_text = ""
        for au in attachment_urls:
            if au.lower().endswith(".pdf"):
                txt = await self.extract_pdf_text(au)
                if txt:
                    attachment_text += txt + "\n"
                    break  # 첫 PDF만 추출

        # PDF 텍스트로 본문 보강
        full_content = content + "\n" + attachment_text

        gpa_min, gpa_scale = self.parse_gpa(full_content)
        income_max = self._extract_income(full_content)
        years = self.parse_years(full_content)
        docs = self.parse_docs(self._extract_docs_section(full_content))
        amount_text = self._extract_amount(full_content)

        region = self.parse_region(full_content)
        nationality = self.parse_nationality(full_content)
        enrollment_required = self.parse_enrollment_required(full_content)
        special_tags = self.parse_special_tags(full_content)
        no_duplicate = self.parse_no_duplicate(full_content)

        apply_url = self.extract_apply_url(full_content)
        ai_summary = await self.ai_summarize(item["title"], full_content)

        uid = hashlib.md5(f"kosaf_{item['seqNo']}".encode()).hexdigest()[:12]
        return Scholarship(
            id=f"kosaf_{uid}",
            source=self.source,
            source_url=url,
            name=item["title"],
            organization="한국장학재단",
            description=content[:300],
            amount_text=amount_text,
            gpa_min=gpa_min,
            gpa_scale=gpa_scale,
            enrollment_required=enrollment_required,
            income_bracket_max=income_max,
            target_years=years,
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

    def _extract_period(self, text: str) -> tuple[Optional[date], Optional[date]]:
        # 형식 예: "2026. 5. 22.(금) 9시 ~ 6. 22.(월) 18시"
        #          "2026.05.22 ~ 2026.06.22"
        #          "2026년 5월 22일 ~ 6월 22일"
        patterns = [
            # 4자리 연도 포함 양쪽: 2026.5.22 ~ 2026.6.22
            r"(\d{4})\D{1,3}(\d{1,2})\D{1,3}(\d{1,2})[^\d~]{0,15}[~～\-]\D{0,15}(\d{4})\D{1,3}(\d{1,2})\D{1,3}(\d{1,2})",
            # 앞만 4자리: 2026. 5. 22 ~ 6. 22
            r"(\d{4})\D{1,3}(\d{1,2})\D{1,3}(\d{1,2})[^\d~]{0,15}[~～\-]\D{0,10}(\d{1,2})\D{1,3}(\d{1,2})",
        ]
        for pat in patterns:
            m = re.search(pat, text)
            if not m:
                continue
            try:
                g = m.groups()
                if len(g) == 6:
                    s = date(int(g[0]), int(g[1]), int(g[2]))
                    e = date(int(g[3]), int(g[4]), int(g[5]))
                else:
                    year = int(g[0])
                    s = date(year, int(g[1]), int(g[2]))
                    e = date(year, int(g[3]), int(g[4]))
                # 합리적 날짜 범위만 허용
                if 2020 <= s.year <= 2030 and 2020 <= e.year <= 2030:
                    return s, e
            except ValueError:
                continue
        return None, None

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
            r"(?:장학금|지원금|장학혜택)[^\n]{0,10}[:：]\s*([^\n]{5,60})",
            text
        )
        if m:
            return m.group(1).strip()
        m2 = re.search(r"(\d[\d,]*\s*(?:만원|원|천원)(?:\s*[~\/]\s*\d[\d,]*\s*(?:만원|원))?)", text)
        if m2:
            return m2.group(1)
        return ""

    def _extract_docs_section(self, text: str) -> str:
        m = re.search(
            r"(?:제출\s*서류|구비\s*서류|제출물)[^\n]*\n((?:.+\n){1,15})",
            text
        )
        return m.group(1) if m else ""
