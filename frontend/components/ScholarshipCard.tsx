"use client";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { UserProfile, computeProfileMatches } from "./ProfileModal";

export interface Scholarship {
  id: string;
  source: string;
  source_url: string;
  name: string;
  organization: string;
  description: string;
  amount_text: string;
  gpa_min: number | null;
  income_bracket_max: number | null;
  target_years: number[];
  target_majors: string[];
  eligibility_text: string;
  required_docs: string[];
  apply_end: string | null;
  is_active: boolean;
  attachment_urls: string[];
  attachment_text: string;
  apply_url: string;
  ai_summary: string;
}

const SOURCE_DOMAIN: Record<string, string> = {
  kosaf: "kosaf.go.kr",
  yonsei: "yonsei.ac.kr",
  dreamspon: "dreamspon.com",
};

function fileLabel(url: string): string {
  const lower = url.toLowerCase();
  if (lower.includes(".pdf")) return "PDF";
  if (lower.includes(".hwpx") || lower.includes(".hwp")) return "HWP";
  if (lower.includes(".docx") || lower.includes(".doc")) return "DOC";
  if (lower.includes(".xlsx") || lower.includes(".xls")) return "EXCEL";
  return "파일";
}

const SCORE_STYLE: Record<string, { bg: string; text: string; label: string }> = {
  high:   { bg: "bg-emerald-50 border-emerald-200", text: "text-emerald-700", label: "높은 매칭" },
  medium: { bg: "bg-amber-50 border-amber-200",    text: "text-amber-700",   label: "부분 매칭" },
  low:    { bg: "bg-red-50 border-red-200",         text: "text-red-600",     label: "낮은 매칭" },
};

