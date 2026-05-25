"use client";
import { useState, useEffect } from "react";

export interface UserProfile {
  // 학업
  gpa: string;
  year: string;
  major: string;
  university: string;
  universityType: string;   // 국립 | 사립
  universityLevel: string;  // 4년제 | 전문대 | 대학원

  // 경제
  income: string;
  isBasicLivelihood: boolean;  // 기초생활수급자
  isNearPoverty: boolean;      // 차상위계층

  // 지역
  residenceRegion: string;
  hometown: string;
  isRural: boolean;  // 농어촌 출신

  // 개인
  gender: string;
  nationality: string;  // 내국인 | 외국인
  birthYear: string;

  // 가족
  siblingCount: string;
  isSingleParent: boolean;
  isMulticultural: boolean;

  // 특수 상황
  hasDisability: boolean;
  militaryStatus: string;  // 미필 | 복무중 | 군필 | 해당없음
  isEmployed: boolean;

  // 활동
  volunteerHours: string;
}

export const EMPTY_PROFILE: UserProfile = {
  gpa: "", year: "", major: "", university: "", universityType: "", universityLevel: "",
  income: "", isBasicLivelihood: false, isNearPoverty: false,
  residenceRegion: "", hometown: "", isRural: false,
  gender: "", nationality: "내국인", birthYear: "",
  siblingCount: "", isSingleParent: false, isMulticultural: false,
  hasDisability: false, militaryStatus: "", isEmployed: false,
  volunteerHours: "",
};

const PROFILE_KEY = "scholarship_user_profile";

export function loadProfile(): UserProfile {
  if (typeof window === "undefined") return EMPTY_PROFILE;
  try {
    const raw = localStorage.getItem(PROFILE_KEY);
    return raw ? { ...EMPTY_PROFILE, ...JSON.parse(raw) } : EMPTY_PROFILE;
  } catch {
    return EMPTY_PROFILE;
  }
}

export function saveProfile(p: UserProfile) {
  localStorage.setItem(PROFILE_KEY, JSON.stringify(p));
}

const REGIONS = [
  "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
  "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주",
];

// ── 사용자 프로필 → 자연어 텍스트 (AI 매칭에 사용) ─────────────────
export function profileToText(p: UserProfile): string {
  const parts: string[] = [];
  if (p.university) parts.push(p.university);
  if (p.major) parts.push(p.major);
  if (p.year) parts.push(`${p.year}학년`);
  if (p.universityLevel) parts.push(p.universityLevel);
  if (p.universityType) parts.push(p.universityType);
  if (p.gpa) parts.push(`성적 ${p.gpa}/4.5`);
  if (p.income) parts.push(`학자금 지원 ${p.income}구간`);
  if (p.isBasicLivelihood) parts.push("기초생활수급자");
  if (p.isNearPoverty) parts.push("차상위계층");
  if (p.residenceRegion) parts.push(`${p.residenceRegion} 거주`);
  if (p.hometown) parts.push(`${p.hometown} 출신`);
  if (p.isRural) parts.push("농어촌 출신");
  if (p.gender && p.gender !== "무관") parts.push(p.gender === "여" ? "여성" : "남성");
  if (p.nationality) parts.push(p.nationality);
  if (p.siblingCount && parseInt(p.siblingCount) >= 3) parts.push(`형제자매 ${p.siblingCount}명`);
  if (p.isSingleParent) parts.push("한부모 가정");
  if (p.isMulticultural) parts.push("다문화 가정");
  if (p.hasDisability) parts.push("장애인 등록");
  if (p.militaryStatus === "복무중") parts.push("군복무 중");
  if (p.volunteerHours) parts.push(`봉사활동 ${p.volunteerHours}시간`);
  return parts.length > 0 ? parts.join(", ") : "조건 미입력";
}

// ── 매칭 키워드 계산 (외부에서도 사용) ──────────────────────────────
export function computeProfileMatches(
  eligibilityText: string,
  profile: UserProfile
): string[] {
  const text = eligibilityText.toLowerCase();
  const tags: string[] = [];
  if (profile.isBasicLivelihood && (text.includes("기초생활") || text.includes("기초수급"))) tags.push("기초생활수급");
  if (profile.isNearPoverty && text.includes("차상위")) tags.push("차상위계층");
  if (profile.hasDisability && text.includes("장애")) tags.push("장애인");
  if (profile.isSingleParent && text.includes("한부모")) tags.push("한부모가정");
  if (profile.isMulticultural && text.includes("다문화")) tags.push("다문화가정");
  if (profile.isRural && (text.includes("농어촌") || text.includes("농촌"))) tags.push("농어촌출신");
  if (profile.gender === "여" && (text.includes("여성") || text.includes("여학생"))) tags.push("여성");
  if (profile.nationality === "외국인" && text.includes("외국인")) tags.push("외국인유학생");
  if (profile.residenceRegion && text.includes(profile.residenceRegion.slice(0, 2))) tags.push(profile.residenceRegion);
  if (profile.hometown && text.includes(profile.hometown.slice(0, 2))) tags.push(`${profile.hometown}출신`);
  if (profile.militaryStatus === "복무중" && text.includes("군")) tags.push("군 관련");
  return tags;
}

