"use client";
import { UserProfile } from "./ProfileModal";

export interface Filters {
  gpa: string;
  income: string;
  year: string;
  major: string;
}

interface Props {
  filters: Filters;
  onChange: (f: Filters) => void;
  onSearch: () => void;
  loading: boolean;
  total: number;
  profile: UserProfile;
  onOpenProfile: () => void;
}

const YEAR_OPTIONS = ["1", "2", "3", "4"];
const INCOME_OPTIONS = [
  { value: "", label: "선택 안 함" },
  { value: "1", label: "1구간 (기초생활수급)" },
  { value: "2", label: "2구간" },
  { value: "3", label: "3구간" },
  { value: "4", label: "4구간" },
  { value: "5", label: "5구간" },
  { value: "6", label: "6구간" },
  { value: "7", label: "7구간" },
  { value: "8", label: "8구간" },
  { value: "9", label: "9구간" },
  { value: "10", label: "10구간" },
];

function profileBadgeCount(p: UserProfile): number {
  let n = 0;
  if (p.gpa) n++;
  if (p.income) n++;
  if (p.year) n++;
  if (p.major) n++;
  if (p.university) n++;
  if (p.isBasicLivelihood) n++;
  if (p.isNearPoverty) n++;
  if (p.isRural) n++;
  if (p.hasDisability) n++;
  if (p.isSingleParent) n++;
  if (p.isMulticultural) n++;
  if (p.residenceRegion) n++;
  if (p.gender) n++;
  return n;
}

export default function FilterPanel({ filters, onChange, onSearch, loading, total, profile, onOpenProfile }: Props) {
  const set = (key: keyof Filters) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      onChange({ ...filters, [key]: e.target.value });

  const toggleYear = (y: string) =>
    onChange({ ...filters, year: filters.year === y ? "" : y });

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") onSearch();
  };

  const profileCount = profileBadgeCount(profile);

  return (
    <aside className="w-full lg:w-72 shrink-0">
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 sticky top-6 space-y-5">

        {/* 내 프로필 버튼 */}
        <button
          onClick={onOpenProfile}
          className="w-full flex items-center justify-between px-4 py-3 rounded-xl border-2 border-dashed border-blue-200 hover:border-blue-400 hover:bg-blue-50 transition-colors group"
        >
          <div className="flex items-center gap-2">
            <span className="text-lg">👤</span>
            <div className="text-left">
              <p className="text-sm font-semibold text-blue-700 group-hover:text-blue-800">내 프로필 설정</p>
              <p className="text-xs text-gray-400">
                {profileCount > 0 ? `${profileCount}개 항목 입력됨 · 매칭 활성화` : "입력하면 장학금 매칭 정보가 표시돼요"}
              </p>
            </div>
          </div>
          {profileCount > 0 && (
            <span className="text-xs bg-blue-600 text-white font-bold px-2 py-0.5 rounded-full">{profileCount}</span>
          )}
        </button>

        <div className="border-t border-gray-100" />

        <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wide -mb-1">필터 검색</h2>

        {/* 성적 */}
        <div>
          <label className="block text-sm font-semibold text-gray-600 mb-1.5">
            성적 <span className="text-gray-400 font-normal">(4.5 만점)</span>
          </label>
          <input
            type="number" step="0.1" min="0" max="4.5" placeholder="예: 3.5"
            value={filters.gpa} onChange={set("gpa")} onKeyDown={handleKey}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <p className="text-xs text-gray-400 mt-1">이 성적 이상 신청 가능한 장학금만 표시</p>
        </div>

        {/* 학자금 지원 구간 */}
        <div>
          <label className="block text-sm font-semibold text-gray-600 mb-1.5">학자금 지원 구간</label>
          <select value={filters.income} onChange={set("income")}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
            {INCOME_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
          <p className="text-xs text-gray-400 mt-1">내 구간 이하 조건인 장학금만 표시</p>
        </div>

        {/* 학년 */}
        <div>
          <label className="block text-sm font-semibold text-gray-600 mb-2">학년</label>
          <div className="flex gap-2">
            {YEAR_OPTIONS.map((y) => (
              <button key={y} onClick={() => toggleYear(y)}
                className={`flex-1 py-2 rounded-lg text-sm font-medium border transition-colors ${
                  filters.year === y
                    ? "bg-blue-600 text-white border-blue-600"
                    : "bg-white text-gray-600 border-gray-200 hover:border-blue-400"
                }`}>
                {y}학년
              </button>
            ))}
          </div>
        </div>

        {/* 전공 */}
        <div>
          <label className="block text-sm font-semibold text-gray-600 mb-1.5">전공 / 단과대</label>
          <input type="text" placeholder="예: 이공계, 경영대학"
            value={filters.major} onChange={set("major")} onKeyDown={handleKey}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <button onClick={onSearch} disabled={loading}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white font-semibold py-2.5 rounded-xl transition-colors">
          {loading ? "검색 중..." : "장학금 찾기"}
        </button>

        {total > 0 && (
          <p className="text-center text-sm text-gray-500">
            총 <span className="font-bold text-blue-600">{total}건</span> 발견
          </p>
        )}
      </div>
    </aside>
  );
}