export default function ScholarshipCard({
  s,
  profile,
  matchScore,
  matchReason,
}: {
  s: Scholarship;
  profile: UserProfile;
  matchScore?: string;
  matchReason?: string;
}) {
  const [open, setOpen] = useState(false);
  const matches = computeProfileMatches(s.eligibility_text + " " + s.attachment_text, profile);

  return (
    <>
      <article
        onClick={() => setOpen(true)}
        className="bg-white rounded-2xl border border-gray-100 shadow-sm hover:shadow-md hover:border-blue-200 transition-all cursor-pointer p-5 flex flex-col gap-3"
      >
        {/* AI 매칭 배지 */}
        {matchScore && SCORE_STYLE[matchScore] && (
          <div className={`-mx-1 -mt-1 px-3 py-1.5 rounded-xl border ${SCORE_STYLE[matchScore].bg} flex items-center gap-1.5`}>
            <span className={`text-xs font-bold ${SCORE_STYLE[matchScore].text}`}>
              ✦ {SCORE_STYLE[matchScore].label}
            </span>
            {matchReason && (
              <span className={`text-xs ${SCORE_STYLE[matchScore].text} opacity-80 line-clamp-1`}>
                — {matchReason}
              </span>
            )}
          </div>
        )}

        {/* 기관 + 모집상태 */}
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs font-medium text-gray-500 truncate">{s.organization}</span>
          {s.is_active
            ? <span className="text-xs text-emerald-600 font-semibold shrink-0">모집 중</span>
            : <span className="text-xs text-gray-400 shrink-0">마감</span>
          }
        </div>

        {/* 장학금명 */}
        <h3 className="font-bold text-gray-900 text-base leading-snug line-clamp-2">{s.name}</h3>

        {/* 금액 */}
        {s.amount_text && (
          <div className="bg-blue-50 rounded-lg px-3 py-2">
            <span className="text-xs text-blue-500 font-medium">지원 금액</span>
            <p className="text-sm font-semibold text-blue-800 mt-0.5 line-clamp-2">{s.amount_text}</p>
          </div>
        )}

        {/* 프로필 매칭 태그 */}
        {matches.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {matches.slice(0, 3).map((m) => (
              <span key={m} className="text-xs bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-0.5 rounded-full font-medium">
                ✓ {m}
              </span>
            ))}
            {matches.length > 3 && (
              <span className="text-xs text-emerald-600 font-medium">+{matches.length - 3}개</span>
            )}
          </div>
        )}

        {/* 조건 태그 */}
        <div className="flex flex-wrap gap-1.5 mt-auto">
          {s.income_bracket_max != null && (
            <Tag icon="💰">{s.income_bracket_max}구간 이하</Tag>
          )}
          {s.gpa_min != null && (
            <Tag icon="📚">성적 {s.gpa_min} 이상</Tag>
          )}
          {s.target_years.length > 0 && (
            <Tag icon="🎓">{s.target_years.join("·")}학년</Tag>
          )}
          {s.target_majors.slice(0, 2).map((m) => (
            <Tag key={m} icon="🏫">{m}</Tag>
          ))}
          {s.apply_end && (
            <Tag icon="📅">~{s.apply_end}</Tag>
          )}
          {s.attachment_urls.length > 0 && (
            <Tag icon="📎">{s.attachment_urls.length}개 첨부</Tag>
          )}
        </div>
      </article>

      {/* 상세 모달 */}
      {open && (
        <div
          className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
          onClick={() => setOpen(false)}
        >
          <div
            className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[85vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-6">
              <div className="flex items-start justify-between mb-4">
                <span className="text-sm text-gray-500">{s.organization}</span>
                <button onClick={() => setOpen(false)}
                  className="text-gray-400 hover:text-gray-600 text-xl leading-none ml-4 shrink-0">
                  ✕
                </button>
              </div>

              <h2 className="text-xl font-bold text-gray-900 mb-4">{s.name}</h2>

              {/* AI 매칭 결과 */}
              {matchScore && SCORE_STYLE[matchScore] && (
                <div className={`mb-4 p-3 rounded-xl border ${SCORE_STYLE[matchScore].bg}`}>
                  <p className={`text-xs font-bold ${SCORE_STYLE[matchScore].text} mb-1`}>
                    ✦ AI 매칭 — {SCORE_STYLE[matchScore].label}
                  </p>
                  {matchReason && (
                    <p className={`text-sm ${SCORE_STYLE[matchScore].text}`}>{matchReason}</p>
                  )}
                </div>
              )}

              {/* AI 요약 */}
              {s.ai_summary && (
                <div className="mb-4 p-3 bg-indigo-50 rounded-xl border border-indigo-100">
                  <p className="text-xs font-bold text-indigo-500 mb-1">✦ AI 요약</p>
                  <div className="text-sm text-indigo-900 leading-relaxed prose prose-sm prose-indigo max-w-none">
                    <ReactMarkdown>{s.ai_summary}</ReactMarkdown>
                  </div>
                </div>
              )}

              {/* 프로필 매칭 */}
              {matches.length > 0 && (
                <div className="mb-4 p-3 bg-emerald-50 rounded-xl border border-emerald-100">
                  <p className="text-xs font-bold text-emerald-700 mb-1.5">내 프로필과 매칭된 조건</p>
                  <div className="flex flex-wrap gap-1.5">
                    {matches.map((m) => (
                      <span key={m} className="text-xs bg-white text-emerald-700 border border-emerald-200 px-2 py-0.5 rounded-full font-medium">
                        ✓ {m}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {s.amount_text && (
                <Section title="지원 금액">
                  <p className="text-sm text-gray-700">{s.amount_text}</p>
                </Section>
              )}

              <Section title="지원 조건">
                <div className="flex flex-wrap gap-2 mb-3">
                  {s.income_bracket_max != null && <Tag icon="💰">{s.income_bracket_max}구간 이하</Tag>}
                  {s.gpa_min != null && <Tag icon="📚">성적 {s.gpa_min} 이상</Tag>}
                  {s.target_years.length > 0 && <Tag icon="🎓">{s.target_years.join("·")}학년</Tag>}
                  {s.target_majors.map((m) => <Tag key={m} icon="🏫">{m}</Tag>)}
                  {s.apply_end && <Tag icon="📅">마감 {s.apply_end}</Tag>}
                </div>
                {s.eligibility_text && (
                  <p className="text-sm text-gray-600 whitespace-pre-line leading-relaxed line-clamp-8">
                    {s.eligibility_text}
                  </p>
                )}
              </Section>

              {s.required_docs.length > 0 && (
                <Section title="제출 서류">
                  <ul className="space-y-1">
                    {s.required_docs.map((doc, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                        <span className="text-blue-400 shrink-0 mt-0.5">•</span>
                        {doc}
                      </li>
                    ))}
                  </ul>
                </Section>
              )}

              {/* 첨부파일 */}
              {s.attachment_urls.length > 0 && (
                <Section title="첨부파일">
                  <div className="space-y-2">
                    {s.attachment_urls.map((url, i) => {
                      const label = fileLabel(url);
                      const isPdf = label === "PDF";
                      return (
                        <a key={i} href={url} target="_blank" rel="noopener noreferrer"
                          className="flex items-center gap-2.5 px-3 py-2.5 rounded-xl border border-gray-200 hover:border-blue-300 hover:bg-blue-50 transition-colors group"
                          onClick={(e) => e.stopPropagation()}>
                          <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${isPdf ? "bg-red-100 text-red-600" : "bg-amber-100 text-amber-700"}`}>
                            {label}
                          </span>
                          <span className="text-sm text-gray-600 group-hover:text-blue-600 truncate flex-1">
                            첨부파일 {i + 1}
                          </span>
                          <span className="text-gray-300 group-hover:text-blue-400">↗</span>
                        </a>
                      );
                    })}
                  </div>
                  {s.attachment_text && (
                    <p className="mt-2 text-xs text-gray-400">* PDF 내용이 조건 분석에 반영됐어요</p>
                  )}
                </Section>
              )}

              <div className="mt-4 flex flex-col gap-2">
                {s.apply_url && (
                  <a href={s.apply_url} target="_blank" rel="noopener noreferrer"
                    className="block w-full bg-emerald-600 hover:bg-emerald-700 text-white text-center font-semibold py-3 rounded-xl transition-colors">
                    온라인 신청 바로가기 →
                  </a>
                )}
                <a href={s.source_url} target="_blank" rel="noopener noreferrer"
                  className={`block w-full text-center font-semibold py-3 rounded-xl transition-colors ${s.apply_url ? "bg-gray-100 hover:bg-gray-200 text-gray-700" : "bg-blue-600 hover:bg-blue-700 text-white"}`}>
                  공고 원문 보기 ({SOURCE_DOMAIN[s.source] ?? s.source}) →
                </a>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function Tag({ icon, children }: { icon: string; children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1 text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded-full">
      {icon} {children}
    </span>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-4">
      <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">{title}</h4>
      {children}
    </div>
  );
}
