"""
parse_eligibility.py

DB에 저장된 장학금의 eligibility_text(원문)를 Claude API로 파싱해서
구조화된 필터 필드를 추출 후 DB에 저장합니다.

추출 필드:
  - gpa_min          : 최소 성적 (숫자)
  - gpa_scale        : 성적 만점 기준 (4.5 or 100.0)
  - income_bracket_max: 소득 분위 상한 (1~10)
  - target_years     : 신청 가능 학년 리스트 [1,2,3,4]
  - target_majors    : 신청 가능 전공/단과대 리스트
  - ai_summary       : 2~3문장 한국어 요약

사용법:
  python parse_eligibility.py                 # 전체 처리
  python parse_eligibility.py --limit 5       # 5건만 테스트
  python parse_eligibility.py --id kosaf_001  # 특정 ID만
"""

import argparse
import json
import os
import sqlite3
import sys
import time

import anthropic

DB_PATH = os.path.join(os.path.dirname(__file__), "scholarships.db")
MODEL = "claude-haiku-4-5"

# ── JSON Schema (구조화된 출력) ──────────────────────────────────────────────
EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "gpa_min": {
            "type": ["number", "null"],
            "description": "최소 성적 요건 (숫자). 예: 3.0, 80. 없으면 null."
        },
        "gpa_scale": {
            "type": ["number", "null"],
            "description": "성적 만점 기준. 4.5 만점이면 4.5, 100점 만점이면 100.0. 없으면 null."
        },
        "income_bracket_max": {
            "type": ["integer", "null"],
            "description": "학자금 지원 구간 상한 (1~10 정수). '8구간 이하'→8, '8분위 이하'→8 (분위와 구간을 동일하게 처리). 없으면 null."
        },
        "target_years": {
            "type": "array",
            "items": {"type": "integer"},
            "description": "신청 가능한 학년 목록. 예: [1,2,3,4]. '전학년' 또는 명시 없으면 []."
        },
        "target_majors": {
            "type": "array",
            "items": {"type": "string"},
            "description": "신청 가능한 전공 또는 단과대 목록. 예: ['이공계', '인문사회계']. 제한 없으면 []."
        },
        "region_requirement": {
            "type": "array",
            "items": {"type": "string"},
            "description": "지역 거주·주민등록 조건. 예: ['이천시'], ['경기도']. 전국 가능하면 []."
        },
        "nationality": {
            "type": "string",
            "enum": ["any", "korean", "foreigner"],
            "description": "'외국인 유학생 전용'이면 foreigner, '내국인 한정'이면 korean, 그 외 any."
        },
        "enrollment_required": {
            "type": "boolean",
            "description": "재학 중이어야 신청 가능한지. 휴학생도 신청 가능하다고 명시된 경우 false, 그 외 true."
        },
        "special_tags": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": ["한부모", "다자녀", "조손", "장애", "농어촌", "보호종료", "이공계", "사범계", "국가유공자", "새터민", "독립유공자"]
            },
            "description": "특수 자격 조건 태그. 해당 조건 보유자만 신청 가능한 경우에만 포함. 없으면 []."
        },
        "no_duplicate_allowed": {
            "type": ["boolean", "null"],
            "description": "중복 수혜 제한 여부. 타 장학금 수혜 중이면 불가 → true, 가능 → false, 언급 없음 → null."
        },
        "ai_summary": {
            "type": "string",
            "description": "이 장학금의 핵심 내용을 2~3문장으로 요약 (한국어). 금액·자격조건·특이사항 포함."
        }
    },
    "required": [
        "gpa_min", "gpa_scale", "income_bracket_max", "target_years", "target_majors",
        "region_requirement", "nationality", "enrollment_required",
        "special_tags", "no_duplicate_allowed", "ai_summary"
    ],
    "additionalProperties": False
}

SYSTEM_PROMPT = """당신은 장학금 공지문에서 지원 자격 조건을 추출하는 전문가입니다.
주어진 텍스트에서 다음 정보를 정확히 파싱해 JSON으로 반환하세요.

규칙:
1. 명시적으로 언급된 정보만 추출하세요. 불분명하면 null 또는 빈 배열([]).
2. 성적 기준: "3.0/4.5" → gpa_min=3.0, gpa_scale=4.5 / "80점 이상" → gpa_min=80.0, gpa_scale=100.0
3. 학자금 지원 구간: "8구간 이하" → 8 / "8분위 이하" → 8 (분위와 구간은 동일하게 취급) / "기초생활수급자·차상위" → 2
4. 학년: "1, 2학년" → [1,2] / "재학생 전체" → [] / "신입생(1학년)" → [1]
5. 전공: "이공계열" → ["이공계"] / "사범대학, 의과대학" → ["사범대학", "의과대학"]
6. region_requirement: "이천시 거주자" → ["이천시"] / "경기도 내 대학 재학생" → ["경기도"] / 전국 가능이면 []
7. nationality: "외국인 유학생 전용" → "foreigner" / "내국인 한정" → "korean" / 그 외 → "any"
8. enrollment_required: "휴학생도 지원 가능" → false / 그 외 → true
9. special_tags: 해당하는 태그만 포함. 한부모·다자녀·조손·장애·농어촌·보호종료·이공계·사범계·국가유공자·새터민·독립유공자
10. no_duplicate_allowed: "타 장학금 수혜자 제외" → true / "중복 수혜 가능" → false / 언급 없음 → null
11. ai_summary: 금액, 핵심 자격조건, 특이사항을 포함한 2~3문장 한국어 요약
"""


