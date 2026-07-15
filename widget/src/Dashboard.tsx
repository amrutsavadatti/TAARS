import React, { useEffect, useMemo, useState } from "react";

export interface DashboardConfig {
  apiKey: string;
  baseUrl: string;
}

interface Experience {
  id?: string;
  organization: string;
  role: string;
  start_month: number | "";
  start_year: number | "";
  end_month: number | "";
  end_year: number | "";
  is_current: boolean;
  summary: string;
  outcome: string;
  display_order: number;
}

interface ProfileDraft {
  owner_id: string;
  owner_name: string;
  experiences: Experience[];
  published_version: number | null;
  has_published_snapshot: boolean;
}

interface PublishedSnapshot {
  version: number;
  published_at: string;
  snapshot: {
    owner_name: string;
    experiences: Experience[];
  };
}

interface ApiIssue {
  field: string;
  message: string;
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

function toNullableNumber(value: number | ""): number | null {
  return value === "" ? null : Number(value);
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
  };
}

function issueMap(issues: ApiIssue[]): Record<string, string> {
  return Object.fromEntries(issues.map((issue) => [issue.field, issue.message]));
}

export function Dashboard({ config }: { config: DashboardConfig }) {
  const [profile, setProfile] = useState<ProfileDraft>({
    owner_id: "",
    owner_name: "",
    experiences: [],
    published_version: null,
    has_published_snapshot: false,
  });
  const [published, setPublished] = useState<PublishedSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [status, setStatus] = useState("");
  const [issues, setIssues] = useState<ApiIssue[]>([]);

  const errors = useMemo(() => issueMap(issues), [issues]);

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
      const draft = (await api("/api/v1/profile")) as ProfileDraft;
      setProfile({
        ...draft,
        experiences: draft.experiences.map((exp, index) => ({
          ...emptyExperience(index),
          ...exp,
          start_month: exp.start_month ?? "",
          start_year: exp.start_year ?? "",
          end_month: exp.end_month ?? "",
          end_year: exp.end_year ?? "",
          display_order: index,
        })),
      });
      try {
        setPublished((await api("/api/v1/profile/published-snapshot")) as PublishedSnapshot);
      } catch {
        setPublished(null);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadProfile();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function updateExperience(index: number, patch: Partial<Experience>) {
    setProfile((current) => ({
      ...current,
      experiences: current.experiences.map((exp, i) => (i === index ? { ...exp, ...patch } : exp)),
    }));
  }

  function reorder(index: number, direction: -1 | 1) {
    setProfile((current) => {
      const next = [...current.experiences];
      const target = index + direction;
      if (target < 0 || target >= next.length) return current;
      [next[index], next[target]] = [next[target], next[index]];
      return { ...current, experiences: next.map((exp, i) => ({ ...exp, display_order: i })) };
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
      setProfile({
        ...saved,
        experiences: saved.experiences.map((exp, index) => ({ ...emptyExperience(index), ...exp })),
      });
      setStatus("Draft saved.");
    } finally {
      setSaving(false);
    }
  }

  async function publishProfile() {
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
    } catch (err) {
      const maybeError = err as { body?: { detail?: { issues?: ApiIssue[] } } };
      const apiIssues = maybeError.body?.detail?.issues;
      if (apiIssues) {
        setIssues(apiIssues);
        setStatus("Publication blocked. Fix the highlighted fields.");
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
          <a className="active">Profile</a>
          <a aria-disabled="true">Content Gaps</a>
          <a aria-disabled="true">Conversations</a>
          <a aria-disabled="true">Quality</a>
        </nav>
      </aside>

      <section className="dashboard-main">
        <header className="dashboard-header">
          <div>
            <p className="eyebrow">Canonical profile</p>
            <h1>Experience profile</h1>
            <p className="muted">
              Published snapshots are the stable contract for future indexing backends.
            </p>
          </div>
          <div className="header-actions">
            <button onClick={saveDraft} disabled={saving || publishing} type="button">
              {saving ? "Saving…" : "Save draft"}
            </button>
            <button className="primary" onClick={publishProfile} disabled={saving || publishing} type="button">
              {publishing ? "Publishing…" : "Publish"}
            </button>
          </div>
        </header>

        {status && <div className={issues.length ? "banner error" : "banner"}>{status}</div>}

        <section className="card">
          <label className="field">
            <span>Owner name</span>
            <input
              value={profile.owner_name}
              onChange={(e) => setProfile((current) => ({ ...current, owner_name: e.target.value }))}
              placeholder="Owner name"
            />
            {errors.owner_name && <em>{errors.owner_name}</em>}
          </label>
        </section>

        <section className="section-heading">
          <div>
            <h2>Experiences</h2>
            <p className="muted">Each role is a separate canonical record, even at the same organization.</p>
          </div>
          <button
            type="button"
            onClick={() =>
              setProfile((current) => ({
                ...current,
                experiences: [...current.experiences, emptyExperience(current.experiences.length)],
              }))
            }
          >
            Add experience
          </button>
        </section>

        {profile.experiences.map((exp, index) => (
          <article className="card experience-card" key={exp.id ?? `draft-${index}`}>
            <div className="experience-toolbar">
              <strong>Experience {index + 1}</strong>
              <div>
                <button type="button" onClick={() => reorder(index, -1)} disabled={index === 0}>
                  ↑
                </button>
                <button type="button" onClick={() => reorder(index, 1)} disabled={index === profile.experiences.length - 1}>
                  ↓
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setProfile((current) => ({
                      ...current,
                      experiences: current.experiences.filter((_, i) => i !== index),
                    }))
                  }
                >
                  Remove
                </button>
              </div>
            </div>

            <div className="grid two">
              <label className="field">
                <span>Organization</span>
                <input value={exp.organization} onChange={(e) => updateExperience(index, { organization: e.target.value })} />
                {errors[`experiences.${index}.organization`] && <em>{errors[`experiences.${index}.organization`]}</em>}
              </label>
              <label className="field">
                <span>Role</span>
                <input value={exp.role} onChange={(e) => updateExperience(index, { role: e.target.value })} />
                {errors[`experiences.${index}.role`] && <em>{errors[`experiences.${index}.role`]}</em>}
              </label>
            </div>

            <div className="grid four">
              <label className="field">
                <span>Start month</span>
                <input type="number" min="1" max="12" value={exp.start_month} onChange={(e) => updateExperience(index, { start_month: e.target.value === "" ? "" : Number(e.target.value) })} />
              </label>
              <label className="field">
                <span>Start year</span>
                <input type="number" min="1900" value={exp.start_year} onChange={(e) => updateExperience(index, { start_year: e.target.value === "" ? "" : Number(e.target.value) })} />
              </label>
              <label className="field">
                <span>End month</span>
                <input type="number" min="1" max="12" value={exp.end_month} disabled={exp.is_current} onChange={(e) => updateExperience(index, { end_month: e.target.value === "" ? "" : Number(e.target.value) })} />
              </label>
              <label className="field">
                <span>End year</span>
                <input type="number" min="1900" value={exp.end_year} disabled={exp.is_current} onChange={(e) => updateExperience(index, { end_year: e.target.value === "" ? "" : Number(e.target.value) })} />
              </label>
            </div>
            {(errors[`experiences.${index}.start`] || errors[`experiences.${index}.end`]) && (
              <p className="field-error">{errors[`experiences.${index}.start`] || errors[`experiences.${index}.end`]}</p>
            )}

            <label className="checkbox">
              <input
                type="checkbox"
                checked={exp.is_current}
                onChange={(e) => updateExperience(index, { is_current: e.target.checked, end_month: "", end_year: "" })}
              />
              Current role
            </label>

            <label className="field">
              <span>Summary</span>
              <textarea value={exp.summary} onChange={(e) => updateExperience(index, { summary: e.target.value })} />
              {errors[`experiences.${index}.summary`] && <em>{errors[`experiences.${index}.summary`]}</em>}
            </label>

            <label className="field">
              <span>Required outcome</span>
              <textarea value={exp.outcome} onChange={(e) => updateExperience(index, { outcome: e.target.value })} />
              {errors[`experiences.${index}.outcome`] && <em>{errors[`experiences.${index}.outcome`]}</em>}
            </label>
          </article>
        ))}

        <section className="card snapshot">
          <h2>Published snapshot</h2>
          {published ? (
            <>
              <p className="muted">Version {published.version} · {new Date(published.published_at).toLocaleString()}</p>
              <pre>{JSON.stringify(published.snapshot, null, 2)}</pre>
            </>
          ) : (
            <p className="muted">No profile has been published yet.</p>
          )}
        </section>
      </section>
    </main>
  );
}