interface Props {
  onClose: () => void;
  onSave: (p: UserProfile) => void;
  initial: UserProfile;
}

export default function ProfileModal({ onClose, onSave, initial }: Props) {
  const [p, setP] = useState<UserProfile>(initial);

  function set<K extends keyof UserProfile>(k: K, v: UserProfile[K]) {
    setP((prev) => ({ ...prev, [k]: v }));
  }

  function handleSave() {
    saveProfile(p);
    onSave(p);
    onClose();
  }

  return (
    <div
      className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 bg-white border-b px-6 py-4 flex items-center justify-between z-10">
          <div>
            <h2 className="text-lg font-bold text-gray-900">내 프로필</h2>
            <p className="text-xs text-gray-400 mt-0.5">저장하면 검색에 자동 반영되고, 장학금과 매칭 여부를 확인할 수 있어요</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
        </div>

        <div className="p-6 space-y-6">

          {/* 학업 정보 */}
          <Section title="학업 정보">
            <div className="grid grid-cols-2 gap-3">
              <Field label="성적 (4.5 만점)">
                <input type="number" step="0.01" min="0" max="4.5" placeholder="예: 3.5"
                  value={p.gpa} onChange={(e) => set("gpa", e.target.value)}
                  className={inputCls} />
              </Field>
              <Field label="학년">
                <div className="flex gap-1.5">
                  {["1", "2", "3", "4"].map((y) => (
                    <button key={y} onClick={() => set("year", p.year === y ? "" : y)}
                      className={`flex-1 py-2 rounded-lg text-sm font-medium border transition-colors ${p.year === y ? "bg-blue-600 text-white border-blue-600" : "border-gray-200 text-gray-600 hover:border-blue-300"}`}>
                      {y}학년
                    </button>
                  ))}
                </div>
              </Field>
              <Field label="전공 / 단과대">
                <input placeholder="예: 이공계, 경영대학" value={p.major}
                  onChange={(e) => set("major", e.target.value)} className={inputCls} />
              </Field>
              <Field label="학교명">
                <input placeholder="예: 연세대학교" value={p.university}
                  onChange={(e) => set("university", e.target.value)} className={inputCls} />
              </Field>
              <Field label="학교 유형">
                <SelectRow
                  options={["국립", "사립"]}
                  value={p.universityType}
                  onChange={(v) => set("universityType", v)}
                />
              </Field>
              <Field label="학교 급">
                <SelectRow
                  options={["4년제", "전문대", "대학원"]}
                  value={p.universityLevel}
                  onChange={(v) => set("universityLevel", v)}
                />
              </Field>
            </div>
          </Section>

          {/* 경제 상황 */}
          <Section title="경제 상황">
            <div className="grid grid-cols-2 gap-3">
              <Field label="학자금 지원 구간 (1~10)">
                <select value={p.income} onChange={(e) => set("income", e.target.value)}
                  className={inputCls}>
                  <option value="">선택 안 함</option>
                  {[1,2,3,4,5,6,7,8,9,10].map((n) => (
                    <option key={n} value={n}>{n}구간</option>
                  ))}
                </select>
              </Field>
              <Field label="특수 경제 상황">
                <div className="space-y-2">
                  <Toggle label="기초생활수급자" value={p.isBasicLivelihood} onChange={(v) => set("isBasicLivelihood", v)} />
                  <Toggle label="차상위계층" value={p.isNearPoverty} onChange={(v) => set("isNearPoverty", v)} />
                </div>
              </Field>
            </div>
          </Section>

          {/* 지역 / 출신 */}
          <Section title="지역 · 출신">
            <div className="grid grid-cols-2 gap-3">
              <Field label="거주 지역">
                <select value={p.residenceRegion} onChange={(e) => set("residenceRegion", e.target.value)}
                  className={inputCls}>
                  <option value="">선택 안 함</option>
                  {REGIONS.map((r) => <option key={r} value={r}>{r}</option>)}
                </select>
              </Field>
              <Field label="출신 고교 지역">
                <select value={p.hometown} onChange={(e) => set("hometown", e.target.value)}
                  className={inputCls}>
                  <option value="">선택 안 함</option>
                  {REGIONS.map((r) => <option key={r} value={r}>{r}</option>)}
                </select>
              </Field>
              <Field label="농어촌 출신">
                <Toggle label="농어촌 지역 출신" value={p.isRural} onChange={(v) => set("isRural", v)} />
              </Field>
            </div>
          </Section>

          {/* 개인 정보 */}
          <Section title="개인 정보">
            <div className="grid grid-cols-2 gap-3">
              <Field label="성별">
                <SelectRow options={["남", "여", "무관"]} value={p.gender} onChange={(v) => set("gender", v)} />
              </Field>
              <Field label="국적">
                <SelectRow options={["내국인", "외국인"]} value={p.nationality} onChange={(v) => set("nationality", v)} />
              </Field>
              <Field label="출생연도">
                <input type="number" placeholder="예: 2003" min="1980" max="2010"
                  value={p.birthYear} onChange={(e) => set("birthYear", e.target.value)} className={inputCls} />
              </Field>
            </div>
          </Section>

          {/* 가족 상황 */}
          <Section title="가족 상황">
            <div className="grid grid-cols-2 gap-3">
              <Field label="형제자매 수 (본인 포함)">
                <input type="number" min="1" max="10" placeholder="예: 3"
                  value={p.siblingCount} onChange={(e) => set("siblingCount", e.target.value)} className={inputCls} />
              </Field>
              <Field label="가족 유형">
                <div className="space-y-2">
                  <Toggle label="한부모 가정" value={p.isSingleParent} onChange={(v) => set("isSingleParent", v)} />
                  <Toggle label="다문화 가정" value={p.isMulticultural} onChange={(v) => set("isMulticultural", v)} />
                </div>
              </Field>
            </div>
          </Section>

          {/* 특수 상황 */}
          <Section title="특수 상황">
            <div className="grid grid-cols-2 gap-3">
              <Field label="장애 여부">
                <Toggle label="장애인 등록" value={p.hasDisability} onChange={(v) => set("hasDisability", v)} />
              </Field>
              <Field label="군복무">
                <SelectRow
                  options={["미필", "복무중", "군필", "해당없음"]}
                  value={p.militaryStatus}
                  onChange={(v) => set("militaryStatus", v)}
                />
              </Field>
              <Field label="재직 여부">
                <Toggle label="현재 재직 중" value={p.isEmployed} onChange={(v) => set("isEmployed", v)} />
              </Field>
            </div>
          </Section>

          {/* 활동 */}
          <Section title="활동">
            <div className="grid grid-cols-2 gap-3">
              <Field label="봉사활동 시간 (누적)">
                <input type="number" min="0" placeholder="예: 50"
                  value={p.volunteerHours} onChange={(e) => set("volunteerHours", e.target.value)} className={inputCls} />
              </Field>
            </div>
          </Section>

        </div>

        <div className="sticky bottom-0 bg-white border-t px-6 py-4 flex gap-3">
          <button onClick={onClose}
            className="flex-1 py-3 rounded-xl border border-gray-200 text-gray-600 text-sm font-medium hover:bg-gray-50 transition-colors">
            취소
          </button>
          <button onClick={handleSave}
            className="flex-1 py-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold transition-colors">
            저장하기
          </button>
        </div>
      </div>
    </div>
  );
}

const inputCls = "w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-200";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3">{title}</h3>
      {children}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-medium text-gray-600">{label}</label>
      {children}
    </div>
  );
}

function Toggle({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onChange(!value)}
      className={`flex items-center gap-2 text-sm px-3 py-2 rounded-lg border transition-colors w-full text-left ${value ? "bg-blue-50 border-blue-300 text-blue-700 font-medium" : "border-gray-200 text-gray-500 hover:border-gray-300"}`}
    >
      <span className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 ${value ? "bg-blue-600 border-blue-600" : "border-gray-300"}`}>
        {value && <span className="text-white text-xs">✓</span>}
      </span>
      {label}
    </button>
  );
}

function SelectRow({ options, value, onChange }: { options: string[]; value: string; onChange: (v: string) => void }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map((o) => (
        <button key={o} onClick={() => onChange(value === o ? "" : o)}
          className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${value === o ? "bg-blue-600 text-white border-blue-600" : "border-gray-200 text-gray-600 hover:border-blue-300"}`}>
          {o}
        </button>
      ))}
    </div>
  );
}
