from abc import ABC, abstractmethod
from typing import Optional
import asyncio
import re
import tempfile
import os
from urllib.parse import urljoin
from models import Scholarship


class BaseCrawler(ABC):
    source: str = ""

    @abstractmethod
    async def crawl(self) -> list[Scholarship]:
        """사이트를 크롤링하고 장학금 목록을 반환."""
        ...

    # ── 공통 파싱 헬퍼 ────────────────────────────────────────────────

    @staticmethod
    def parse_gpa(text: str) -> tuple[Optional[float], Optional[float]]:
        """
        '3.0 이상 (4.5 만점)'  → (3.0, 4.5)
        '백분위 80점 이상'      → (80.0, 100)
        '12학점 이상 이수'      → (None, None)  ← 학점수 조건은 GPA 아님
        'B학점 이상'           → (None, None)
        """
        # 학점 이수 조건(credit hours)은 GPA가 아니므로 제외
        cleaned = re.sub(r"\d+학점\s*이상\s*이수", "", text)
        cleaned = cleaned.replace(",", ".")

        # 4.5 만점 / 100점 만점 기준
        scale_match = re.search(r"(\d+\.?\d*)\s*만점", cleaned)
        scale = float(scale_match.group(1)) if scale_match else None

        # '백분위 N점 이상' → 100점 만점으로 간주
        percentile = re.search(r"백분위\s*(\d+\.?\d*)\s*점?\s*이상", cleaned)
        if percentile:
            return float(percentile.group(1)), 100.0

        # '성적 N.N 이상' 또는 'N.N점 이상 (4.5 만점)'
        gpa_match = re.search(
            r"(?:성적|평점|GPA|gpa)?\s*(\d+\.\d+)\s*(?:점|\/\s*\d)?\s*이상",
            cleaned,
        )
        if gpa_match:
            val = float(gpa_match.group(1))
            # 소수점 있는 값만 GPA로 인정 (12 같은 정수는 학점수일 가능성)
            if val <= 4.5 or scale:
                return val, scale or 4.5
            if val <= 100:
                return val, scale or 100.0

        return None, None

    @staticmethod
    def parse_income_bracket(text: str) -> Optional[int]:
        """
        '소득 3분위 이하' → 3
        '기초·차상위 계층' → 2  (기초=1분위, 차상위=2분위로 근사)
        """
        if "기초" in text and "차상위" in text:
            return 2
        if "기초" in text:
            return 1
        m = re.search(r"(\d+)\s*(?:분위|구간)", text)
        return int(m.group(1)) if m else None

    @staticmethod
    def parse_years(text: str) -> list[int]:
        """
        '1~3학년' → [1, 2, 3]
        '2학년 이상' → [2, 3, 4]
        '전 학년' → []  (빈 리스트 = 제한 없음)
        """
        if any(k in text for k in ["전 학년", "전학년", "학년 무관", "제한없음"]):
            return []

        range_m = re.search(r"(\d+)[~\-~](\d+)\s*학년", text)
        if range_m:
            return list(range(int(range_m.group(1)), int(range_m.group(2)) + 1))

        above_m = re.search(r"(\d+)\s*학년\s*이상", text)
        if above_m:
            return list(range(int(above_m.group(1)), 5))

        singles = re.findall(r"(\d+)\s*학년", text)
        if singles:
            return sorted(set(int(y) for y in singles if 1 <= int(y) <= 4))

        return []

    @staticmethod
    def parse_amount(text: str) -> tuple[Optional[int], Optional[int]]:
        """
        '연 450만원 이내' → (None, 4_500_000)
        '월 30만~50만원' → (300_000, 500_000)
        '등록금 전액' → (None, None)
        """
        text = text.replace(",", "").replace(" ", "")
        nums = re.findall(r"(\d+(?:\.\d+)?)(만|억)?원", text)
        if not nums:
            return None, None

        def to_won(n: str, unit: str) -> int:
            v = float(n)
            if unit == "억":
                return int(v * 1_0000_0000)
            if unit == "만":
                return int(v * 10000)
            return int(v)

        values = [to_won(n, u) for n, u in nums]
        if len(values) == 1:
            return None, values[0]
        return min(values), max(values)

    # ── 공고 유효성 필터 ──────────────────────────────────────────────

    # 이 키워드가 제목에 있으면 무조건 제외
    _STRONG_EXCLUDE = [
        "업무처리기준", "근로기관", "담당자", "만족도", "설문", "보도자료",
        "행정예고", "우수사례", "수기 공모", "취업약정", "홈페이지 오류",
        "시스템 점검", "시스템점검", "인터뷰", "언론",
        # 장학금 공고가 아닌 콘텐츠
        "꿀팁", "MOU",
    ]
    # 이 키워드가 제목에 있고, 아래 허용 키워드가 없으면 제외
    _SOFT_EXCLUDE = [
        "선발 결과", "선발결과", "결과 발표", "결과발표", "결과 안내",
        "운영 안내", "운영안내", "작성 안내", "작성요령", "작성방법",
        "처리 기준", "기준 안내", "지급 결과", "지급결과",
        # 장학금 신청과 무관한 행정/운영 공지
        "멘토링", "서포터즈",
        "포기", "반환", "변경 안내",
    ]
    # 이 키워드 중 하나라도 있으면 soft_exclude 무력화 (신청 공고로 인정)
    _ALLOW_KEYWORDS = ["신청", "모집", "공고", "선발 안내", "지원 안내"]

    @classmethod
    def is_scholarship_notice(cls, title: str, content: str = "") -> bool:
        """장학금 신청 공고인지 판별. 운영/결과 안내 등은 False 반환."""
        for kw in cls._STRONG_EXCLUDE:
            if kw in title:
                return False
        has_allow = any(kw in title for kw in cls._ALLOW_KEYWORDS)
        for kw in cls._SOFT_EXCLUDE:
            if kw in title and not has_allow:
                return False
        return True

    @staticmethod
    def extract_apply_url(text: str) -> str:
        """본문에서 별도 온라인 신청 URL 추출."""
        patterns = [
            r"신청\s*(?:URL|링크|사이트|페이지)\s*[:\s]\s*(https?://\S+)",
            r"온라인\s*신청\s*[:\s]\s*(https?://\S+)",
            r"접수\s*(?:URL|링크)\s*[:\s]\s*(https?://\S+)",
        ]
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                url = m.group(1).rstrip(".,)")
                if len(url) > 10:
                    return url
        return ""

    # ── AI 요약 ──────────────────────────────────────────────────────

    @staticmethod
    async def ai_summarize(name: str, content: str) -> str:
        """claude-haiku로 장학금 공지를 2~3문장 요약. API 키 없으면 빈 문자열."""
        def _sync() -> str:
            import os
            try:
                from dotenv import load_dotenv
                load_dotenv(override=True)
            except ImportError:
                pass
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if not api_key:
                return ""
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=api_key)
                msg = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=250,
                    messages=[{
                        "role": "user",
                        "content": (
                            "다음 장학금 공지를 2~3문장으로 간결하게 요약해줘. "
                            "핵심 정보(지원 대상, 지원 금액, 신청 기간, 주요 조건)를 포함하고, "
                            "불필요한 인사말·안내 문구 없이 핵심만 작성해줘.\n\n"
                            f"장학금명: {name}\n---\n{content[:2500]}"
                        ),
                    }],
                )
                return msg.content[0].text.strip()
            except Exception:
                return ""
        return await asyncio.to_thread(_sync)

    @staticmethod
    async def ai_extract_from_images(image_urls: list[str], scholarship_name: str = "", user_agent: str = "", referer: str = "") -> dict:
        """이미지에서 Claude Vision API로 장학금 정보 추출. 실패 시 빈 dict."""
        def _sync() -> dict:
            import os, base64, json
            try:
                from dotenv import load_dotenv
                load_dotenv(override=True)
            except ImportError:
                pass
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if not api_key or not image_urls:
                return {}
            try:
                import anthropic
                import requests as req
                client = anthropic.Anthropic(api_key=api_key)
                headers = {
                    "User-Agent": user_agent or "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
                }
                if referer:
                    headers["Referer"] = referer
                content = []
                for url in image_urls[:3]:
                    try:
                        resp = req.get(url, headers=headers, timeout=15)
                        if resp.status_code != 200:
                            print(f"[vision] 이미지 다운로드 실패: HTTP {resp.status_code} → {url}")
                            continue
                        ct = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
                        if not ct.startswith("image/"):
                            print(f"[vision] 이미지 아님 (content-type={ct}): {url}")
                            continue
                        b64 = base64.standard_b64encode(resp.content).decode()
                        content.append({
                            "type": "image",
                            "source": {"type": "base64", "media_type": ct, "data": b64},
                        })
                        print(f"[vision] 이미지 로드 성공: {url}")
                    except Exception as e:
                        print(f"[vision] 이미지 요청 오류: {e} ({url})")
                        continue
                if not content:
                    print("[vision] 유효한 이미지 없음 → Vision 스킵")
                    return {}
                content.append({
                    "type": "text",
                    "text": (
                        f"장학금명: {scholarship_name}\n\n"
                        "위 이미지는 장학금 공고 포스터입니다. 이미지에서 다음 정보를 추출해 JSON으로만 응답하세요.\n"
                        "{\n"
                        '  "apply_start": "YYYY-MM-DD 또는 null",\n'
                        '  "apply_end": "YYYY-MM-DD 또는 null",\n'
                        '  "amount_text": "지원 금액 (예: 500만원, 등록금 전액) 또는 null",\n'
                        '  "eligibility": "지원 자격/대상 요약 또는 null",\n'
                        '  "summary": "2문장 이내 핵심 요약"\n'
                        "}\n"
                        "확인 불가 항목은 null. JSON 외 다른 텍스트는 포함하지 마세요."
                    ),
                })
                msg = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=500,
                    messages=[{"role": "user", "content": content}],
                )
                text = msg.content[0].text.strip()
                print(f"[vision] Claude 응답: {text[:300]}")
                json_match = re.search(r"\{.*\}", text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
            except Exception as e:
                print(f"[vision] Vision API 오류: {e}")
            return {}

        return await asyncio.to_thread(_sync)

    @staticmethod
    def extract_inline_image_urls(soup, base_url: str = "", container_selector: str = ".board-view") -> list[str]:
        """게시판 본문 인라인 img 태그에서 이미지 URL 추출."""
        container = soup.select_one(container_selector) or soup
        urls: list[str] = []
        seen: set[str] = set()
        for img in container.find_all("img", src=True):
            src = img["src"]
            if not src or src.startswith("data:"):
                continue
            full = src if src.startswith("http") else urljoin(base_url, src)
            if full not in seen:
                seen.add(full)
                urls.append(full)
        return urls

    @staticmethod
    def extract_attachment_urls(soup, base_url: str = "") -> list[str]:
        """HTML에서 PDF/HWP/DOC 첨부파일 링크 추출."""
        EXTS = (".pdf", ".hwp", ".hwpx", ".doc", ".docx", ".xls", ".xlsx")
        urls = []
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            lower = href.lower()
            if not any(lower.endswith(ext) or ext in lower for ext in EXTS):
                # download= 속성이나 파일명 힌트도 확인
                download = a.get("download", "")
                if not any(download.lower().endswith(ext) for ext in EXTS):
                    continue
            full = href if href.startswith("http") else urljoin(base_url, href)
            if full not in seen:
                seen.add(full)
                urls.append(full)
        return urls

    @staticmethod
    async def extract_pdf_text(url: str, user_agent: str = "") -> str:
        """PDF URL에서 텍스트 추출 (최대 10페이지). 실패 시 빈 문자열 반환."""
        def _sync() -> str:
            try:
                import pdfplumber, requests
                headers = {"User-Agent": user_agent or "Mozilla/5.0"}
                resp = requests.get(url, headers=headers, timeout=30)
                if resp.status_code != 200:
                    return ""
                ct = resp.headers.get("content-type", "")
                if "pdf" not in ct.lower() and not url.lower().endswith(".pdf"):
                    return ""
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                    f.write(resp.content)
                    tmp = f.name
                try:
                    with pdfplumber.open(tmp) as pdf:
                        pages = pdf.pages[:10]
                        return "\n".join(p.extract_text() or "" for p in pages)
                finally:
                    os.unlink(tmp)
            except Exception:
                return ""

        return await asyncio.to_thread(_sync)

    @staticmethod
    def parse_docs(text: str) -> list[str]:
        """줄바꿈 또는 '·', '•', '-' 구분자로 서류 목록 파싱."""
        lines = re.split(r"[\n·•\-]|,(?!\s*\d)", text)
        docs = [l.strip() for l in lines if l.strip()]
        return [d for d in docs if len(d) > 1]

    # ── 신규 필터 파싱 헬퍼 ──────────────────────────────────────────────

    @staticmethod
    def parse_region(text: str) -> list[str]:
        """
        지역 거주·주민등록 조건 추출.
        '이천시 거주자' → ['이천시']
        '전라남도 출신 고교 졸업자' → ['전라남도']
        조건 없으면 → []
        """
        triggers = r"(?:거주|주민등록|출신|소재|재학|해당\s*지역)"
        patterns = [
            rf"([가-힣]{{2,6}}(?:특별시|광역시|특별자치시|특별자치도))\s*{triggers}",
            rf"([가-힣]{{2,4}}(?:도|특별자치도))\s*{triggers}",
            rf"([가-힣]{{2,6}}(?:시|군|구))\s*(?:에\s*)?{triggers}",
        ]
        regions: list[str] = []
        for pat in patterns:
            for m in re.finditer(pat, text):
                r = m.group(1)
                if r not in regions:
                    regions.append(r)
        return regions

    @staticmethod
    def parse_nationality(text: str) -> str:
        """
        '외국인 유학생 전용' → 'foreigner'
        '내국인에 한함' → 'korean'
        그 외 → 'any'
        """
        if any(k in text for k in ["외국인 유학생", "외국인유학생", "외국 국적", "외국인 학생"]):
            return "foreigner"
        if any(k in text for k in ["내국인", "대한민국 국적", "한국 국적", "한국인"]):
            return "korean"
        return "any"

    @staticmethod
    def parse_enrollment_required(text: str) -> bool:
        """
        휴학생도 지원 가능하다고 명시된 경우 False, 그 외 True(기본값).
        """
        if any(k in text for k in ["휴학생 포함", "휴학중인 자 포함", "휴학생도 지원 가능",
                                    "휴학 중에도 신청", "휴학생도 신청"]):
            return False
        return True

    _SPECIAL_TAG_PATTERNS: list[tuple[str, list[str]]] = [
        ("한부모",    ["한부모", "한 부모 가정"]),
        ("다자녀",    ["다자녀", "자녀 3명 이상", "3자녀 이상"]),
        ("조손",      ["조손 가정", "조손가정"]),
        ("장애",      ["장애인", "장애 등급", "장애를 가진", "장애자녀"]),
        ("농어촌",    ["농어촌", "농촌 출신", "어촌 출신"]),
        ("보호종료",  ["보호종료아동", "보호종료", "자립준비청년"]),
        ("이공계",    ["이공계", "이공 계열", "공학계열", "자연과학계열", "STEM"]),
        ("사범계",    ["사범대", "사범대학", "교육대학", "교육계열"]),
        ("국가유공자",["국가유공자", "보훈 대상", "보훈가족"]),
        ("새터민",    ["새터민", "탈북", "북한이탈주민"]),
        ("독립유공자",["독립유공자"]),
    ]

    @classmethod
    def parse_special_tags(cls, text: str) -> list[str]:
        """
        특수 자격 조건 태그 추출.
        '한부모 가정 학생' → ['한부모']
        '이공계열 재학생 대상' → ['이공계']
        """
        return [tag for tag, keywords in cls._SPECIAL_TAG_PATTERNS
                if any(kw in text for kw in keywords)]

    @staticmethod
    def parse_no_duplicate(text: str) -> Optional[bool]:
        """
        중복 수혜 제한 여부.
        '타 장학금 수혜자 제외' → True
        '중복 수혜 가능' → False
        명시 없음 → None
        """
        if any(k in text for k in ["중복 수혜 불가", "중복수혜 불가", "중복수혜불가",
                                    "타 장학금 수혜자 제외", "중복 지원 불가",
                                    "타 장학금과 중복 불가", "다른 장학금을 받는 자 제외"]):
            return True
        if any(k in text for k in ["중복 수혜 가능", "중복수혜 가능", "타 장학금과 중복 수혜 가능"]):
            return False
        return None
