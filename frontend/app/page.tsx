"use client";
import { useState, useEffect } from "react";
import FilterPanel, { type Filters } from "@/components/FilterPanel";
import ScholarshipCard, { type Scholarship } from "@/components/ScholarshipCard";
import ProfileModal, { type UserProfile, loadProfile, EMPTY_PROFILE, profileToText } from "@/components/ProfileModal";

const API = "http://localhost:8000";

const DEFAULT_FILTERS: Filters = { gpa: "", income: "", year: "", major: "" };

export default function Home() {
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [results, setResults] = useState<Scholarship[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [dbTotal, setDbTotal] = useState<number | null>(null);
  const [profile, setProfile] = useState<UserProfile>(EMPTY_PROFILE);
  const [showProfile, setShowProfile] = useState(false);

  type AiResult = { scholarship: Scholarship; match_score: string; match_reason: string };
  const [aiResults, setAiResults] = useState<AiResult[]>([]);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiMode, setAiMode] = useState(false);

  useEffect(() => {
    const p = loadProfile();
    setProfile(p);
    // 저장된 프로필로 필터 자동 채우기
    if (p.gpa || p.income || p.year || p.major) {
      setFilters({
        gpa: p.gpa,
        income: p.income,
        year: p.year,
        major: p.major,
      });
    }
  }, []);

  useEffect(() => {
    fetch(`${API}/api/stats`)
      .then((r) => r.json())
      .then((d) => setDbTotal(d.total))
      .catch(() => {});
  }, []);

  const search = async () => {
    setLoading(true);
    setSearched(true);
    try {
      const params = new URLSearchParams();
      if (filters.gpa)           params.set("gpa", filters.gpa);
      if (filters.income)        params.set("income", filters.income);
      if (filters.year)          params.set("year", filters.year);
      if (filters.major)         params.set("major", filters.major);
      if (profile.hometown)      params.set("hometown", profile.hometown);
      if (profile.residenceRegion) params.set("residence_region", profile.residenceRegion);

      const res = await fetch(`${API}/api/scholarships?${params}`);
      const data = await res.json();
      setResults(data.results);
      setTotal(data.total);
    } catch {
      alert("백엔드 서버에 연결할 수 없어요.\n터미널에서 백엔드를 먼저 실행해주세요.");
    } finally {
      setLoading(false);
    }
  };

  const searchAi = async () => {
    const text = profileToText(profile);
    if (text === "조건 미입력") {
      alert("프로필을 먼저 입력해주세요. 👤 내 프로필 버튼을 눌러 정보를 저장하면 AI가 더 정확하게 매칭해드려요.");
      return;
    }
    setAiLoading(true);
    setAiMode(true);
    setSearched(true);
    try {
      const body = {
        user_profile_text: text,
        gpa: filters.gpa ? parseFloat(filters.gpa) : undefined,
        year: filters.year ? parseInt(filters.year) : undefined,
        income: filters.income ? parseInt(filters.income) : undefined,
        major: filters.major || undefined,
        residence: profile.residenceRegion || undefined,
        hometown: profile.hometown || undefined,
        nationality: profile.nationality === "외국인" ? "foreigner" : profile.nationality === "내국인" ? "korean" : undefined,
      };
      const res = await fetch(`${API}/api/scholarships/ai-match`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `서버 오류 (HTTP ${res.status})`);
      }
      const data = await res.json();
      setAiResults(data.results ?? []);
      setTotal(data.total ?? 0);
    } catch {
      alert("백엔드 서버에 연결할 수 없어요.");
    } finally {
      setAiLoading(false);
    }
  };

  const reset = () => {
    setFilters(DEFAULT_FILTERS);
    setResults([]);
    setAiResults([]);
    setSearched(false);
    setAiMode(false);
    setTotal(0);
  };

  const handleProfileSave = (p: UserProfile) => {
    setProfile(p);
    setFilters({
      gpa: p.gpa,
      income: p.income,
      year: p.year,
      major: p.major,
    });
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 헤더 */}
      <header className="bg-white border-b border-gray-100 sticky top-0 z-40">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-extrabold text-gray-900">🎓 장학금 찾기</h1>
            <p className="text-xs text-gray-400 mt-0.5">
              한국장학재단 · 연세대학교 · 드림스폰
              {dbTotal != null && ` · 총 ${dbTotal}건`}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowProfile(true)}
              className="flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-700 font-medium"
            >
              👤 내 프로필
            </button>
          </div>
        </div>
      </header>

      {/* 히어로 */}
      {!searched && (
        <div className="bg-gradient-to-br from-blue-600 to-indigo-700 text-white py-14 px-4">
          <div className="max-w-6xl mx-auto text-center">
            <h2 className="text-3xl font-extrabold mb-3">나에게 맞는 장학금만 골라보세요</h2>
            <p className="text-blue-100 text-base">
              성적 · 소득 분위 · 학년 · 전공으로 필터링해서 꼭 맞는 장학금을 빠르게 찾아요
            </p>
            {dbTotal != null && (
              <p className="mt-4 text-sm text-blue-200">
                현재 <span className="font-bold text-white">{dbTotal}개</span>의 장학금 정보가 있어요
              </p>
            )}
            <button
              onClick={searchAi}
              className="mt-6 inline-flex items-center gap-2 bg-white text-indigo-700 font-bold text-sm px-5 py-2.5 rounded-full shadow hover:bg-indigo-50 transition-colors"
            >
              ✦ AI가 내 프로필로 직접 골라주기
            </button>
          </div>
        </div>
      )}

      {/* 메인 */}
      <main className="max-w-6xl mx-auto px-4 py-8">
        <div className="flex flex-col lg:flex-row gap-6">
          <FilterPanel
            filters={filters}
            onChange={setFilters}
            onSearch={search}
            loading={loading}
            total={total}
            profile={profile}
            onOpenProfile={() => setShowProfile(true)}
          />

          <div className="flex-1">
            {!searched && !loading && (
              <div className="flex flex-col items-center justify-center py-24 text-gray-400">
                <span className="text-5xl mb-4">🔍</span>
                <p className="text-lg font-medium">조건을 입력하고 검색해보세요</p>
                <p className="text-sm mt-1">조건을 비워두고 검색하면 전체 목록이 나와요</p>
              </div>
            )}

            {searched && !loading && !aiLoading && (
              <div className="flex items-center justify-between mb-4">
                <p className="text-sm text-gray-600">
                  {aiMode ? (
                    <>✦ AI 매칭 결과 <span className="font-bold text-indigo-600">{total}건</span></>
                  ) : (
                    <>조건에 맞는 장학금 <span className="font-bold text-blue-600">{total}건</span></>
                  )}
                </p>
                <button onClick={reset} className="text-xs text-gray-400 hover:text-gray-600 underline">
                  초기화
                </button>
              </div>
            )}

            {(loading || aiLoading) && (
              <div className="flex flex-col items-center justify-center py-24 text-gray-400 gap-3">
                <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
                {aiLoading && <p className="text-sm">AI가 장학금을 분석하고 있어요...</p>}
              </div>
            )}

            {searched && !loading && !aiLoading && (aiMode ? aiResults : results).length === 0 && (
              <div className="flex flex-col items-center justify-center py-24 text-gray-400">
                <span className="text-5xl mb-4">😔</span>
                <p className="text-lg font-medium">조건에 맞는 장학금이 없어요</p>
                <p className="text-sm mt-1">조건을 조금 완화해보세요</p>
              </div>
            )}

            {!aiMode && results.length > 0 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                {results.map((s) => (
                  <ScholarshipCard key={s.id} s={s} profile={profile} />
                ))}
              </div>
            )}

            {aiMode && aiResults.length > 0 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                {aiResults.map((r) => (
                  <ScholarshipCard
                    key={r.scholarship.id}
                    s={r.scholarship}
                    profile={profile}
                    matchScore={r.match_score}
                    matchReason={r.match_reason}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </main>

      {/* 프로필 모달 */}
      {showProfile && (
        <ProfileModal
          initial={profile}
          onClose={() => setShowProfile(false)}
          onSave={handleProfileSave}
        />
      )}
    </div>
  );
}
