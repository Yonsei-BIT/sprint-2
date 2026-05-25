import json
import re
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float, Integer,
    String, Text, create_engine, select, func, text, or_
)
from sqlalchemy.orm import DeclarativeBase, Session

from models import Scholarship


class Base(DeclarativeBase):
    pass


class ScholarshipRow(Base):
    __tablename__ = "scholarships"

    id = Column(String, primary_key=True)
    source = Column(String, nullable=False, index=True)
    source_url = Column(String)
    name = Column(String, nullable=False, index=True)
    organization = Column(String)
    description = Column(Text, default="")
    amount_text = Column(String, default="")
    amount_min = Column(Integer, nullable=True)
    amount_max = Column(Integer, nullable=True)

    gpa_min = Column(Float, nullable=True)
    gpa_scale = Column(Float, nullable=True)
    enrollment_required = Column(Boolean, default=True)
    income_bracket_max = Column(Integer, nullable=True)
    target_years = Column(String, default="[]")           # JSON
    target_majors = Column(String, default="[]")          # JSON
    target_universities = Column(String, default="[]")    # JSON
    region_requirement = Column(String, default="[]")     # JSON
    nationality = Column(String, default="any")
    special_tags = Column(String, default="[]")           # JSON
    no_duplicate_allowed = Column(Boolean, nullable=True)

    eligibility_text = Column(Text, default="")
    required_docs = Column(Text, default="[]")        # JSON

    apply_start = Column(Date, nullable=True)
    apply_end = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True)

    attachment_urls = Column(Text, default="[]")      # JSON
    attachment_text = Column(Text, default="")
    apply_url = Column(String, default="")
    ai_summary = Column(Text, default="")

    crawled_at = Column(DateTime, default=datetime.now)
    extra = Column(Text, default="{}")                # JSON


def _to_row(s: Scholarship) -> ScholarshipRow:
    return ScholarshipRow(
        id=s.id,
        source=s.source,
        source_url=s.source_url,
        name=s.name,
        organization=s.organization,
        description=s.description,
        amount_text=s.amount_text,
        amount_min=s.amount_min,
        amount_max=s.amount_max,
        gpa_min=s.gpa_min,
        gpa_scale=s.gpa_scale,
        enrollment_required=s.enrollment_required,
        income_bracket_max=s.income_bracket_max,
        target_years=json.dumps(s.target_years, ensure_ascii=False),
        target_majors=json.dumps(s.target_majors, ensure_ascii=False),
        target_universities=json.dumps(s.target_universities, ensure_ascii=False),
        region_requirement=json.dumps(s.region_requirement, ensure_ascii=False),
        nationality=s.nationality,
        special_tags=json.dumps(s.special_tags, ensure_ascii=False),
        no_duplicate_allowed=s.no_duplicate_allowed,
        eligibility_text=s.eligibility_text,
        required_docs=json.dumps(s.required_docs, ensure_ascii=False),
        apply_start=s.apply_start,
        apply_end=s.apply_end,
        is_active=s.is_active,
        attachment_urls=json.dumps(s.attachment_urls, ensure_ascii=False),
        attachment_text=s.attachment_text,
        apply_url=s.apply_url,
        ai_summary=s.ai_summary,
        crawled_at=s.crawled_at,
        extra=json.dumps(s.extra, ensure_ascii=False, default=str),
    )


def _from_row(r: ScholarshipRow) -> Scholarship:
    return Scholarship(
        id=r.id,
        source=r.source,
        source_url=r.source_url,
        name=r.name,
        organization=r.organization or "",
        description=r.description or "",
        amount_text=r.amount_text or "",
        amount_min=r.amount_min,
        amount_max=r.amount_max,
        gpa_min=r.gpa_min,
        gpa_scale=r.gpa_scale,
        enrollment_required=r.enrollment_required if r.enrollment_required is not None else True,
        income_bracket_max=r.income_bracket_max,
        target_years=json.loads(r.target_years or "[]"),
        target_majors=json.loads(r.target_majors or "[]"),
        target_universities=json.loads(r.target_universities or "[]"),
        region_requirement=json.loads(r.region_requirement or "[]"),
        nationality=r.nationality or "any",
        special_tags=json.loads(r.special_tags or "[]"),
        no_duplicate_allowed=r.no_duplicate_allowed,
        eligibility_text=r.eligibility_text or "",
        required_docs=json.loads(r.required_docs or "[]"),
        apply_start=r.apply_start,
        apply_end=r.apply_end,
        is_active=r.is_active,
        attachment_urls=json.loads(r.attachment_urls or "[]"),
        attachment_text=r.attachment_text or "",
        apply_url=r.apply_url or "",
        ai_summary=r.ai_summary or "",
        crawled_at=r.crawled_at or datetime.now(),
        extra=json.loads(r.extra or "{}"),
    )


