import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import "./segments.css";

/* Traveller segments page: component 4, Tourist Behaviour Analytics & Segmentation (IT23366886). */

// Fixed categorical order, assigned by segment position (S1, S2, ...), never by rank.
const SEGMENT_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"];

interface Meta {
  data_source: "synthetic" | "survey";
  rows: number;
  feature_count: number;
  method: string;
  k: number;
  selection_rule: string;
  generated_at: string;
}

interface Share {
  label: string;
  share: number;
}

interface Segment {
  id: string;
  name: string;
  scope: string;
  description: string;
  size: number;
  share: number;
  typical_spend: string;
  traits: Record<string, number>;
  top_activities: Share[];
  top_transport: Share[];
  top_districts: Share[];
}

interface Trait {
  key: string;
  label: string;
  unit: string;
}

interface MethodResult {
  id: string;
  name: string;
  kind: "baseline" | "proposed";
  setting: string;
  clusters: number;
  noise_share: number;
  silhouette: number;
  davies_bouldin: number;
  calinski_harabasz: number;
  agreement_with_planted?: number;
}

interface Evaluation {
  methods: MethodResult[];
  k_sweep: { k: number; silhouette: number; davies_bouldin: number }[];
  chosen: { method: string; k: number; silhouette: number; davies_bouldin: number };
  targets: { silhouette_min: number; davies_bouldin_max: number; silhouette_met: boolean; davies_bouldin_met: boolean };
  assignment_agreement: number;
}

interface Assignment {
  segment_id: string;
  segment_name: string;
  match_strength: number;
  distances: { segment_id: string; segment_name: string; match_strength: number }[];
  agreement_with_full_model: number;
}

interface SegmentsPageProps {
  apiUrl: string;
  profile: object;
}

const percent = (value: number, digits = 0) => `${(value * 100).toFixed(digits)}%`;

function formatTrait(value: number, unit: string) {
  if (unit === "%") return percent(value);
  if (unit === "km") return `${Math.round(value)} km`;
  if (unit === "days") return `${value.toFixed(1)} days`;
  if (unit === "people") return `${value.toFixed(1)}`;
  return value.toFixed(1);
}

