"""FastAPI 백엔드 — 장학금 검색 API"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import anthropic
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from typing import Optional
from pydantic import BaseModel

from database import ScholarshipDB

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="장학금 검색 API", version="0.2.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.path.join(os.path.dirname(__file__), "scholarships.db")
db = ScholarshipDB(DB_PATH)


class ScholarshipOut(BaseModel):
    id: str
    source: str
    source_url: str
    name: str
    organization: str
    description: str
    amount_text: str
    # 학업 조건
    gpa_min: Optional[float]
    enrollment_required: bool
    # 경제적 조건
    income_bracket_max: Optional[int]
    # 신분/자격 조건
    target_years: list[int]
    target_majors: list[str]
    target_universities: list[str]
    region_requirement: list[str]
    nationality: str
    # 특수 자격 태그
    special_tags: list[str]
    no_duplicate_allowed: Optional[bool]
    # 기타
    eligibility_text: str
    required_docs: list[str]
    apply_start: Optional[str]
    apply_end: Optional[str]
    is_active: bool
    attachment_urls: list[str]
    apply_url: str
    ai_summary: str


@app.get("/api/scholarships", response_model=dict)
def search(
    # 학업 조건
    gpa: Optional[float] = Query(None, description="성적 (4.5 만점 기준)"),
    year: Optional[int] = Query(None, description="학년 (1~4)"),
    major: Optional[str] = Query(None, description="전공 키워드"),
    university: Optional[str] = Query(None, description="재학 대학교 이름"),
    enrolled: Optional[bool] = Query(None, description="현재 재학 중인지 (false=휴학)"),
    # 경제적 조건
    income: Optional[int] = Query(None, description="학자금 지원 구간 (1~10)"),
    # 신분/자격 조건
    residence: Optional[str] = Query(None, description="현재 거주 지역 (예: 아산시)"),
    hometown: Optional[str] = Query(None, description="출신 고교 지역 (예: 거창군)"),
    nationality: Optional[str] = Query(None, description="국적: korean | foreigner"),
    # 특수 자격 태그 (쉼표 구분, 예: 한부모,이공계)
    tags: Optional[str] = Query(None, description="해당하는 특수조건 (쉼표 구분): 한부모,다자녀,장애,농어촌,보호종료,이공계,사범계,국가유공자,새터민"),
    has_other_scholarship: Optional[bool] = Query(None, description="현재 다른 장학금 수혜 중인지"),
    # 검색/필터
    source: Optional[str] = Query(None, description="출처: kosaf | dreamspon | yonsei"),
    active_only: bool = Query(True, description="모집 중인 것만"),
):
    user_regions = [r for r in [residence, hometown] if r] or None
    user_tags = [t.strip() for t in tags.split(",")] if tags else None

    results = db.query(
        gpa=gpa,
        income_bracket=income,
        year=year,
        major=major,
        university=university,
        regions=user_regions,
        nationality=nationality,
        enrolled=enrolled,
        user_tags=user_tags,
        has_other_scholarship=has_other_scholarship,
        source=source,
        active_only=active_only,
    )

    out = [_to_out(r) for r in results]
    return {"total": len(out), "results": out}


@app.get("/api/scholarships/{scholarship_id}")
def get_one(scholarship_id: str):
    from sqlalchemy.orm import Session
    from database import ScholarshipRow, _from_row
    with Session(db.engine) as session:
        row = session.get(ScholarshipRow, scholarship_id)
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="장학금을 찾을 수 없습니다.")
    return _to_out(_from_row(row))


class AiMatchRequest(BaseModel):
    user_profile_text: str
    gpa: Optional[float] = None
    year: Optional[int] = None
    income: Optional[int] = None
    major: Optional[str] = None
    university: Optional[str] = None
    residence: Optional[str] = None
    hometown: Optional[str] = None
    nationality: Optional[str] = None
    enrolled: Optional[bool] = None
    tags: Optional[str] = None
    has_other_scholarship: Optional[bool] = None


@app.post("/api/scholarships/ai-match")
@limiter.limit("2/day")
def ai_match(request: Request, req: AiMatchRequest):
    user_tags = [t.strip() for t in req.tags.split(",")] if req.tags else None
    user_regions = [r for r in [req.residence, req.hometown] if r] or None

    candidates = db.query(
        gpa=req.gpa, income_bracket=req.income, year=req.year,
        major=req.major, university=req.university, regions=user_regions,
        nationality=req.nationality, enrolled=req.enrolled,
        user_tags=user_tags, has_other_scholarship=req.has_other_scholarship,
        active_only=True,
    )
    if not candidates:
        return {"total": 0, "results": []}

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)
    all_results = []
    for i in range(0, len(candidates), 5):
        batch = candidates[i:i + 5]
        all_results.extend(_llm_match_batch(client, req.user_profile_text, batch))

    score_order = {"high": 0, "medium": 1, "low": 2}
    all_results.sort(key=lambda x: score_order.get(x["match_score"], 3))
    return {"total": len(all_results), "results": all_results}


def _llm_match_batch(client: anthropic.Anthropic, user_profile: str, scholarships: list) -> list:
    entries = []
    for i, s in enumerate(scholarships, 1):
        body = s.ai_summary or ""
        if s.eligibility_text:
            body += "\n자격: " + s.eligibility_text[:600]
        entries.append(f"[{i}] {s.name} ({s.organization})\n{body}")

    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1024,
        system="""장학금 자격 조건과 사용자 프로필을 비교합니다.