class ScholarshipDB:
    def __init__(self, path: str = "scholarships.db"):
        self.engine = create_engine(f"sqlite:///{path}", echo=False)
        Base.metadata.create_all(self.engine)
        self._migrate()

    def _migrate(self):
        """기존 DB에 새 컬럼이 없을 때 추가."""
        new_cols = [
            ("attachment_urls", "TEXT DEFAULT '[]'"),
            ("attachment_text", "TEXT DEFAULT ''"),
            ("apply_url", "TEXT DEFAULT ''"),
            ("ai_summary", "TEXT DEFAULT ''"),
            ("enrollment_required", "BOOLEAN DEFAULT 1"),
            ("region_requirement", "TEXT DEFAULT '[]'"),
            ("nationality", "TEXT DEFAULT 'any'"),
            ("special_tags", "TEXT DEFAULT '[]'"),
            ("no_duplicate_allowed", "BOOLEAN"),
        ]
        with self.engine.connect() as conn:
            for col, definition in new_cols:
                try:
                    conn.execute(text(f"ALTER TABLE scholarships ADD COLUMN {col} {definition}"))
                    conn.commit()
                except Exception:
                    pass  # 이미 존재하면 무시

    def upsert(self, scholarships: list[Scholarship]) -> int:
        with Session(self.engine) as session:
            for s in scholarships:
                existing = session.get(ScholarshipRow, s.id)
                if existing:
                    row = _to_row(s)
                    for col in ScholarshipRow.__table__.columns:
                        if col.name != "id":
                            setattr(existing, col.name, getattr(row, col.name))
                else:
                    session.add(_to_row(s))
            session.commit()
        return len(scholarships)

    def query(
        self,
        source: Optional[str] = None,
        gpa: Optional[float] = None,
        income_bracket: Optional[int] = None,
        year: Optional[int] = None,
        major: Optional[str] = None,
        university: Optional[str] = None,
        regions: Optional[list[str]] = None,
        nationality: Optional[str] = None,
        enrolled: Optional[bool] = None,
        user_tags: Optional[list[str]] = None,
        has_other_scholarship: Optional[bool] = None,
        active_only: bool = True,
    ) -> list[Scholarship]:
        with Session(self.engine) as session:
            stmt = select(ScholarshipRow)
            if source:
                stmt = stmt.where(ScholarshipRow.source == source)
            if active_only:
                stmt = stmt.where(ScholarshipRow.is_active == True)
                today = date.today()
                stmt = stmt.where(
                    or_(ScholarshipRow.apply_end == None, ScholarshipRow.apply_end >= today)
                )

            rows = session.execute(stmt).scalars().all()
            results = [_from_row(r) for r in rows]

        filtered = [
            s for s in results
            if s.matches(
                gpa=gpa,
                income_bracket=income_bracket,
                year=year,
                major=major,
                university=university,
                regions=regions,
                nationality=nationality,
                enrolled=enrolled,
                user_tags=user_tags,
                has_other_scholarship=has_other_scholarship,
            )
        ]
        return _deduplicate(filtered)

    def count(self) -> int:
        with Session(self.engine) as session:
            return session.execute(select(func.count()).select_from(ScholarshipRow)).scalar()

    def clear_all(self):
        with Session(self.engine) as session:
            session.execute(ScholarshipRow.__table__.delete())
            session.commit()


def _normalize_name(name: str) -> str:
    """장학금명 정규화: 공백·괄호·연도 제거 후 소문자."""
    n = re.sub(r"\d{4}년\s*(?:\d+학기)?", "", name)
    n = re.sub(r"[()（）\[\]【】]", "", n)
    n = re.sub(r"\s+", "", n)
    return n.lower()


def _deduplicate(scholarships: list[Scholarship]) -> list[Scholarship]:
    """같은 장학금명(정규화)이 여러 출처에 있을 때 정보가 더 많은 것만 유지."""
    seen: dict[str, Scholarship] = {}
    for s in scholarships:
        key = _normalize_name(s.name)
        if key not in seen:
            seen[key] = s
        else:
            # 기존 vs 현재: 정보 필드 합산이 더 많은 것 유지
            existing = seen[key]
            existing_score = bool(existing.amount_text) + bool(existing.eligibility_text) + len(existing.required_docs)
            new_score = bool(s.amount_text) + bool(s.eligibility_text) + len(s.required_docs)
            if new_score > existing_score:
                seen[key] = s
    return list(seen.values())