function SegmentsPage({ apiUrl, profile }: SegmentsPageProps) {
  const [segments, setSegments] = useState<{ meta: Meta; traits: Trait[]; segments: Segment[] } | null>(null);
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [points, setPoints] = useState<{ x: number; y: number; segment: string }[]>([]);
  const [assignment, setAssignment] = useState<Assignment | null>(null);
  const [error, setError] = useState("");
  const [assignError, setAssignError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [segmentResponse, evaluationResponse, pointResponse] = await Promise.all([
          fetch(`${apiUrl}/segments`),
          fetch(`${apiUrl}/segments/evaluation`),
          fetch(`${apiUrl}/segments/points`),
        ]);
        if (!segmentResponse.ok) {
          const data = await segmentResponse.json().catch(() => ({}));
          throw new Error(data.detail || "Traveller segments could not be loaded.");
        }
        const [segmentData, evaluationData, pointData] = await Promise.all([
          segmentResponse.json(), evaluationResponse.json(), pointResponse.json(),
        ]);
        if (cancelled) return;
        setSegments(segmentData);
        setEvaluation(evaluationData);
        setPoints(pointData.points);
      } catch (loadError) {
        if (!cancelled) setError(loadError instanceof Error ? loadError.message : "Traveller segments could not be loaded.");
      }
    }
    void load();
    return () => { cancelled = true; };
  }, [apiUrl]);

  const profileKey = JSON.stringify(profile);
  useEffect(() => {
    let cancelled = false;
    async function assign() {
      try {
        const response = await fetch(`${apiUrl}/segments/assign`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: profileKey,
        });
        const data = await response.json();
        if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Your profile could not be matched.");
        if (!cancelled) { setAssignment(data); setAssignError(""); }
      } catch (assignFailure) {
        if (!cancelled) setAssignError(assignFailure instanceof Error ? assignFailure.message : "Your profile could not be matched.");
      }
    }
    void assign();
    return () => { cancelled = true; };
  }, [apiUrl, profileKey]);

  const colorOf = useMemo(() => {
    const ids = segments?.segments.map((s) => s.id) ?? [];
    return (id: string) => SEGMENT_COLORS[Math.max(0, ids.indexOf(id)) % SEGMENT_COLORS.length];
  }, [segments]);

  if (error) {
    return (
      <div className="page-content">
        <div className="segments-notice error" role="alert"><strong>Segments unavailable</strong>{error}</div>
      </div>
    );
  }
  if (!segments || !evaluation) {
    return <div className="page-content"><p className="segments-loading">Loading traveller segments…</p></div>;
  }

  const { meta, traits } = segments;
  const synthetic = meta.data_source === "synthetic";
  const showPlanted = synthetic && evaluation.methods.some((m) => m.agreement_with_planted !== undefined);
  const yourSegment = segments.segments.find((s) => s.id === assignment?.segment_id);

  return (
    <div className="page-content segments-page">
      <div className="page-header">
        <div>
          <span className="eyebrow">TRAVELLER BEHAVIOUR ANALYTICS</span>
          <h1>Traveller segments</h1>
          <p>
            Groups of travellers discovered from how they actually travel: trip length, spending, the places they
            visit, what they do and what matters to them, rather than age or nationality.
          </p>
        </div>
      </div>

      {synthetic && (
        <div className="segments-notice" role="note">
          <strong>Test data</strong>
          These segments come from {meta.rows} synthetic survey responses generated to test the method. They show how
          the system works and are not findings about real tourists. Real survey responses will replace them.
        </div>
      )}

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-card-icon">◎</div>
          <span>Segments found</span>
          <strong>{meta.k}</strong>
          <small>{meta.method}, chosen by Silhouette score</small>
        </div>
        <div className="stat-card">
          <div className="stat-card-icon">✎</div>
          <span>Survey responses</span>
          <strong>{meta.rows}</strong>
          <small>{synthetic ? "Synthetic test responses" : "Real survey responses"}</small>
        </div>
        <div className="stat-card">
          <div className="stat-card-icon">▦</div>
          <span>Behaviour features</span>
          <strong>{meta.feature_count}</strong>
          <small>Trip, spending, mobility, activity and value answers</small>
        </div>
        <div className="stat-card">
          <div className="stat-card-icon">✓</div>
          <span>Silhouette score</span>
          <strong>{evaluation.chosen.silhouette.toFixed(2)}</strong>
          <small>Proposal target {evaluation.targets.silhouette_min.toFixed(2)}</small>
        </div>
      </div>

      <section className="dashboard-section segments-you">
        <div className="section-heading">
          <div>
            <span className="eyebrow">WHERE YOU FIT</span>
            <h2>Your closest traveller segment</h2>
          </div>
        </div>
        {assignError && <p className="segments-muted">{assignError}</p>}
        {assignment && yourSegment && (
          <div className="segments-you-body">
            <div className="segments-you-main">
              <span className="segments-dot large" style={{ background: colorOf(yourSegment.id) }} aria-hidden="true" />
              <div>
                <strong>{yourSegment.name}</strong>
                <p>{yourSegment.description}</p>
              </div>
            </div>
            <div className="segments-you-strength" aria-label="Match strength for each segment">
              {assignment.distances.map((row) => (
                <div className="segments-bar-row" key={row.segment_id}>
                  <span>{row.segment_id} · {row.segment_name}</span>
                  <div className="segments-bar-track">
                    <div className="segments-bar" style={{ width: percent(row.match_strength), background: colorOf(row.segment_id) }} />
                  </div>
                  <b>{percent(row.match_strength)}</b>
                </div>
              ))}
            </div>
            <p className="segments-muted">
              Based on the 12 answers your Traveler Profile shares with the survey: trip length, daily budget,
              interests, travel style, crowd preference, sustainability and pace. Matching on these answers alone
              places survey respondents in the same segment as the full model {percent(assignment.agreement_with_full_model)} of the time.
            </p>
          </div>
        )}
      </section>

      <section className="dashboard-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">THE SEGMENTS</span>
            <h2>{meta.k} kinds of traveller</h2>
          </div>
        </div>
        <div className="segments-cards">
          {segments.segments.map((segment) => (
            <article className="segments-card" key={segment.id} style={{ borderTopColor: colorOf(segment.id) }}>
              <div className="segments-card-top">
                <span className="segments-dot" style={{ background: colorOf(segment.id) }} aria-hidden="true" />
                <span className="segments-id">{segment.id}</span>
                <span className="segments-share">{percent(segment.share)} of travellers · {segment.size} responses</span>
              </div>
              <h3>{segment.name}</h3>
              <p>{segment.description}</p>
              <dl className="segments-facts">
                <div><dt>Trip length</dt><dd>{segment.traits.trip_days.toFixed(1)} days</dd></div>
                <div><dt>Daily spend</dt><dd>{segment.typical_spend}</dd></div>
                <div><dt>Districts</dt><dd>{segment.traits.districts_visited.toFixed(1)}</dd></div>
                <div><dt>From overseas</dt><dd>{percent(segment.traits.overseas_share)}</dd></div>
              </dl>
              <div className="segments-chips">
                {segment.top_activities.map((activity) => (
                  <span key={activity.label}>{activity.label} · {percent(activity.share)}</span>
                ))}
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="dashboard-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">COMPARISON</span>
            <h2>How the segments differ</h2>
          </div>
        </div>
        <div className="segments-legend" aria-hidden="true">
          {segments.segments.map((s) => (
            <span key={s.id}><i style={{ background: colorOf(s.id) }} />{s.id} · {s.name}</span>
          ))}
        </div>
        <div className="segments-compare">
          {traits.map((trait) => {
            const max = Math.max(...segments.segments.map((s) => s.traits[trait.key]), 0.0001);
            return (
              <div className="segments-compare-row" key={trait.key}>
                <span className="segments-compare-label">{trait.label}</span>
                <div className="segments-compare-bars">
                  {segments.segments.map((s) => (
                    <div className="segments-bar-row compact" key={s.id} title={`${s.name}: ${formatTrait(s.traits[trait.key], trait.unit)}`}>
                      <span className="segments-visually-hidden">{s.name}</span>
                      <div className="segments-bar-track">
                        <div className="segments-bar" style={{ width: `${(s.traits[trait.key] / max) * 100}%`, background: colorOf(s.id) }} />
                      </div>
                      <b>{formatTrait(s.traits[trait.key], trait.unit)}</b>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="dashboard-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">MAP OF RESPONSES</span>
            <h2>The segments in two dimensions</h2>
          </div>
        </div>
        <p className="segments-muted">
          Each dot is one survey response. The {meta.feature_count} behaviour features are flattened to two dimensions
          with principal component analysis (PCA), so dots close together describe similar trips.
        </p>
        <div className="segments-chart">
          <ResponsiveContainer width="100%" height={360}>
            <ScatterChart margin={{ top: 10, right: 16, bottom: 8, left: 0 }}>
              <CartesianGrid stroke="#e1e0d9" />
              <XAxis type="number" dataKey="x" name="Component 1" tick={{ fontSize: 12, fill: "#52514e" }} stroke="#c3c2b7" />
              <YAxis type="number" dataKey="y" name="Component 2" tick={{ fontSize: 12, fill: "#52514e" }} stroke="#c3c2b7" />
              <Tooltip cursor={{ strokeDasharray: "0" }} formatter={(value) => Number(value).toFixed(2)} />
              <Legend />
              {segments.segments.map((s) => (
                <Scatter key={s.id} name={`${s.id} · ${s.name}`} data={points.filter((p) => p.segment === s.id)}
                  fill={colorOf(s.id)} fillOpacity={0.85} stroke="#fcfcfb" strokeWidth={1} />
              ))}
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="dashboard-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">RESEARCH RESULTS</span>
            <h2>Comparing the clustering methods</h2>
          </div>
        </div>
        <p className="segments-muted">
          The proposed behaviour-based methods are compared with the two baselines from the proposal. Silhouette
          (higher is better) and Davies–Bouldin (lower is better) measure how tight and separate the groups are.
        </p>
        <div className="segments-table-wrap">
          <table className="segments-table">
            <thead>
              <tr>
                <th>Method</th><th>Type</th><th>Setting</th><th>Groups</th><th>Silhouette</th><th>Davies–Bouldin</th><th>Calinski–Harabasz</th>
                {showPlanted && <th title="Adjusted Rand index against the planted test groups">Planted match</th>}
              </tr>
            </thead>
            <tbody>
              {evaluation.methods.map((method) => (
                <tr key={method.id} className={method.id === "kmeans" ? "chosen" : ""}>
                  <td>{method.name}{method.id === "kmeans" && <em> (used)</em>}</td>
                  <td>{method.kind === "baseline" ? "Baseline" : "Proposed"}</td>
                  <td>{method.setting}{method.noise_share > 0 && ` · ${percent(method.noise_share)} noise`}</td>
                  <td>{method.clusters}</td>
                  <td>{method.silhouette.toFixed(3)}</td>
                  <td>{method.davies_bouldin.toFixed(2)}</td>
                  <td>{method.calinski_harabasz.toFixed(0)}</td>
                  {showPlanted && <td>{method.agreement_with_planted?.toFixed(2)}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="segments-targets">
          <div className={evaluation.targets.silhouette_met ? "met" : "unmet"}>
            <span aria-hidden="true">{evaluation.targets.silhouette_met ? "✓" : "!"}</span>
            Silhouette {evaluation.chosen.silhouette.toFixed(2)} against the proposal target of at least {evaluation.targets.silhouette_min.toFixed(2)}:
            <b> {evaluation.targets.silhouette_met ? "met" : "not met"}</b>
          </div>
          <div className={evaluation.targets.davies_bouldin_met ? "met" : "unmet"}>
            <span aria-hidden="true">{evaluation.targets.davies_bouldin_met ? "✓" : "!"}</span>
            Davies–Bouldin {evaluation.chosen.davies_bouldin.toFixed(2)} against the proposal target of at most {evaluation.targets.davies_bouldin_max.toFixed(2)}:
            <b> {evaluation.targets.davies_bouldin_met ? "met" : "not met"}</b>
          </div>
        </div>

        <h3 className="segments-subheading">Silhouette score by number of K-Means groups</h3>
        <div className="segments-chart small">
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={evaluation.k_sweep} margin={{ top: 16, right: 20, bottom: 8, left: 0 }}>
              <CartesianGrid stroke="#e1e0d9" vertical={false} />
              <XAxis dataKey="k" tick={{ fontSize: 12, fill: "#52514e" }} stroke="#c3c2b7"
                label={{ value: "Number of groups (k)", position: "insideBottom", offset: -4, fontSize: 12, fill: "#52514e" }} height={42} />
              <YAxis tick={{ fontSize: 12, fill: "#52514e" }} stroke="#c3c2b7" domain={[0, "auto"]} tickCount={5} tickFormatter={(value) => Number(value).toFixed(2)} />
              <Tooltip formatter={(value) => Number(value).toFixed(3)} labelFormatter={(k) => `k = ${k}`} />
              <Line type="monotone" dataKey="silhouette" name="Silhouette" stroke="#2a78d6" strokeWidth={2}
                dot={{ r: 4, fill: "#2a78d6", stroke: "#fcfcfb", strokeWidth: 2 }} activeDot={{ r: 6 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <p className="segments-muted">
          {meta.selection_rule}. Generated {new Date(meta.generated_at).toLocaleString()} from {meta.rows} {synthetic ? "synthetic" : "survey"} responses.
        </p>
      </section>
    </div>
  );
}

export default SegmentsPage;
