import React, { useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronUp, GripVertical, Trash2 } from "lucide-react";

export interface DashboardConfig {
  apiKey: string;
  baseUrl: string;
}

type NumberField = number | "";
type ViewName = "home" | "profile" | "preview" | "indexing" | "account";
type SectionName = "experiences" | "projects" | "skills" | "education" | "achievements" | "personal_topics";

interface Experience {
  id?: string;
  organization: string;
  role: string;
  start_month: NumberField;
  start_year: NumberField;
  end_month: NumberField;
  end_year: NumberField;
  is_current: boolean;
  summary: string;
  outcome: string;
  display_order: number;
}

interface Project {
  id?: string;
  name: string;
  problem: string;
  contribution: string;
  outcome: string;
  measurable_impact: string;
  technologies: string[];
  collaborators: string[];
  links: string[];
  start_month: NumberField;
  start_year: NumberField;
  end_month: NumberField;
  end_year: NumberField;
  is_current: boolean;
  featured: boolean;
  visibility: "public" | "private";
  display_order: number;
}

interface Skill {
  id?: string;
  name: string;
  category: string;
  aliases: string[];
  context: string;
  evidence: string;
  display_order: number;
}

interface Education {
  id?: string;
  institution: string;
  credential: string;
  field: string;
  start_month: NumberField;
  start_year: NumberField;
  end_month: NumberField;
  end_year: NumberField;
  is_current: boolean;
  summary: string;
  outcome: string;
  display_order: number;
}

interface Achievement {
  id?: string;
  title: string;
  summary: string;
  outcome: string;
  month: NumberField;
  year: NumberField;
  featured: boolean;
  display_order: number;
}

interface PersonalTopic {
  id?: string;
  category: string;
  detail: string;
  approved: boolean;
  display_order: number;
}

interface ProfileDraft {
  owner_id: string;
  owner_name: string;
  experiences: Experience[];
  projects: Project[];
  skills: Skill[];
  education: Education[];
  achievements: Achievement[];
  personal_topics: PersonalTopic[];
  published_version: number | null;
  has_published_snapshot: boolean;
}

type CanonicalSnapshot = Partial<ProfileDraft> & {
  version?: number;
  published_at?: string;
};

interface PublishedSnapshot {
  version: number;
  published_at: string;
  snapshot: CanonicalSnapshot;
}

interface IndexStatus {
  owner_id: string;
  published_version: number | null;
  indexed_version: number | null;
  indexed_backend_version: string | null;
  indexed_at: string | null;
  chunk_count: number;
  is_stale: boolean;
}

interface IndexChunk {
  id: string;
  source_type: string;
  source_id: string;
  title: string;
}

interface IndexResponse extends IndexStatus {
  chunks: IndexChunk[];
}

interface AskEvidence {
  source_type: string;
  source_id: string;
  title: string;
  quote: string;
}

interface AskResponse {
  answer: string;
  evidence: AskEvidence[];
  snapshot_version: number;
  status: "SUPPORTED" | "PARTIAL" | "UNANSWERABLE";
  knowledge_backend: string;
  knowledge_backend_version: string;
}

interface ApiIssue {
  field: string;
  message: string;
}

interface AccountDetails {
  name: string;
  email: string;
  organization: string;
  timezone: string;
}

const emptyExperience = (displayOrder: number): Experience => ({
  organization: "",
  role: "",
  start_month: "",
  start_year: "",
  end_month: "",
  end_year: "",
  is_current: false,
  summary: "",
  outcome: "",
  display_order: displayOrder,
});

const emptyProject = (displayOrder: number): Project => ({
  name: "",
  problem: "",
  contribution: "",
  outcome: "",
  measurable_impact: "",
  technologies: [],
  collaborators: [],
  links: [],
  start_month: "",
  start_year: "",
  end_month: "",
  end_year: "",
  is_current: false,
  featured: false,
  visibility: "public",
  display_order: displayOrder,
});

const emptySkill = (displayOrder: number): Skill => ({
  name: "",
  category: "",
  aliases: [],
  context: "",
  evidence: "",
  display_order: displayOrder,
});

const emptyEducation = (displayOrder: number): Education => ({
  institution: "",
  credential: "",
  field: "",
  start_month: "",
  start_year: "",
  end_month: "",
  end_year: "",
  is_current: false,
  summary: "",
  outcome: "",
  display_order: displayOrder,
});

const emptyAchievement = (displayOrder: number): Achievement => ({
  title: "",
  summary: "",
  outcome: "",
  month: "",
  year: "",
  featured: false,
  display_order: displayOrder,
});

const emptyPersonalTopic = (displayOrder: number): PersonalTopic => ({
  category: "",
  detail: "",
  approved: true,
  display_order: displayOrder,
});

const sectionFactories = {
  experiences: emptyExperience,
  projects: emptyProject,
  skills: emptySkill,
  education: emptyEducation,
  achievements: emptyAchievement,
  personal_topics: emptyPersonalTopic,
};

function toNullableNumber(value: NumberField): number | null {
  return value === "" ? null : Number(value);
}

