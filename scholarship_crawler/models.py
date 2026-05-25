from __future__ import annotations
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


class Scholarship(BaseModel):
    # 식별
    id: str
    source: str                          # kosaf | dreamspon | yonsei
    source_url: str

    # 기본 정보
    name: str
    organization: str
    description: str = ""

    # 금액
    amount_text: str = ""               # 원문 텍스트 (예: "연 450만원 이내")
    amount_min: Optional[int] = None    # 원 단위 (파싱 가능한 경우)
    amount_max: Optional[int] = None

    # ── 필터링 핵심 필드 ──────────────────────────────────────────────
    # 학업 조건
    gpa_min: Optional[float] = None         # 최소 성적 (4.5 만점 or 100점 만점)
    gpa_scale: Optional[float] = None       # 4.5 or 100
    enrollment_required: bool = True        # 재학 중이어야 신청 가능 여부

    # 경제적 조건
    income_bracket_max: Optional[int] = None  # 소득 분위 상한 (1~10)

    # 신분/자격 조건
    target_years: list[int] = Field(default_factory=list)        # [1,2,3,4] 빈 = 전체
    target_majors: list[str] = Field(default_factory=list)       # 전공/단과대, 빈 = 전체
    target_universities: list[str] = Field(default_factory=list) # 빈 = 전체
    region_requirement: list[str] = Field(default_factory=list)  # 빈 = 전국, 예: ["이천시"]
    nationality: str = "any"                # "any" | "korean" | "foreigner"

    # 특수 자격 태그
    # 빈 = 누구나, 값이 있으면 해당 조건 보유자만
    # 예: ["한부모", "다자녀", "장애", "농어촌", "보호종료", "이공계", "사범계"]
    special_tags: list[str] = Field(default_factory=list)
    no_duplicate_allowed: Optional[bool] = None  # True = 타 장학금 수혜 중이면 불가

    # 자격 및 서류
    eligibility_text: str = ""          # 원문 자격 조건
    required_docs: list[str] = Field(default_factory=list)

    # 신청 기간
    apply_start: Optional[date] = None
    apply_end: Optional[date] = None
    is_active: bool = True

    # 첨부파일
    attachment_urls: list[str] = Field(default_factory=list)  # PDF/HWP 링크
    attachment_text: str = ""  # PDF에서 추출한 텍스트

    # 온라인 신청
    apply_url: str = ""  # 공지 내 별도 신청 링크 (있을 경우)

    # AI 요약
    ai_summary: str = ""  # claude-haiku 2~3문장 요약

    # 메타
    crawled_at: datetime = Field(default_factory=datetime.now)
    extra: dict = Field(default_factory=dict)  # 사이트별 추가 필드

    def matches(
        self,
        gpa: Optional[float] = None,
        income_bracket: Optional[int] = None,
        year: Optional[int] = None,
        major: Optional[str] = None,
        university: Optional[str] = None,
        regions: Optional[list[str]] = None,
        nationality: Optional[str] = None,       # "korean" | "foreigner"
        enrolled: Optional[bool] = None,          # 현재 재학 중인지
        user_tags: Optional[list[str]] = None,    # 사용자가 해당하는 특수 태그 목록
        has_other_scholarship: Optional[bool] = None,  # 현재 다른 장학금 수혜 중인지
    ) -> bool:
        """사용자 조건으로 필터링."""
        # 성적
        if gpa is not None and self.gpa_min is not None:
            scale = self.gpa_scale or 4.5
            user_gpa = gpa / 4.5 * 100.0 if scale > 10 else gpa
            if user_gpa < self.gpa_min:
                return False

        # 소득분위
        if income_bracket is not None and self.income_bracket_max is not None:
            if income_bracket > self.income_bracket_max:
                return False

        # 학년
        if year is not None and self.target_years:
            if year not in self.target_years:
                return False

        # 전공
        if major is not None and self.target_majors:
            if not any(major in m or m in major for m in self.target_majors):
                return False

        # 대학교
        if university is not None and self.target_universities:
            if not any(university in u or u in university for u in self.target_universities):
                return False

        # 지역 조건 — 사용자 지역(거주/출신) 중 하나라도 장학금 요구 지역과 겹치면 통과
        if regions and self.region_requirement:
            if not any(
                any(ur in r or r in ur for r in self.region_requirement)
                for ur in regions
            ):
                return False

        # 국적
        if nationality is not None and self.nationality != "any":
            if self.nationality != nationality:
                return False

        # 재학 상태
        if enrolled is not None and self.enrollment_required:
            if not enrolled:
                return False

        # 특수 자격 태그
        # user_tags=None → 필터 생략 (프론트에서 태그 미선택)
        # user_tags=[]   → 해당하는 특수조건 없음 → 태그 요구 장학금 탈락
        if self.special_tags and user_tags is not None:
            if not set(user_tags).intersection(self.special_tags):
                return False

        # 중복 수혜 제한
        if has_other_scholarship and self.no_duplicate_allowed:
            return False

        return True