def fetch_records(conn: sqlite3.Connection, limit: int | None, target_id: str | None) -> list[dict]:
    """파싱이 필요한 레코드 조회."""
    cur = conn.cursor()
    if target_id:
        rows = cur.execute(
            "SELECT id, name, organization, eligibility_text, amount_text FROM scholarships WHERE id = ?",
            (target_id,)
        ).fetchall()
    else:
        rows = cur.execute(
            """SELECT id, name, organization, eligibility_text, amount_text
               FROM scholarships
               WHERE eligibility_text IS NOT NULL AND eligibility_text != ''
               ORDER BY id"""
        ).fetchall()

    records = [
        {"id": r[0], "name": r[1], "organization": r[2],
         "eligibility_text": r[3], "amount_text": r[4]}
        for r in rows
    ]
    if limit:
        records = records[:limit]
    return records


def parse_one(client: anthropic.Anthropic, record: dict) -> dict:
    """Claude API로 eligibility_text 파싱."""
    user_content = f"""장학금명: {record['name']}
기관: {record['organization']}
금액 정보: {record['amount_text'] or '(없음)'}

[자격 조건 원문]
{record['eligibility_text'][:3000]}
"""
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
        tools=[{
            "name": "extract_scholarship_fields",
            "description": "장학금 자격 조건에서 필터링 필드를 추출합니다.",
            "input_schema": EXTRACTION_SCHEMA,
        }],
        tool_choice={"type": "tool", "name": "extract_scholarship_fields"},
    )
    return response.content[0].input


def update_record(conn: sqlite3.Connection, record_id: str, parsed: dict):
    """파싱 결과를 DB에 업데이트."""
    conn.execute(
        """UPDATE scholarships SET
            gpa_min = ?,
            gpa_scale = ?,
            income_bracket_max = ?,
            target_years = ?,
            target_majors = ?,
            region_requirement = ?,
            nationality = ?,
            enrollment_required = ?,
            special_tags = ?,
            no_duplicate_allowed = ?,
            ai_summary = ?
           WHERE id = ?""",
        (
            parsed.get("gpa_min"),
            parsed.get("gpa_scale"),
            parsed.get("income_bracket_max"),
            json.dumps(parsed.get("target_years", []), ensure_ascii=False),
            json.dumps(parsed.get("target_majors", []), ensure_ascii=False),
            json.dumps(parsed.get("region_requirement", []), ensure_ascii=False),
            parsed.get("nationality", "any"),
            parsed.get("enrollment_required", True),
            json.dumps(parsed.get("special_tags", []), ensure_ascii=False),
            parsed.get("no_duplicate_allowed"),
            parsed.get("ai_summary", ""),
            record_id,
        )
    )
    conn.commit()


def print_summary(conn: sqlite3.Connection):
    """처리 후 필드 채움 현황 출력."""
    cur = conn.cursor()
    total = cur.execute("SELECT COUNT(*) FROM scholarships").fetchone()[0]

    def count(cond: str) -> int:
        return cur.execute(f"SELECT COUNT(*) FROM scholarships WHERE {cond}").fetchone()[0]

    stats = [
        ("gpa_min",            "gpa_min IS NOT NULL"),
        ("income_bracket_max", "income_bracket_max IS NOT NULL"),
        ("target_years",       "target_years != '[]'"),
        ("target_majors",      "target_majors != '[]'"),
        ("region_requirement", "region_requirement != '[]'"),
        ("nationality",        "nationality != 'any'"),
        ("special_tags",       "special_tags != '[]'"),
        ("no_duplicate",       "no_duplicate_allowed IS NOT NULL"),
        ("ai_summary",         "ai_summary != ''"),
    ]

    print(f"\n{'─'*40}")
    print(f"{'필드':<22} {'채움':>6} / {'전체':>5}")
    print(f"{'─'*40}")
    for label, cond in stats:
        print(f"{label:<22} {count(cond):>6} / {total:>5}")
    print(f"{'─'*40}")


def main():
    parser = argparse.ArgumentParser(description="eligibility_text → 구조화 필드 추출")
    parser.add_argument("--limit", type=int, default=None, help="처리할 최대 건수")
    parser.add_argument("--id", type=str, default=None, help="특정 레코드 ID만 처리")
    parser.add_argument("--db", default=DB_PATH, help="DB 파일 경로")
    parser.add_argument("--dry-run", action="store_true", help="API 호출 없이 레코드 목록만 출력")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    records = fetch_records(conn, args.limit, args.id)

    if not records:
        print("처리할 레코드가 없습니다.")
        conn.close()
        return

    print(f"처리 대상: {len(records)}건 (모델: {MODEL})")

    if args.dry_run:
        for r in records:
            print(f"  - [{r['id']}] {r['name']}")
        conn.close()
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("오류: ANTHROPIC_API_KEY 환경 변수를 설정해 주세요.", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    success = 0
    fail = 0
    for i, record in enumerate(records, 1):
        print(f"[{i}/{len(records)}] {record['name'][:40]}", end=" ... ", flush=True)
        try:
            parsed = parse_one(client, record)
            update_record(conn, record["id"], parsed)
            print(f"✓  (gpa={parsed.get('gpa_min')}, 소득={parsed.get('income_bracket_max')}, "
                  f"학년={parsed.get('target_years')}, 지역={parsed.get('region_requirement')}, "
                  f"태그={parsed.get('special_tags')}, 중복제한={parsed.get('no_duplicate_allowed')})")
            success += 1
        except Exception as e:
            print(f"✗  오류: {e}")
            fail += 1
        # Rate limit 방지: 0.3초 대기
        if i < len(records):
            time.sleep(0.3)

    print(f"\n처리 완료: 성공 {success}건, 실패 {fail}건")
    print_summary(conn)
    conn.close()


if __name__ == "__main__":
    main()