- high: 자격 조건 충족, 또는 조건이 불명확하여 누구나 가능
- medium: 일부 불확실한 조건 있음
- low: 지역·특수 신분 등 명시적 조건 불일치

소득 관련 주의: 사용자 프로필의 '학자금 지원 N구간'과 장학금 조건의 'N구간 이하' 또는 'N분위 이하'는 동일한 기준입니다. 사용자 구간이 조건 상한 이하이면 충족입니다.""",
        messages=[{"role": "user", "content": f"사용자: {user_profile}\n\n" + "\n\n".join(entries)}],
        tools=[{
            "name": "evaluate_matches",
            "description": "각 장학금의 매칭도 평가",
            "input_schema": {
                "type": "object",
                "properties": {
                    "evaluations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "index": {"type": "integer"},
                                "match_score": {"type": "string", "enum": ["high", "medium", "low"]},
                                "match_reason": {"type": "string", "description": "1문장 이내 한국어 이유"},
                            },
                            "required": ["index", "match_score", "match_reason"],
                        }
                    }
                },
                "required": ["evaluations"],
            }
        }],
        tool_choice={"type": "tool", "name": "evaluate_matches"},
    )

    results = []
    for ev in response.content[0].input["evaluations"]:
        idx = ev["index"] - 1
        if 0 <= idx < len(scholarships):
            results.append({
                "scholarship": _to_out(scholarships[idx]),
                "match_score": ev["match_score"],
                "match_reason": ev["match_reason"],
            })
    return results


@app.get("/api/stats")
def stats():
    all_results = db.query(active_only=False)
    by_source: dict[str, int] = {}
    tag_count: dict[str, int] = {}
    for r in all_results:
        by_source[r.source] = by_source.get(r.source, 0) + 1
        for tag in r.special_tags:
            tag_count[tag] = tag_count.get(tag, 0) + 1
    return {
        "total": len(all_results),
        "by_source": by_source,
        "tag_distribution": tag_count,
    }


def _to_out(r) -> dict:
    return ScholarshipOut(
        id=r.id,
        source=r.source,
        source_url=r.source_url,
        name=r.name,
        organization=r.organization,
        description=r.description,
        amount_text=r.amount_text,
        gpa_min=r.gpa_min,
        enrollment_required=r.enrollment_required,
        income_bracket_max=r.income_bracket_max,
        target_years=r.target_years,
        target_majors=r.target_majors,
        target_universities=r.target_universities,
        region_requirement=r.region_requirement,
        nationality=r.nationality,
        special_tags=r.special_tags,
        no_duplicate_allowed=r.no_duplicate_allowed,
        eligibility_text=r.eligibility_text,
        required_docs=r.required_docs,
        apply_start=str(r.apply_start) if r.apply_start else None,
        apply_end=str(r.apply_end) if r.apply_end else None,
        is_active=r.is_active,
        attachment_urls=r.attachment_urls,
        apply_url=r.apply_url,
        ai_summary=r.ai_summary,
    ).model_dump()
