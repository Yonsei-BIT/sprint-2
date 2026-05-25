"""
드림스폰 (dreamspon.com) 크롤러
URL: https://www.dreamspon.com/scholarship/list.html
구조: 목록 테이블(장학명/기관명/모집현황) → 상세 (로그인 필요 시 목록 정보만 보존)
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

BASE = "https://www.dreamspon.com"
LIST_URL = f"{BASE}/scholarship/list.html"
TODAY = date.today()


class DreamsponCrawler(BaseCrawler):
    source = "dreamspon"

    def __init__(self, max_pages: int = 5):
        self.max_pages = max_pages

    async def crawl(self) -> list[Scholarship]:
        results: list[Scholarship] = []

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            ctx = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                           "AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800},
            )
            page = await ctx.new_page()

            items = await self._collect_list(page)
            print(f"[dreamspon] 목록 수집: {len(items)}건")

            for item in items:
                # 마감 항목 즉시 제외
                status = item.get("status", "")
                if "마감" in status or "종료" in status:
                    continue

                try:
                    s = await self._parse_detail(page, item)
                    if s and s.is_active:
                        results.append(s)
                    await asyncio.sleep(0.8)
                except Exception as e:
                    print(f"[dreamspon] 상세 파싱 오류 ({item['name']}): {e}")
                    fallback = self._make_from_list(item)
                    if fallback and fallback.is_active:
                        results.append(fallback)

            await browser.close()

        print(f"[dreamspon] 완료: 모집중 {len(results)}건")
        return results

    async def _collect_list(self, page: Page) -> list[dict]:
        items: list[dict] = []
        for pg in range(1, self.max_pages + 1):
            url = f"{LIST_URL}?page={pg}"
            try:
                await page.goto(url, timeout=15000, wait_until="networkidle")
                await page.wait_for_timeout(2000)

                html = await page.content()
                soup = BeautifulSoup(html, "lxml")

                found = 0
                for row in soup.select("table tr"):
                    cells = row.select("td")
                    if len(cells) < 3:
                        continue
                    link = cells[0].select_one("a[href*='/scholarship/view']")
                    if not link:
                        continue

                    raw_name = link.get_text(strip=True)
                    name = re.sub(r"#\S+", "", raw_name).strip()
                    org = cells[1].get_text(strip=True)
                    status = cells[2].get_text(strip=True)
                    href = link.get("href", "")
                    full_url = BASE + href if href.startswith("/") else href
                    tags = re.findall(r"#(\S+)", raw_name)

                    if not self.is_scholarship_notice(name):
                        continue
                    items.append({
                        "name": name,
                        "organization": org,
                        "status": status,
                        "url": full_url,
                        "tags": tags,
                    })
                    found += 1

                print(f"[dreamspon] page {pg}: {found}건")
                if found == 0:
                    break
                await asyncio.sleep(0.8)
            except Exception as e:
                print(f"[dreamspon] page {pg} 오류: {e}")
                break

        return items

    async def _parse_detail(self, page: Page, item: dict) -> Optional[Scholarship]:
        await page.goto(item["url"], timeout=20000, wait_until="networkidle")
        await page.wait_for_timeout(1500)

        html = await page.content()
        soup = BeautifulSoup(html, "lxml")
        body_text = soup.get_text(separator="\n")

        # 상세 내용 마스킹 여부 확인 (로그인 필요 페이지 감지)
        star_count = body_text.count("*")
        has_login_form = bool(soup.select("input[type='password'], input[name*='password'], input[name*='passwd'], input[id*='password']"))
        info_keywords = ["신청자격", "지원자격", "대상", "신청기간", "접수기간", "지원금액", "장학금액", "모집요강"]
        has_info_text = any(kw in body_text for kw in info_keywords)
        is_masked = star_count > 30 or has_login_form or not has_info_text
        print(f"[dreamspon] '{item['name']}' 마스킹={is_masked} (별표={star_count}, 로그인폼={has_login_form}, 정보텍스트={has_info_text})")

        eligibility, docs, amount_text = "", [], ""
        apply_start, apply_end = None, None
        ai_summary = ""

        if not is_masked:
            for row in soup.select("table tr, dl"):
                cells = row.select("th,td,dt,dd")
                if len(cells) >= 2:
                    key = cells[0].get_text(strip=True)
                    val = cells[1].get_text(separator="\n", strip=True)
                    if "자격" in key or "대상" in key:
                        eligibility = val
                    elif "서류" in key:
                        docs = self.parse_docs(val)
                    elif "금액" in key or "장학금" in key:
                        amount_text = val[:100]
                    elif "기간" in key or "신청" in key:
                        apply_start, apply_end = self._extract_period(val)
        else:
            # 마스킹 상태: 공개된 포스터 이미지에서 Vision API로 정보 추출
            _SKIP = ("icon", "logo", "btn", "arrow", "bullet", "banner_sm", "bg_", "common", "layout", "naver", "kakao")
            _PREFER = ("upload", "poster", "thumb", "banner", "scholarship", "notice", "board", "file")
            preferred, others = [], []
            for img in soup.select("img[src]"):
                u = img.get("src", "")
                if not u:
                    continue
                full = BASE + u if u.startswith("/") else u
                if any(s in full.lower() for s in _SKIP):
                    continue
                if any(p in full.lower() for p in _PREFER):
                    preferred.append(full)
                else:
                    others.append(full)
            img_urls = preferred + others
            print(f"[dreamspon] 마스킹 이미지 후보: preferred={len(preferred)}, others={len(others)}")
            for u in img_urls[:5]:
                print(f"  → {u}")

            if img_urls:
                print(f"[dreamspon] Vision 추출 시도 ({len(img_urls)}장)")
                extracted = await self.ai_extract_from_images(img_urls, item["name"], referer=item["url"])
                if extracted:
                    amount_text = extracted.get("amount_text") or ""
                    eligibility = extracted.get("eligibility") or ""
                    ai_summary = extracted.get("summary") or ""
                    for key, attr in [("apply_start", "apply_start"), ("apply_end", "apply_end")]:
                        val = extracted.get(key)
                        if val and val != "null":
                            try:
                                from datetime import datetime
                                d = datetime.strptime(val, "%Y-%m-%d").date()
                                if key == "apply_start":
                                    apply_start = d
                                else:
                                    apply_end = d
                            except ValueError:
                                pass

        # 상태에서 D-N 파싱으로 마감일 추정
        status = item["status"]
        if apply_end is None:
            days_left = re.search(r"D-(\d+)", status)
            if days_left:
                from datetime import timedelta
                apply_end = TODAY + timedelta(days=int(days_left.group(1)))

        is_active = "마감" not in status and "종료" not in status
        if apply_end and apply_end < TODAY:
            is_active = False

        parse_src = eligibility or body_text
        gpa_min, gpa_scale = self.parse_gpa(parse_src)
        income_max = self.parse_income_bracket(parse_src)
        years = self._tags_to_years(item["tags"])
        majors = self._tags_to_majors(item["tags"])

        region = self.parse_region(parse_src)
        nationality = self.parse_nationality(parse_src)
        enrollment_required = self.parse_enrollment_required(parse_src)
        special_tags = self.parse_special_tags(parse_src)
        no_duplicate = self.parse_no_duplicate(parse_src)

        if not ai_summary:
            ai_summary = await self.ai_summarize(item["name"], parse_src)

        uid = hashlib.md5(item["url"].encode()).hexdigest()[:12]
        return Scholarship(
            id=f"dreamspon_{uid}",
            source=self.source,
            source_url=item["url"],
            name=item["name"],
            organization=item["organization"],
            description=f"모집현황: {status}",
            amount_text=amount_text,
            gpa_min=gpa_min,
            gpa_scale=gpa_scale,
            enrollment_required=enrollment_required,
            income_bracket_max=income_max,
            target_years=years,
            target_majors=majors,
            region_requirement=region,
            nationality=nationality,
            special_tags=special_tags,
            no_duplicate_allowed=no_duplicate,
            eligibility_text=eligibility,
            required_docs=docs,
            apply_end=apply_end,
            is_active=is_active,
            ai_summary=ai_summary,
            extra={"status": status, "masked": is_masked, "vision_used": is_masked and bool(eligibility or amount_text)},
        )

    def _make_from_list(self, item: dict) -> Optional[Scholarship]:
        if not item.get("name"):
            return None
        status = item["status"]
        is_active = "마감" not in status and "종료" not in status

        days_left = re.search(r"D-(\d+)", status)
        apply_end = None
        if days_left:
            from datetime import timedelta
            apply_end = TODAY + timedelta(days=int(days_left.group(1)))

        uid = hashlib.md5(item["url"].encode()).hexdigest()[:12]
        return Scholarship(
            id=f"dreamspon_{uid}",
            source=self.source,
            source_url=item["url"],
            name=item["name"],
            organization=item["organization"],
            description=f"모집현황: {status}",
            apply_end=apply_end,
            is_active=is_active,
            extra={"status": status},
        )

    def _extract_period(self, text: str):
        m = re.search(
            r"(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})\s*[~\-]\s*"
            r"(?:(\d{4})[.\-])?(\d{1,2})[.\-](\d{1,2})",
            text
        )
        if not m:
            return None, None
        try:
            g = m.groups()
            s = date(int(g[0]), int(g[1]), int(g[2]))
            year = int(g[3]) if g[3] else int(g[0])
            e = date(year, int(g[4]), int(g[5]))
            return s, e
        except ValueError:
            return None, None

    def _tags_to_years(self, tags: list[str]) -> list[int]:
        years = []
        for tag in tags:
            m = re.search(r"(\d+)학년", tag)
            if m:
                y = int(m.group(1))
                if 1 <= y <= 4:
                    years.append(y)
        return years

    def _tags_to_majors(self, tags: list[str]) -> list[str]:
        keywords = ["이공계", "인문", "사회", "예체능", "의대", "약대", "법대"]
        return [t for t in tags if any(k in t for k in keywords)]