function splitCsv(value: string): string[] {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function toMonthValue(month: NumberField | null | undefined, year: NumberField | null | undefined): string {
  if (!month || !year) return "";
  return `${String(year).padStart(4, "0")}-${String(month).padStart(2, "0")}`;
}

function monthValuePatch(value: string): { month: NumberField; year: NumberField } {
  if (!value) return { month: "", year: "" };
  const [year, month] = value.split("-").map(Number);
  return { month, year };
}

function isDateRangeBackwards(item: {
  start_month: NumberField;
  start_year: NumberField;
  end_month: NumberField;
  end_year: NumberField;
  is_current: boolean;
}): boolean {
  if (item.is_current || !item.start_month || !item.start_year || !item.end_month || !item.end_year) return false;
  return Number(item.end_year) * 100 + Number(item.end_month) < Number(item.start_year) * 100 + Number(item.start_month);
}

function validateProfileForPublication(profile: ProfileDraft): ApiIssue[] {
  const issues: ApiIssue[] = [];
  const add = (field: string, message: string) => issues.push({ field, message });

  if (!profile.owner_name.trim()) add("owner_name", "Owner name is required.");
  if (!profile.experiences.length && !profile.projects.length) {
    add("profile", "At least one experience or project is required before publication.");
  }

  profile.experiences.forEach((item, index) => {
    const prefix = `experiences.${index}`;
    if (!item.organization.trim()) add(`${prefix}.organization`, "Organization is required.");
    if (!item.role.trim()) add(`${prefix}.role`, "Role is required.");
    validateRequiredDateRange(issues, prefix, item);
    if (!item.summary.trim()) add(`${prefix}.summary`, "Summary is required.");
  });

  profile.projects.forEach((item, index) => {
    const prefix = `projects.${index}`;
    if (!item.name.trim()) add(`${prefix}.name`, "Project name is required.");
    if (!item.problem.trim()) add(`${prefix}.problem`, "Problem is required.");
    if (!item.contribution.trim()) add(`${prefix}.contribution`, "Contribution is required.");
    validateRequiredDateRange(issues, prefix, item);
  });

  profile.skills.forEach((item, index) => {
    if (!item.name.trim()) add(`skills.${index}.name`, "Skill name is required.");
  });

  profile.education.forEach((item, index) => {
    const prefix = `education.${index}`;
    if (!item.institution.trim()) add(`${prefix}.institution`, "Institution is required.");
    if (!item.credential.trim()) add(`${prefix}.credential`, "Credential is required.");
    validateRequiredDateRange(issues, prefix, item);
  });

  profile.achievements.forEach((item, index) => {
    const prefix = `achievements.${index}`;
    if (!item.title.trim()) add(`${prefix}.title`, "Title is required.");
    if (!item.summary.trim()) add(`${prefix}.summary`, "Summary is required.");
  });

  profile.personal_topics.forEach((item, index) => {
    const prefix = `personal_topics.${index}`;
    if (item.approved && !item.category.trim()) add(`${prefix}.category`, "Category is required.");
    if (item.approved && !item.detail.trim()) add(`${prefix}.detail`, "Detail is required.");
  });

  return issues;
}

function validateRequiredDateRange(
  issues: ApiIssue[],
  prefix: string,
  item: { start_month: NumberField; start_year: NumberField; end_month: NumberField; end_year: NumberField; is_current: boolean },
) {
  if (!item.start_month || !item.start_year) issues.push({ field: `${prefix}.start`, message: "Start date is required." });
  if (!item.is_current && (!item.end_month || !item.end_year)) {
    issues.push({ field: `${prefix}.end`, message: "End date is required unless this is current." });
  }
  if (isDateRangeBackwards(item)) {
    issues.push({ field: `${prefix}.end`, message: "End date cannot be before start date." });
  }
}

function sectionCount(profile: Pick<ProfileDraft, SectionName>): number {
  return (
    profile.experiences.length +
    profile.projects.length +
    profile.skills.length +
    profile.education.length +
    profile.achievements.length +
    profile.personal_topics.filter((topic) => topic.approved).length
  );
}

function completionScore(profile: ProfileDraft): number {
  const checks = [
    profile.owner_name.trim().length > 0,
    profile.experiences.length > 0,
    profile.experiences.every((item) => item.organization && item.role && item.summary),
    profile.projects.length > 0,
    profile.projects.every((item) => item.name && item.problem && item.contribution),
    profile.skills.length > 0,
    profile.education.length > 0,
  ];
  return Math.round((checks.filter(Boolean).length / checks.length) * 100);
}

function missingProfileItems(profile: ProfileDraft): string[] {
  const missing: string[] = [];
  if (!profile.owner_name.trim()) missing.push("Owner name");
  if (!profile.experiences.length) missing.push("At least one experience");
  if (!profile.projects.length) missing.push("At least one project");
  if (!profile.skills.length) missing.push("Skills");
  if (!profile.education.length) missing.push("Education");
  return missing;
}

function normalizeForApi(profile: ProfileDraft) {
  return {
    owner_name: profile.owner_name,
    experiences: profile.experiences.map((exp, index) => ({
      ...exp,
      start_month: toNullableNumber(exp.start_month),
      start_year: toNullableNumber(exp.start_year),
      end_month: exp.is_current ? null : toNullableNumber(exp.end_month),
      end_year: exp.is_current ? null : toNullableNumber(exp.end_year),
      display_order: index,
    })),
    projects: profile.projects.map((project, index) => ({
      ...project,
      start_month: toNullableNumber(project.start_month),
      start_year: toNullableNumber(project.start_year),
      end_month: project.is_current ? null : toNullableNumber(project.end_month),
      end_year: project.is_current ? null : toNullableNumber(project.end_year),
      display_order: index,
    })),
    skills: profile.skills.map((skill, index) => ({ ...skill, display_order: index })),
    education: profile.education.map((item, index) => ({
      ...item,
      start_month: toNullableNumber(item.start_month),
      start_year: toNullableNumber(item.start_year),
      end_month: item.is_current ? null : toNullableNumber(item.end_month),
      end_year: item.is_current ? null : toNullableNumber(item.end_year),
      display_order: index,
    })),
    achievements: profile.achievements.map((item, index) => ({
      ...item,
      month: toNullableNumber(item.month),
      year: toNullableNumber(item.year),
      display_order: index,
    })),
    personal_topics: profile.personal_topics.map((topic, index) => ({ ...topic, display_order: index })),
  };
}

function issueMap(issues: ApiIssue[]): Record<string, string> {
  return Object.fromEntries(issues.map((issue) => [issue.field, issue.message]));
}

function hydrateDraft(draft: ProfileDraft): ProfileDraft {
  return {
    ...draft,
    experiences: (draft.experiences ?? []).map((item, index) => ({
      ...emptyExperience(index),
      ...item,
      start_month: item.start_month ?? "",
      start_year: item.start_year ?? "",
      end_month: item.end_month ?? "",
      end_year: item.end_year ?? "",
      display_order: index,
    })),
    projects: (draft.projects ?? []).map((item, index) => ({
      ...emptyProject(index),
      ...item,
      start_month: item.start_month ?? "",
      start_year: item.start_year ?? "",
      end_month: item.end_month ?? "",
      end_year: item.end_year ?? "",
      display_order: index,
    })),
    skills: (draft.skills ?? []).map((item, index) => ({ ...emptySkill(index), ...item, display_order: index })),
    education: (draft.education ?? []).map((item, index) => ({
      ...emptyEducation(index),
      ...item,
      start_month: item.start_month ?? "",
      start_year: item.start_year ?? "",
      end_month: item.end_month ?? "",
      end_year: item.end_year ?? "",
      display_order: index,
    })),
    achievements: (draft.achievements ?? []).map((item, index) => ({
      ...emptyAchievement(index),
      ...item,
      month: item.month ?? "",
      year: item.year ?? "",
      display_order: index,
    })),
    personal_topics: (draft.personal_topics ?? []).map((item, index) => ({
      ...emptyPersonalTopic(index),
      ...item,
      display_order: index,
    })),
  };
}

function initialView(): ViewName {
  const hash = window.location.hash.replace("#", "");
  if (hash === "profile" || hash === "preview" || hash === "indexing" || hash === "account") return hash;
  return "home";
}

export function Dashboard({ config }: { config: DashboardConfig }) {
  const [activeView, setActiveView] = useState<ViewName>(initialView);
  const [profile, setProfile] = useState<ProfileDraft>({
    owner_id: "",
    owner_name: "",
    experiences: [],
    projects: [],
    skills: [],
    education: [],
    achievements: [],
    personal_topics: [],
    published_version: null,
    has_published_snapshot: false,
  });
  const [account, setAccount] = useState<AccountDetails>({
    name: "Amrut Savadatti",
    email: "amrut@example.com",
    organization: "TAARS",
    timezone: "America/New_York",
  });
  const [published, setPublished] = useState<PublishedSnapshot | null>(null);
  const [indexStatus, setIndexStatus] = useState<IndexStatus | null>(null);
  const [indexing, setIndexing] = useState(false);
  const [question, setQuestion] = useState("What backend experience does this profile show?");
  const [asking, setAsking] = useState(false);
  const [answer, setAnswer] = useState<AskResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [status, setStatus] = useState("");
  const [issues, setIssues] = useState<ApiIssue[]>([]);

  const errors = useMemo(() => issueMap(issues), [issues]);
  const completion = useMemo(() => completionScore(profile), [profile]);
  const missingItems = useMemo(() => missingProfileItems(profile), [profile]);

  function navigate(view: ViewName) {
    window.location.hash = view === "home" ? "" : view;
    setActiveView(view);
  }

  async function api(path: string, init: RequestInit = {}) {
    const res = await fetch(`${config.baseUrl}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": config.apiKey,
        ...(init.headers ?? {}),
      },
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw { status: res.status, body };
    }
    return res.json();
  }

  async function loadProfile() {
    setLoading(true);
    setStatus("");
    try {
      setProfile(hydrateDraft((await api("/api/v1/profile")) as ProfileDraft));
      try {
        setPublished((await api("/api/v1/profile/published-snapshot")) as PublishedSnapshot);
      } catch {
        setPublished(null);
      }
      try {
        setIndexStatus((await api("/api/v1/profile/index-status")) as IndexStatus);
      } catch {
        setIndexStatus(null);
      }
    } finally {
      setLoading(false);
    }
  }

  async function indexPublishedProfile() {
    setIndexing(true);
    setStatus("");
    setAnswer(null);
    try {
      const indexed = (await api("/api/v1/profile/index", { method: "POST" })) as IndexResponse;
      setIndexStatus(indexed);
      setStatus(`Indexed published profile version ${indexed.indexed_version}.`);
    } catch (err) {
      const maybeError = err as { body?: { detail?: string } };
      setStatus(maybeError.body?.detail || "Indexing failed.");
    } finally {
      setIndexing(false);
    }
  }

  async function askIndexedProfile() {
    if (!question.trim()) return;
    setAsking(true);
    setStatus("");
    try {
      setAnswer((await api("/api/v1/ask", {
        method: "POST",
        body: JSON.stringify({ question }),
      })) as AskResponse);
    } catch (err) {
      const maybeError = err as { body?: { detail?: string } };
      setStatus(maybeError.body?.detail || "Question failed.");
    } finally {
      setAsking(false);
    }
  }

  useEffect(() => {
    void loadProfile();
    const onHashChange = () => setActiveView(initialView());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function updateItem<T extends SectionName>(section: T, index: number, patch: Partial<ProfileDraft[T][number]>) {
    setProfile((current) => ({
      ...current,
      [section]: current[section].map((item, i) => (i === index ? { ...item, ...patch } : item)),
    }));
  }

  function addItem(section: SectionName) {
    setProfile((current) => ({
      ...current,
      [section]: [...current[section], sectionFactories[section](current[section].length)],
    }));
  }

  function removeItem(section: SectionName, index: number) {
    setProfile((current) => ({
      ...current,
      [section]: current[section].filter((_, i) => i !== index).map((item, i) => ({ ...item, display_order: i })),
    }));
  }

  function reorder(section: SectionName, fromIndex: number, toIndex: number) {
    setProfile((current) => {
      const next = [...current[section]];
      if (fromIndex === toIndex || fromIndex < 0 || toIndex < 0 || fromIndex >= next.length || toIndex >= next.length) {
        return current;
      }
      const [moved] = next.splice(fromIndex, 1);
      next.splice(toIndex, 0, moved);
      return { ...current, [section]: next.map((item, i) => ({ ...item, display_order: i })) };
    });
  }

  async function saveDraft() {
    setSaving(true);
    setStatus("");
    setIssues([]);
    try {
      const saved = (await api("/api/v1/profile/draft", {
        method: "PUT",
        body: JSON.stringify(normalizeForApi(profile)),
      })) as ProfileDraft;
      setProfile(hydrateDraft(saved));
      setStatus("Draft saved.");
    } finally {
      setSaving(false);
    }
  }

  async function publishProfile() {
    const clientIssues = validateProfileForPublication(profile);
    if (clientIssues.length) {
      setIssues(clientIssues);
      setStatus("Publication blocked. Fix the highlighted fields.");
      navigate("profile");
      return;
    }

    setPublishing(true);
    setStatus("");
    setIssues([]);
    try {
      await saveDraft();
      const snapshot = (await api("/api/v1/profile/publish", { method: "POST" })) as PublishedSnapshot;
      setPublished(snapshot);
      setProfile((current) => ({
        ...current,
        published_version: snapshot.version,
        has_published_snapshot: true,
      }));
      setStatus(`Published version ${snapshot.version}.`);
      navigate("preview");
    } catch (err) {
      const maybeError = err as { body?: { detail?: { issues?: ApiIssue[] } } };
      const apiIssues = maybeError.body?.detail?.issues;
      if (apiIssues) {
        setIssues(apiIssues);
        setStatus("Publication blocked. Fix the highlighted fields.");
        navigate("profile");
      } else {
        setStatus("Something went wrong.");
      }
    } finally {
      setPublishing(false);
    }
  }

  if (loading) {
    return <main className="dashboard-shell">Loading profile…</main>;
  }

  return (
    <main className="dashboard-shell">
      <aside className="dashboard-nav">
        <div className="dashboard-logo">TAARS</div>
        <nav>
          <NavButton active={activeView === "home"} onClick={() => navigate("home")}>Home</NavButton>
          <NavButton active={activeView === "profile"} onClick={() => navigate("profile")}>Profile builder</NavButton>
          <NavButton active={activeView === "preview"} onClick={() => navigate("preview")}>Published profile</NavButton>
          <a aria-disabled="true">Conversations</a>
          <NavButton active={activeView === "indexing"} onClick={() => navigate("indexing")}>Indexing</NavButton>
          <NavButton active={activeView === "account"} onClick={() => navigate("account")}>Account</NavButton>
        </nav>
      </aside>

      <section className="dashboard-main">
        {status && <div className={issues.length ? "banner error" : "banner"}>{status}</div>}

        {activeView === "home" && (
          <HomeView
            profile={profile}
            published={published}
            indexStatus={indexStatus}
            completion={completion}
            missingItems={missingItems}
            navigate={navigate}
          />
        )}

        {activeView === "profile" && (
          <ProfileBuilderView
            profile={profile}
            errors={errors}
            saving={saving}
            publishing={publishing}
            saveDraft={saveDraft}
            publishProfile={publishProfile}
            setProfile={setProfile}
            addItem={addItem}
            removeItem={removeItem}
            reorder={reorder}
            updateItem={updateItem}
          />
        )}

        {activeView === "preview" && (
          <PublishedProfileView published={published} navigate={navigate} />
        )}

        {activeView === "indexing" && (
          <IndexingView
            published={published}
            indexStatus={indexStatus}
            indexing={indexing}
            question={question}
            asking={asking}
            answer={answer}
            setQuestion={setQuestion}
            indexPublishedProfile={indexPublishedProfile}
            askIndexedProfile={askIndexedProfile}
            navigate={navigate}
          />
        )}

        {activeView === "account" && (
          <AccountView account={account} setAccount={setAccount} />
        )}
      </section>
    </main>
  );
}

function HomeView({
  profile,
  published,
  indexStatus,
  completion,
  missingItems,
  navigate,
}: {
  profile: ProfileDraft;
  published: PublishedSnapshot | null;
  indexStatus: IndexStatus | null;
  completion: number;
  missingItems: string[];
  navigate: (view: ViewName) => void;
}) {
  const totalRecords = sectionCount(profile);
  const indexingLabel = indexStatus?.indexed_version ? `v${indexStatus.indexed_version}` : "Not indexed";
  const indexingDetail = indexStatus?.is_stale ? "Published profile changed; re-index needed" : "Ready for evidenced Q&A";
  return (
    <>
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">Overview</p>
          <h1>Analytics dashboard</h1>
          <p className="muted">Quick view of profile readiness, publication status, and placeholder product metrics.</p>
        </div>
        <div className="header-actions">
          <button type="button" onClick={() => navigate("profile")}>Edit profile</button>
          <button className="primary" type="button" onClick={() => navigate("preview")}>View published profile</button>
        </div>
      </header>

      <section className="metric-grid">
        <MetricCard label="Profile completeness" value={`${completion}%`} detail={`${missingItems.length} gaps remaining`} />
        <MetricCard label="Published profile" value={published ? `v${published.version}` : "Not published"} detail={published ? new Date(published.published_at).toLocaleString() : "Publish after required fields are complete"} />
        <MetricCard label="Canonical records" value={String(totalRecords)} detail="Draft profile sections" />
        <MetricCard label="Indexing status" value={indexingLabel} detail={indexStatus?.indexed_version ? indexingDetail : "Index published profile next"} />
      </section>

      <section className="grid two">
        <article className="card">
          <h2>Profile readiness</h2>
          {missingItems.length ? (
            <ul className="check-list">
              {missingItems.map((item) => <li key={item}>{item}</li>)}
            </ul>
          ) : (
            <p className="muted">No obvious profile gaps in the current draft.</p>
          )}
        </article>

        <article className="card">
          <h2>Conversation analytics</h2>
          <div className="placeholder-grid">
            <MetricCard label="Visitors" value="—" detail="Backend metric pending" />
            <MetricCard label="Questions" value="—" detail="Backend metric pending" />
            <MetricCard label="Low-confidence answers" value="—" detail="Will use evidence checks" />
          </div>
        </article>
      </section>
    </>
  );
}

function ProfileBuilderView({
  profile,
  errors,
  saving,
  publishing,
  saveDraft,
  publishProfile,
  setProfile,
  addItem,
  removeItem,
  reorder,
  updateItem,
}: {
  profile: ProfileDraft;
  errors: Record<string, string>;
  saving: boolean;
  publishing: boolean;
  saveDraft: () => Promise<void>;
  publishProfile: () => Promise<void>;
  setProfile: React.Dispatch<React.SetStateAction<ProfileDraft>>;
  addItem: (section: SectionName) => void;
  removeItem: (section: SectionName, index: number) => void;
  reorder: (section: SectionName, fromIndex: number, toIndex: number) => void;
  updateItem: <T extends SectionName>(section: T, index: number, patch: Partial<ProfileDraft[T][number]>) => void;
}) {
  const [collapsedCards, setCollapsedCards] = useState<Record<string, boolean>>({});
  const [draggedCard, setDraggedCard] = useState<{ section: SectionName; index: number } | null>(null);
  const cardKey = (section: SectionName, item: { id?: string }, index: number) => `${section}:${item.id ?? index}`;
  const isCollapsed = (section: SectionName, item: { id?: string }, index: number) => Boolean(collapsedCards[cardKey(section, item, index)]);
  const toggleCard = (section: SectionName, item: { id?: string }, index: number) => {
    const key = cardKey(section, item, index);
    setCollapsedCards((current) => ({ ...current, [key]: !current[key] }));
  };
  const addSectionItem = (section: SectionName) => {
    const items = profile[section];
    const lastIndex = items.length - 1;
    if (lastIndex >= 0) {
      const key = cardKey(section, items[lastIndex], lastIndex);
      setCollapsedCards((current) => ({ ...current, [key]: true }));
    }
    addItem(section);
  };
  const dragProps = (section: SectionName, index: number) => ({
    section,
    index,
    draggedCard,
    setDraggedCard,
    reorder,
  });

  return (
    <>
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">Canonical profile</p>
          <h1>Profile builder</h1>
          <p className="muted">Edit the canonical draft. Publishing freezes a stable snapshot for future indexing.</p>
        </div>
        <div className="header-actions">
          <button onClick={saveDraft} disabled={saving || publishing} type="button">{saving ? "Saving…" : "Save draft"}</button>
          <button className="primary" onClick={publishProfile} disabled={saving || publishing} type="button">{publishing ? "Publishing…" : "Publish"}</button>
        </div>
      </header>

      <section className="card">
        <label className="field">
          <span>Owner name</span>
          <input value={profile.owner_name} onChange={(e) => setProfile((current) => ({ ...current, owner_name: e.target.value }))} placeholder="Owner name" />
          {errors.owner_name && <em>{errors.owner_name}</em>}
        </label>
      </section>

      <SectionHeading title="Experiences" description="Roles, companies, dates, summaries, and optional outcomes." onAdd={() => addSectionItem("experiences")} />
      {profile.experiences.map((exp, index) => {
        const collapsed = isCollapsed("experiences", exp, index);
        return (
          <DraggableCard key={exp.id ?? `experience-${index}`} {...dragProps("experiences", index)}>
            <Toolbar title={`Experience ${index + 1}`} subtitle={`${exp.role || "Untitled role"} · ${exp.organization || "No organization"}`} section="experiences" index={index} count={profile.experiences.length} reorder={reorder} remove={removeItem} collapsed={collapsed} onToggle={() => toggleCard("experiences", exp, index)} />
            {!collapsed && (
              <>
                <div className="grid two">
                  <Field label="Organization" value={exp.organization} error={errors[`experiences.${index}.organization`]} onChange={(value) => updateItem("experiences", index, { organization: value })} />
                  <Field label="Role" value={exp.role} error={errors[`experiences.${index}.role`]} onChange={(value) => updateItem("experiences", index, { role: value })} />
                </div>
                <DateFields prefix={`experiences.${index}`} item={exp} errors={errors} onChange={(patch) => updateItem("experiences", index, patch)} />
                <TextArea label="Summary" value={exp.summary} error={errors[`experiences.${index}.summary`]} onChange={(value) => updateItem("experiences", index, { summary: value })} />
                <TextArea label="Outcome (optional)" value={exp.outcome} error={errors[`experiences.${index}.outcome`]} onChange={(value) => updateItem("experiences", index, { outcome: value })} />
              </>
            )}
          </DraggableCard>
        );
      })}
      {profile.experiences.length > 0 && <CardAddButton label="Add another experience" onClick={() => addSectionItem("experiences")} />}

      <SectionHeading title="Projects" description="Specific work with problem, contribution, optional outcome, tech, links, and visibility." onAdd={() => addSectionItem("projects")} />
      {profile.projects.map((project, index) => {
        const collapsed = isCollapsed("projects", project, index);
        return (
          <DraggableCard key={project.id ?? `project-${index}`} {...dragProps("projects", index)}>
            <Toolbar title={`Project ${index + 1}`} subtitle={project.name || "Untitled project"} section="projects" index={index} count={profile.projects.length} reorder={reorder} remove={removeItem} collapsed={collapsed} onToggle={() => toggleCard("projects", project, index)} />
            {!collapsed && (
              <>
                <Field label="Project name" value={project.name} error={errors[`projects.${index}.name`]} onChange={(value) => updateItem("projects", index, { name: value })} />
                <DateFields prefix={`projects.${index}`} item={project} errors={errors} onChange={(patch) => updateItem("projects", index, patch)} />
                <TextArea label="Problem" value={project.problem} error={errors[`projects.${index}.problem`]} onChange={(value) => updateItem("projects", index, { problem: value })} />
                <TextArea label="Contribution" value={project.contribution} error={errors[`projects.${index}.contribution`]} onChange={(value) => updateItem("projects", index, { contribution: value })} />
                <TextArea label="Outcome (optional)" value={project.outcome} error={errors[`projects.${index}.outcome`]} onChange={(value) => updateItem("projects", index, { outcome: value })} />
                <TextArea label="Measurable impact" value={project.measurable_impact} onChange={(value) => updateItem("projects", index, { measurable_impact: value })} />
                <div className="grid three">
                  <Field label="Technologies" value={project.technologies.join(", ")} onChange={(value) => updateItem("projects", index, { technologies: splitCsv(value) })} />
                  <Field label="Collaborators" value={project.collaborators.join(", ")} onChange={(value) => updateItem("projects", index, { collaborators: splitCsv(value) })} />
                  <Field label="Links" value={project.links.join(", ")} onChange={(value) => updateItem("projects", index, { links: splitCsv(value) })} />
                </div>
                <div className="inline-options">
                  <label className="checkbox"><input type="checkbox" checked={project.featured} onChange={(e) => updateItem("projects", index, { featured: e.target.checked })} /> Featured</label>
                  <label className="field compact">
                    <span>Visibility</span>
                    <select value={project.visibility} onChange={(e) => updateItem("projects", index, { visibility: e.target.value as Project["visibility"] })}>
                      <option value="public">Public</option>
                      <option value="private">Private</option>
                    </select>
                  </label>
                </div>
              </>
            )}
          </DraggableCard>
        );
      })}
      {profile.projects.length > 0 && <CardAddButton label="Add another project" onClick={() => addSectionItem("projects")} />}

      <SectionHeading title="Skills" description="Canonical skills with category, aliases, context, and evidence. Not a raw keyword dump." onAdd={() => addSectionItem("skills")} />
      {profile.skills.map((skill, index) => {
        const collapsed = isCollapsed("skills", skill, index);
        return (
          <DraggableCard key={skill.id ?? `skill-${index}`} {...dragProps("skills", index)}>
            <Toolbar title={`Skill ${index + 1}`} subtitle={`${skill.name || "Untitled skill"}${skill.category ? ` · ${skill.category}` : ""}`} section="skills" index={index} count={profile.skills.length} reorder={reorder} remove={removeItem} collapsed={collapsed} onToggle={() => toggleCard("skills", skill, index)} />
            {!collapsed && (
              <>
                <div className="grid two">
                  <Field label="Skill name" value={skill.name} error={errors[`skills.${index}.name`]} onChange={(value) => updateItem("skills", index, { name: value })} />
                  <Field label="Category" value={skill.category} onChange={(value) => updateItem("skills", index, { category: value })} />
                </div>
                <Field label="Aliases / search terms" value={skill.aliases.join(", ")} onChange={(value) => updateItem("skills", index, { aliases: splitCsv(value) })} />
                <TextArea label="Context" value={skill.context} onChange={(value) => updateItem("skills", index, { context: value })} />
                <TextArea label="Evidence" value={skill.evidence} onChange={(value) => updateItem("skills", index, { evidence: value })} />
              </>
            )}
          </DraggableCard>
        );
      })}
      {profile.skills.length > 0 && <CardAddButton label="Add another skill" onClick={() => addSectionItem("skills")} />}

      <SectionHeading title="Education" description="Education records with required dates and optional outcomes." onAdd={() => addSectionItem("education")} />
      {profile.education.map((item, index) => {
        const collapsed = isCollapsed("education", item, index);
        return (
          <DraggableCard key={item.id ?? `education-${index}`} {...dragProps("education", index)}>
            <Toolbar title={`Education ${index + 1}`} subtitle={`${item.credential || "Credential"} · ${item.institution || "Institution"}`} section="education" index={index} count={profile.education.length} reorder={reorder} remove={removeItem} collapsed={collapsed} onToggle={() => toggleCard("education", item, index)} />
            {!collapsed && (
              <>
                <div className="grid three">
                  <Field label="Institution" value={item.institution} error={errors[`education.${index}.institution`]} onChange={(value) => updateItem("education", index, { institution: value })} />
                  <Field label="Credential" value={item.credential} error={errors[`education.${index}.credential`]} onChange={(value) => updateItem("education", index, { credential: value })} />
                  <Field label="Field" value={item.field} onChange={(value) => updateItem("education", index, { field: value })} />
                </div>
                <DateFields prefix={`education.${index}`} item={item} errors={errors} onChange={(patch) => updateItem("education", index, patch)} />
                <TextArea label="Summary" value={item.summary} onChange={(value) => updateItem("education", index, { summary: value })} />
                <TextArea label="Outcome (optional)" value={item.outcome} onChange={(value) => updateItem("education", index, { outcome: value })} />
              </>
            )}
          </DraggableCard>
        );
      })}
      {profile.education.length > 0 && <CardAddButton label="Add another education record" onClick={() => addSectionItem("education")} />}

      <SectionHeading title="Achievements" description="Awards, launches, recognitions, or notable wins." onAdd={() => addSectionItem("achievements")} />
      {profile.achievements.map((item, index) => {
        const collapsed = isCollapsed("achievements", item, index);
        return (
          <DraggableCard key={item.id ?? `achievement-${index}`} {...dragProps("achievements", index)}>
            <Toolbar title={`Achievement ${index + 1}`} subtitle={item.title || "Untitled achievement"} section="achievements" index={index} count={profile.achievements.length} reorder={reorder} remove={removeItem} collapsed={collapsed} onToggle={() => toggleCard("achievements", item, index)} />
            {!collapsed && (
              <>
                <Field label="Title" value={item.title} error={errors[`achievements.${index}.title`]} onChange={(value) => updateItem("achievements", index, { title: value })} />
                <label className="field">
                  <span>Achievement date</span>
                  <input
                    type="month"
                    min="1900-01"
                    value={toMonthValue(item.month, item.year)}
                    onChange={(e) => {
                      const patch = monthValuePatch(e.target.value);
                      updateItem("achievements", index, { month: patch.month, year: patch.year });
                    }}
                  />
                </label>
                <label className="checkbox"><input type="checkbox" checked={item.featured} onChange={(e) => updateItem("achievements", index, { featured: e.target.checked })} /> Featured</label>
                <TextArea label="Summary" value={item.summary} error={errors[`achievements.${index}.summary`]} onChange={(value) => updateItem("achievements", index, { summary: value })} />
                <TextArea label="Outcome (optional)" value={item.outcome} error={errors[`achievements.${index}.outcome`]} onChange={(value) => updateItem("achievements", index, { outcome: value })} />
              </>
            )}
          </DraggableCard>
        );
      })}
      {profile.achievements.length > 0 && <CardAddButton label="Add another achievement" onClick={() => addSectionItem("achievements")} />}

      <SectionHeading title="Approved personal topics" description="Only approved topics are copied into the published snapshot." onAdd={() => addSectionItem("personal_topics")} />
      {profile.personal_topics.map((topic, index) => {
        const collapsed = isCollapsed("personal_topics", topic, index);
        return (
          <DraggableCard key={topic.id ?? `topic-${index}`} {...dragProps("personal_topics", index)}>
            <Toolbar title={`Topic ${index + 1}`} subtitle={topic.category || "Uncategorized topic"} section="personal_topics" index={index} count={profile.personal_topics.length} reorder={reorder} remove={removeItem} collapsed={collapsed} onToggle={() => toggleCard("personal_topics", topic, index)} />
            {!collapsed && (
              <>
                <Field label="Category" value={topic.category} error={errors[`personal_topics.${index}.category`]} onChange={(value) => updateItem("personal_topics", index, { category: value })} />
                <TextArea label="Detail" value={topic.detail} error={errors[`personal_topics.${index}.detail`]} onChange={(value) => updateItem("personal_topics", index, { detail: value })} />
                <label className="checkbox"><input type="checkbox" checked={topic.approved} onChange={(e) => updateItem("personal_topics", index, { approved: e.target.checked })} /> Approved for publication</label>
              </>
            )}
          </DraggableCard>
        );
      })}
      {profile.personal_topics.length > 0 && <CardAddButton label="Add another personal topic" onClick={() => addSectionItem("personal_topics")} />}
    </>
  );
}

function PublishedProfileView({ published, navigate }: { published: PublishedSnapshot | null; navigate: (view: ViewName) => void }) {
  if (!published) {
    return (
      <>
        <header className="dashboard-header">
          <div>
            <p className="eyebrow">Published profile</p>
            <h1>No published profile yet</h1>
            <p className="muted">Publish the canonical profile to create the stable snapshot preview.</p>
          </div>
          <button className="primary" type="button" onClick={() => navigate("profile")}>Go to profile builder</button>
        </header>
      </>
    );
  }

  const snapshot = published.snapshot;
  const groupedSkills = (snapshot.skills ?? []).reduce<Record<string, Skill[]>>((groups, skill) => {
    const category = skill.category || "General";
    groups[category] = [...(groups[category] ?? []), skill];
    return groups;
  }, {});

  return (
    <>
      <header className="dashboard-header profile-preview-header">
        <div>
          <p className="eyebrow">Published profile</p>
          <h1>{snapshot.owner_name || "Profile"}</h1>
          <p className="muted">Version {published.version} · {new Date(published.published_at).toLocaleString()}</p>
        </div>
        <button type="button" onClick={() => navigate("profile")}>Edit draft</button>
      </header>

      <section className="profile-preview">
        <PreviewSection title="Experience">
          {(snapshot.experiences ?? []).map((item) => (
            <PreviewItem key={item.id} title={`${item.role} · ${item.organization}`} meta={dateRange(item)}>
              <p>{item.summary}</p>
              <p className="outcome">Outcome: {item.outcome}</p>
            </PreviewItem>
          ))}
        </PreviewSection>

        <PreviewSection title="Featured projects">
          {(snapshot.projects ?? []).map((item) => (
            <PreviewItem key={item.id} title={item.name} meta={dateRange(item)}>
              <p>{item.problem}</p>
              <p>{item.contribution}</p>
              <p className="outcome">Outcome: {item.outcome}</p>
              {item.technologies?.length ? <div className="tag-row">{item.technologies.map((tech) => <span key={tech}>{tech}</span>)}</div> : null}
            </PreviewItem>
          ))}
        </PreviewSection>

        <PreviewSection title="Skills">
          <div className="skill-groups">
            {Object.entries(groupedSkills).map(([category, skills]) => (
              <div className="skill-group" key={category}>
                <h3>{category}</h3>
                <div className="tag-row">{skills.map((skill) => <span key={skill.id}>{skill.name}</span>)}</div>
              </div>
            ))}
          </div>
        </PreviewSection>

        <PreviewSection title="Education">
          {(snapshot.education ?? []).map((item) => (
            <PreviewItem key={item.id} title={`${item.credential} ${item.field ? `· ${item.field}` : ""}`} meta={`${item.institution} · ${dateRange(item)}`}>
              {item.summary && <p>{item.summary}</p>}
              {item.outcome && <p className="outcome">Outcome: {item.outcome}</p>}
            </PreviewItem>
          ))}
        </PreviewSection>

        <PreviewSection title="Achievements">
          {(snapshot.achievements ?? []).map((item) => (
            <PreviewItem key={item.id} title={item.title} meta={item.year ? `${item.month || ""}/${item.year}` : undefined}>
              <p>{item.summary}</p>
              <p className="outcome">Outcome: {item.outcome}</p>
            </PreviewItem>
          ))}
        </PreviewSection>

        <PreviewSection title="Personal topics">
          {(snapshot.personal_topics ?? []).map((topic) => (
            <PreviewItem key={topic.id} title={topic.category}>
              <p>{topic.detail}</p>
            </PreviewItem>
          ))}
        </PreviewSection>
      </section>

      <details className="card snapshot-debug">
        <summary>View raw snapshot JSON</summary>
        <pre>{JSON.stringify(snapshot, null, 2)}</pre>
      </details>
    </>
  );
}

function IndexingView({
  published,
  indexStatus,
  indexing,
  question,
  asking,
  answer,
  setQuestion,
  indexPublishedProfile,
  askIndexedProfile,
  navigate,
}: {
  published: PublishedSnapshot | null;
  indexStatus: IndexStatus | null;
  indexing: boolean;
  question: string;
  asking: boolean;
  answer: AskResponse | null;
  setQuestion: React.Dispatch<React.SetStateAction<string>>;
  indexPublishedProfile: () => Promise<void>;
  askIndexedProfile: () => Promise<void>;
  navigate: (view: ViewName) => void;
}) {
  const canAsk = Boolean(indexStatus?.indexed_version && !indexStatus.is_stale);

  return (
    <>
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">Retrieval pipeline</p>
          <h1>Indexing</h1>
          <p className="muted">Index the active published profile snapshot with pgvector, then test one evidenced answer.</p>
        </div>
        <div className="header-actions">
          <button type="button" onClick={() => navigate("preview")}>View published profile</button>
          <button className="primary" type="button" onClick={indexPublishedProfile} disabled={indexing || !published}>
            {indexing ? "Indexing…" : indexStatus?.is_stale ? "Re-index published profile" : "Index published profile"}
          </button>
        </div>
      </header>

      <section className="metric-grid">
        <MetricCard label="Published version" value={published ? `v${published.version}` : "None"} detail={published ? new Date(published.published_at).toLocaleString() : "Publish a profile first"} />
        <MetricCard label="Indexed version" value={indexStatus?.indexed_version ? `v${indexStatus.indexed_version}` : "None"} detail={indexStatus?.is_stale ? "Stale; re-index required" : "Matches latest indexed snapshot"} />
        <MetricCard label="Chunks" value={String(indexStatus?.chunk_count ?? 0)} detail="Structured profile chunks" />
        <MetricCard label="Last indexed" value={indexStatus?.indexed_at ? new Date(indexStatus.indexed_at).toLocaleDateString() : "Never"} detail={indexStatus?.indexed_at ? new Date(indexStatus.indexed_at).toLocaleTimeString() : "No index yet"} />
      </section>

      {!published && (
        <section className="card">
          <h2>No published snapshot</h2>
          <p className="muted">Create and publish the profile before indexing.</p>
          <button type="button" onClick={() => navigate("profile")}>Go to profile builder</button>
        </section>
      )}

      <section className="card">
        <h2>Ask one evidenced question</h2>
        <p className="muted">Test the same grounded answer pipeline used by the visitor widget.</p>
        <label className="field">
          <span>Question</span>
          <input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="What backend experience does Amrut have?" />
        </label>
        <button className="primary" type="button" onClick={askIndexedProfile} disabled={!canAsk || asking}>
          {asking ? "Asking…" : "Ask indexed profile"}
        </button>
        {!canAsk && <p className="field-error">Index the current published profile before asking.</p>}

        {answer && (
          <div className="answer-panel">
            <h3>Answer</h3>
            <p>{answer.answer}</p>
            <p className="muted">
              {answer.status} · Snapshot v{answer.snapshot_version} · {answer.knowledge_backend}
            </p>
            <h3>Evidence</h3>
            <div className="evidence-list">
              {answer.evidence.map((item) => (
                <article className="evidence-card" key={`${item.source_type}-${item.source_id}`}>
                  <p className="eyebrow">{item.source_type}</p>
                  <h4>{item.title}</h4>
                  <p>{item.quote}</p>
                  <code>{item.source_id}</code>
                </article>
              ))}
            </div>
          </div>
        )}
      </section>
    </>
  );
}

function AccountView({ account, setAccount }: { account: AccountDetails; setAccount: React.Dispatch<React.SetStateAction<AccountDetails>> }) {
  return (
    <>
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">Settings</p>
          <h1>Account</h1>
          <p className="muted">Dummy account and subscription details for now. Billing/auth wiring comes later.</p>
        </div>
      </header>

      <section className="grid two">
        <article className="card">
          <h2>User details</h2>
          <Field label="Name" value={account.name} onChange={(value) => setAccount((current) => ({ ...current, name: value }))} />
          <Field label="Email" value={account.email} onChange={(value) => setAccount((current) => ({ ...current, email: value }))} />
          <Field label="Organization" value={account.organization} onChange={(value) => setAccount((current) => ({ ...current, organization: value }))} />
          <Field label="Timezone" value={account.timezone} onChange={(value) => setAccount((current) => ({ ...current, timezone: value }))} />
        </article>

        <article className="card">
          <h2>Subscription</h2>
          <dl className="detail-list">
            <div><dt>Plan</dt><dd>Founder Sandbox</dd></div>
            <div><dt>Status</dt><dd>Active dummy state</dd></div>
            <div><dt>Widget seats</dt><dd>1 included</dd></div>
            <div><dt>Monthly conversations</dt><dd>500 placeholder limit</dd></div>
            <div><dt>Billing</dt><dd>Stripe not connected yet</dd></div>
          </dl>
        </article>
      </section>
    </>
  );
}

function DateFields({
  prefix,
  item,
  onChange,
  errors,
}: {
  prefix: string;
  item: { start_month: NumberField; start_year: NumberField; end_month: NumberField; end_year: NumberField; is_current: boolean };
  onChange: (patch: Partial<typeof item>) => void;
  errors: Record<string, string>;
}) {
  const hasBackwardsRange = isDateRangeBackwards(item);
  return (
    <>
      <div className="grid two">
        <label className="field">
          <span>Start date</span>
          <input
            type="month"
            min="1900-01"
            value={toMonthValue(item.start_month, item.start_year)}
            onChange={(e) => {
              const patch = monthValuePatch(e.target.value);
              onChange({ start_month: patch.month, start_year: patch.year });
            }}
            aria-invalid={Boolean(errors[`${prefix}.start`])}
          />
        </label>
        <label className="field">
          <span>End date</span>
          <input
            type="month"
            min="1900-01"
            value={toMonthValue(item.end_month, item.end_year)}
            disabled={item.is_current}
            onChange={(e) => {
              const patch = monthValuePatch(e.target.value);
              onChange({ end_month: patch.month, end_year: patch.year });
            }}
            aria-invalid={Boolean(errors[`${prefix}.end`] || hasBackwardsRange)}
          />
        </label>
      </div>
      {(errors[`${prefix}.start`] || errors[`${prefix}.end`] || hasBackwardsRange) && (
        <p className="field-error">
          {errors[`${prefix}.start`] || errors[`${prefix}.end`] || "End date cannot be before start date."}
        </p>
      )}
      <label className="checkbox">
        <input type="checkbox" checked={item.is_current} onChange={(e) => onChange({ is_current: e.target.checked, end_month: "", end_year: "" })} />
        Current
      </label>
    </>
  );
}

function SectionHeading({ title, description, onAdd }: { title: string; description: string; onAdd: () => void }) {
  return (
    <section className="section-heading">
      <div>
        <h2>{title}</h2>
        <p className="muted">{description}</p>
      </div>
      <button type="button" onClick={onAdd}>Add</button>
    </section>
  );
}

function CardAddButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <div className="card-add-row">
      <button type="button" onClick={onClick}>+ {label}</button>
    </div>
  );
}

function DraggableCard({
  section,
  index,
  draggedCard,
  setDraggedCard,
  reorder,
  children,
}: {
  section: SectionName;
  index: number;
  draggedCard: { section: SectionName; index: number } | null;
  setDraggedCard: React.Dispatch<React.SetStateAction<{ section: SectionName; index: number } | null>>;
  reorder: (section: SectionName, fromIndex: number, toIndex: number) => void;
  children: React.ReactNode;
}) {
  const isDragging = draggedCard?.section === section && draggedCard.index === index;
  const canDrop = draggedCard?.section === section && draggedCard.index !== index;

  return (
    <article
      className={["card", "experience-card", isDragging ? "dragging" : "", canDrop ? "drop-target" : ""].filter(Boolean).join(" ")}
      draggable
      onDragStart={(event) => {
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", `${section}:${index}`);
        setDraggedCard({ section, index });
      }}
      onDragOver={(event) => {
        if (canDrop) {
          event.preventDefault();
          event.dataTransfer.dropEffect = "move";
        }
      }}
      onDrop={(event) => {
        event.preventDefault();
        if (draggedCard?.section === section) {
          reorder(section, draggedCard.index, index);
        }
        setDraggedCard(null);
      }}
      onDragEnd={() => setDraggedCard(null)}
    >
      {children}
    </article>
  );
}

function Toolbar({
  title,
  subtitle,
  section,
  index,
  count,
  reorder,
  remove,
  collapsed,
  onToggle,
}: {
  title: string;
  subtitle?: string;
  section: SectionName;
  index: number;
  count: number;
  reorder: (section: SectionName, fromIndex: number, toIndex: number) => void;
  remove: (section: SectionName, index: number) => void;
  collapsed: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="experience-toolbar">
      <span className="drag-handle" aria-label="Drag to reorder" title="Drag to reorder">
        <GripVertical aria-hidden="true" size={20} strokeWidth={2} />
      </span>
      <div className="tile-title">
        <strong>{title}</strong>
        {subtitle && <span>{subtitle}</span>}
      </div>
      <div className="tile-actions">
        <IconButton label={collapsed ? "Expand" : "Collapse"} onClick={onToggle}>
          {collapsed ? <ChevronDown aria-hidden="true" size={20} strokeWidth={2.2} /> : <ChevronUp aria-hidden="true" size={20} strokeWidth={2.2} />}
        </IconButton>
        <IconButton label="Remove" onClick={() => remove(section, index)} danger>
          <Trash2 aria-hidden="true" size={19} strokeWidth={2} />
        </IconButton>
      </div>
    </div>
  );
}

function IconButton({
  label,
  onClick,
  danger = false,
  children,
}: {
  label: string;
  onClick: () => void;
  danger?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button className={danger ? "icon-button danger" : "icon-button"} type="button" onClick={onClick} aria-label={label} title={label}>
      {children}
    </button>
  );
}

function Field({ label, value, error, onChange }: { label: string; value: string; error?: string; onChange: (value: string) => void }) {
  return (
    <label className="field">
      <span>{label}</span>
      <input value={value} onChange={(e) => onChange(e.target.value)} />
      {error && <em>{error}</em>}
    </label>
  );
}

function TextArea({ label, value, error, onChange }: { label: string; value: string; error?: string; onChange: (value: string) => void }) {
  return (
    <label className="field">
      <span>{label}</span>
      <textarea value={value} onChange={(e) => onChange(e.target.value)} />
      {error && <em>{error}</em>}
    </label>
  );
}

function NavButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return <button className={active ? "active nav-button" : "nav-button"} type="button" onClick={onClick}>{children}</button>;
}

function MetricCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <article className="metric-card">
      <p>{label}</p>
      <strong>{value}</strong>
      <span>{detail}</span>
    </article>
  );
}

function PreviewSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="card preview-section">
      <h2>{title}</h2>
      {React.Children.count(children) ? children : <p className="muted">No published records.</p>}
    </section>
  );
}

function PreviewItem({ title, meta, children }: { title: string; meta?: string; children: React.ReactNode }) {
  return (
    <article className="preview-item">
      <div>
        <h3>{title}</h3>
        {meta && <p className="muted">{meta}</p>}
      </div>
      {children}
    </article>
  );
}

function dateRange(item: { start_month?: NumberField | null; start_year?: NumberField | null; end_month?: NumberField | null; end_year?: NumberField | null; is_current?: boolean }) {
  const start = item.start_month && item.start_year ? `${item.start_month}/${item.start_year}` : "Unknown start";
  const end = item.is_current ? "Present" : item.end_month && item.end_year ? `${item.end_month}/${item.end_year}` : "Unknown end";
  return `${start} – ${end}`;
}
