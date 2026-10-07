import { useEffect, useMemo, useState } from "react";

const API_URL = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

type Page =
  | "dashboard"
  | "recommendations"
  | "saved"
  | "profile"
  | "itinerary"
  | "account"
  | "crowd"
  | "weather"
  | "analytics"
  | "evaluation"
  | "assistant";

interface Recommendation {
  rank: number;
  destination_id: string;
  name: string;
  category: string;
  district: string;
  distance_km: number | null;
  duration_hours?: number | null;
  estimated_cost_lkr: number | null;
  sustainability_score: number | null;
  seasonality_score: number | null;
  weather_temp_c: number | null;
  weather_rain_risk: number | null;
  weather_suitability: number | null;
  predicted_crowd_score: number | null;
  predicted_crowd_level: string | null;
  preference_score: number | null;
  budget_fit: number | null;
  predicted_crowd_fit: number | null;
  weather_fit: number | null;
  sustainability_fit: number | null;
  distance_fit: number | null;
  pace_fit: number | null;
  sentiment_fit: number | null;
  demand_suitability: number | null;
  demand_aware_score: number | null;
  scenario_score?: number | null;
  explanation: string | null;
}

interface RecommendationsResponse {
  user_id: string;
  recommendations: Recommendation[];
}

interface UsersResponse {
  users: string[];
}

interface AuthSession {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  account: { id: number; email: string };
}

interface AccountProfileSummary {
  user_id: string;
  name: string;
}

interface ProfileData {
  name: string;
  sustainabilityImportance: number;
  budget: string;
  tripDuration: string;
  travelStyle: string;
  startingLocation: string;
  interests: string;
  maxDistanceKm: string;
  travelPace: string;
  preferredCrowd: string;
  preferredWeather: string;
}

/* =========================================================
   EVALUATION TYPES
========================================================= */

interface EvaluationModel {
  id: string;
  name: string;
  precision_at_5: number;
  recall_at_5: number;
  ndcg_at_5: number;
}

interface NdcgPoint {
  k: number;
  b5_ndcg: number;
  demand_aware_ndcg: number;
  ndcg_change: number;
}

interface DemandAwareStatistics {
  total_recommendations: number;
  unique_users: number;
  unique_destinations: number;
  mean_sbert_hybrid_score: number;
  mean_predicted_crowd_score: number;
  mean_crowd_suitability: number;
  mean_demand_aware_score: number;
  changed_rankings: number;
  unchanged_rankings: number;
}

interface EvaluationResponse {
  models: EvaluationModel[];
  ndcg_by_k: NdcgPoint[];
  demand_aware_statistics: DemandAwareStatistics;
}

/* =========================================================
   DEFAULT PROFILE
========================================================= */

const defaultProfile: ProfileData = {
  name: "",
  sustainabilityImportance: 0.5,
  budget: "10000",
  tripDuration: "3",
  travelStyle: "Nature & Adventure",
  startingLocation: "Colombo",
  interests: "Nature, Hiking, Wildlife",
  maxDistanceKm: "Any distance",
  travelPace: "Balanced",
  preferredCrowd: "Low",
  preferredWeather: "Sunny",
};

/* =========================================================
   GENERAL HELPERS
========================================================= */

function formatCurrency(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "N/A";
  }

  return `LKR ${Math.round(value).toLocaleString()}`;
}

function formatNumber(value: number | null | undefined, decimals = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "N/A";
  }

  return value.toFixed(decimals);
}

function scorePercent(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return 0;
  }

  return Math.max(0, Math.min(100, value * 100));
}

function getScoreLabel(value: number | null | undefined) {
  const score = scorePercent(value);

  if (score >= 80) return "Excellent Match";
  if (score >= 65) return "Strong Match";
  if (score >= 50) return "Good Match";
  if (score >= 35) return "Moderate Match";

  return "Low Match";
}

function getCrowdClass(level: string | null | undefined) {
  const normalized = String(level || "").toLowerCase();

  if (normalized.includes("low")) return "low";
  if (normalized.includes("medium")) return "medium";
  if (normalized.includes("high")) return "high";

  return "medium";
}

function getWeatherClass(value: number | null | undefined) {
  const score = scorePercent(value);

  if (score >= 75) return "good";
  if (score >= 50) return "moderate";

  return "poor";
}

interface ItineraryStop {
  destination_id: string;
  name: string;
  district: string;
  rank: number;
  estimated_cost_lkr: number | null;
  visit_duration_hours: number;
  straight_line_distance_km: number | null;
  recommendation_reason: string;
}

interface ItineraryDay {
  day: number;
  area: string;
  estimated_visit_hours: number;
  stops: ItineraryStop[];
}

interface ItineraryResponse {
  user_id: string;
  traveler_name: string;
  days: ItineraryDay[];
  planning_note: string;
}

function escapeHtml(value: string) {
  return value.replace(/[&<>"']/g, (character) => {
    const entities: Record<string, string> = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };
    return entities[character];
  });
}

function downloadHtmlReport(filename: string, html: string) {
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function downloadPdfReport(filename: string, lines: string[]) {
  const encoder = new TextEncoder();
  const clean = (value: string) => value.normalize("NFKD").replace(/[^\x20-\x7E]/g, "?");
  const wrapped = lines.flatMap((line) => {
    const words = clean(line).split(/\s+/);
    const rows: string[] = [];
    let row = "";
    words.forEach((word) => {
      if (row && `${row} ${word}`.length > 88) { rows.push(row); row = word; }
      else row = row ? `${row} ${word}` : word;
    });
    rows.push(row);
    return rows;
  });
  const pageLines = Array.from({ length: Math.ceil(wrapped.length / 46) || 1 }, (_, page) => wrapped.slice(page * 46, (page + 1) * 46));
  const fontId = 3 + pageLines.length * 2;
  const objects: string[] = [];
  objects[1] = "<< /Type /Catalog /Pages 2 0 R >>";
  objects[2] = `<< /Type /Pages /Kids [${pageLines.map((_, index) => `${3 + index * 2} 0 R`).join(" ")}] /Count ${pageLines.length} >>`;
  pageLines.forEach((page, index) => {
    const pageId = 3 + index * 2;
    const streamId = pageId + 1;
    const content = page.map((line, lineIndex) => `BT /F1 10 Tf 48 ${744 - lineIndex * 15} Td (${line.replace(/[\\()]/g, "\\$&")}) Tj ET`).join("\n");
    objects[pageId] = `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 ${fontId} 0 R >> >> /Contents ${streamId} 0 R >>`;
    objects[streamId] = `<< /Length ${encoder.encode(content).length} >>\nstream\n${content}\nendstream`;
  });
  objects[fontId] = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>";
  let pdf = "%PDF-1.4\n%TravelMind\n";
  const offsets = [0];
  for (let id = 1; id < objects.length; id += 1) {
    offsets[id] = encoder.encode(pdf).length;
    pdf += `${id} 0 obj\n${objects[id]}\nendobj\n`;
  }
  const xrefOffset = encoder.encode(pdf).length;
  pdf += `xref\n0 ${objects.length}\n0000000000 65535 f \n`;
  for (let id = 1; id < objects.length; id += 1) pdf += `${String(offsets[id]).padStart(10, "0")} 00000 n \n`;
  pdf += `trailer\n<< /Size ${objects.length} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF`;
  const url = URL.createObjectURL(new Blob([encoder.encode(pdf)], { type: "application/pdf" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

interface AssistantSource {
  id: string;
  title: string;
  details: string;
}

interface AssistantMessage {
  role: "user" | "assistant";
  content: string;
  sources?: AssistantSource[];
  latencyMs?: number;
}

interface AssistantResponse {
  answer: string;
  sources: AssistantSource[];
  latency_ms: number;
  model: string;
}

function AppIcon({ name }: { name: string }) {
  const paths: Record<string, string> = {
    dashboard: "M3 3h8v8H3z M13 3h8v5h-8z M13 10h8v11h-8z M3 13h8v8H3z",
    compass: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20Z m4.2-14.2-2.8 6.4-6.4 2.8 2.8-6.4 6.4-2.8Z",
    user: "M20 21a8 8 0 0 0-16 0 M12 13a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z",
    heart: "M20.8 8.7c0 5.2-8.8 10.3-8.8 10.3S3.2 13.9 3.2 8.7a4.7 4.7 0 0 1 8.8-2.2 4.7 4.7 0 0 1 8.8 2.2Z",
    people: "M16 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2 M10 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z M20 21v-2a4 4 0 0 0-3-3.87 M16 3.13a4 4 0 0 1 0 7.75",
    sun: "M12 3v2 M12 19v2 M4.2 4.2l1.4 1.4 M18.4 18.4l1.4 1.4 M3 12h2 M19 12h2 M4.2 19.8l1.4-1.4 M18.4 5.6l1.4-1.4 M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z",
    chart: "M3 3v18h18 M19 9l-5 5-4-4-5 5",
    award: "m12 15-2 2-4-1 1-4-3-3 4-1 2-4 2 4 4 1-3 3 1 4-4 1-2-2Z M8 15v6l4-2 4 2v-6",
    sparkle: "m12 3 1.9 5.8L20 11l-6.1 2.2L12 19l-1.9-5.8L4 11l6.1-2.2L12 3Z M19 14l1 2.5 2 1-2 1-1 2.5-1-2.5-2-1 2-1 1-2.5Z",
    leaf: "M20 4C12 4 6 7 6 14a6 6 0 0 0 6 6c7 0 10-6 8-16Z M5 21c2-5 6-8 11-11",
    pin: "M20 10c0 5-8 12-8 12S4 15 4 10a8 8 0 1 1 16 0Z M12 10a2 2 0 1 0 0 .01",
  };

  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d={paths[name] || paths.sparkle} />
    </svg>
  );
}

function getDestinationImage(category: string | null | undefined) {
  const normalized = String(category || "").toLowerCase();
  if (normalized.includes("beach") || normalized.includes("coast") || normalized.includes("sea")) {
    return "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1100&q=82";
  }
  if (normalized.includes("mountain") || normalized.includes("hill") || normalized.includes("hiking")) {
    return "https://images.unsplash.com/photo-1470770841072-f978cf4d019e?auto=format&fit=crop&w=1100&q=82";
  }
  if (normalized.includes("waterfall") || normalized.includes("river") || normalized.includes("water")) {
    return "https://images.unsplash.com/photo-1433086966358-54859d0ed716?auto=format&fit=crop&w=1100&q=82";
  }
  if (normalized.includes("wildlife") || normalized.includes("safari") || normalized.includes("national park")) {
    return "https://images.unsplash.com/photo-1516026672322-bc52d61a55d5?auto=format&fit=crop&w=1100&q=82";
  }
  if (normalized.includes("heritage") || normalized.includes("historical") || normalized.includes("cultural")) {
    return "https://images.unsplash.com/photo-1548013146-72479768bada?auto=format&fit=crop&w=1100&q=82";
  }
  if (normalized.includes("forest") || normalized.includes("nature")) {
    return "https://images.unsplash.com/photo-1448375240586-882707db888b?auto=format&fit=crop&w=1100&q=82";
  }
  return "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1100&q=82";
}

function getDestinationVisual(category: string | null | undefined) {
  const normalized = String(category || "").toLowerCase();

  if (
    normalized.includes("beach") ||
    normalized.includes("coast") ||
    normalized.includes("sea")
  ) {
    return {
      emoji: "🏖️",
      gradient: "linear-gradient(135deg, #dff5ff 0%, #bde7f7 100%)",
    };
  }

  if (
    normalized.includes("mountain") ||
    normalized.includes("hill") ||
    normalized.includes("hiking")
  ) {
    return {
      emoji: "🏔️",
      gradient: "linear-gradient(135deg, #e4f2e7 0%, #b9d8bf 100%)",
    };
  }

  if (
    normalized.includes("waterfall") ||
    normalized.includes("river") ||
    normalized.includes("water")
  ) {
    return {
      emoji: "💧",
      gradient: "linear-gradient(135deg, #e3f6ff 0%, #b7e2f4 100%)",
    };
  }

  if (
    normalized.includes("wildlife") ||
    normalized.includes("safari") ||
    normalized.includes("national park")
  ) {
    return {
      emoji: "🦌",
      gradient: "linear-gradient(135deg, #edf6df 0%, #cde4b2 100%)",
    };
  }

  if (
    normalized.includes("heritage") ||
    normalized.includes("historical") ||
    normalized.includes("cultural")
  ) {
    return {
      emoji: "🏛️",
      gradient: "linear-gradient(135deg, #f7eddc 0%, #ead5ae 100%)",
    };
  }

  if (
    normalized.includes("forest") ||
    normalized.includes("nature")
  ) {
    return {
      emoji: "🌿",
      gradient: "linear-gradient(135deg, #e4f5e7 0%, #c2e2c9 100%)",
    };
  }

  return {
    emoji: "📍",
    gradient: "linear-gradient(135deg, #edf2f7 0%, #dce6ef 100%)",
  };
}

function buildDetailedExplanation(
  recommendation: Recommendation,
  profile: ProfileData,
) {
  const factors: string[] = [];
  const considerations: string[] = [];

  const preference = scorePercent(recommendation.preference_score);
  const budget = scorePercent(recommendation.budget_fit);
  const crowd = scorePercent(recommendation.predicted_crowd_fit);
  const weather = scorePercent(recommendation.weather_fit);
  const sustainability = scorePercent(
    recommendation.sustainability_fit,
  );

  if (preference >= 65) {
    factors.push(
      `matches your ${profile.travelStyle.toLowerCase()} travel style and selected interests`,
    );
  }

  if (budget >= 65) {
    factors.push("fits well within your selected travel budget");
  }

  if (crowd >= 65) {
    factors.push(
      `aligns with your preference for ${profile.preferredCrowd.toLowerCase()} crowd levels`,
    );
  }

  if (weather >= 65) {
    factors.push(
      `has good suitability for your preferred ${profile.preferredWeather.toLowerCase()} weather`,
    );
  }

  if (sustainability >= 65) {
    factors.push("has a strong sustainability profile");
  }

  if (preference < 45) considerations.push("preference fit is lower than for your strongest matches");
  if (budget < 45) considerations.push("the estimated cost may stretch your selected budget");
  if (crowd < 45) considerations.push(`the crowd estimate is less aligned with your ${profile.preferredCrowd.toLowerCase()}-crowd preference`);
  if (weather < 45) considerations.push(`weather fit is limited for your preferred ${profile.preferredWeather.toLowerCase()} conditions`);
  if (sustainability < 40) considerations.push("the available sustainability score is comparatively low");

  if (factors.length === 0 && considerations.length === 0) {
    return (
      recommendation.explanation ||
      "This destination was selected using multiple recommendation and demand-aware signals."
    );
  }

  const positiveSummary = factors.length
    ? `This destination is recommended because it ${factors.join(", ")}.`
    : "This destination remains in your ranked results based on its overall combination of signals.";
  return considerations.length
    ? `${positiveSummary} Things to consider: ${considerations.join("; ")}.`
    : positiveSummary;
}

/* =========================================================
   SMALL UI COMPONENTS
========================================================= */

function ScoreCircle({
  value,
  size = 84,
}: {
  value: number | null | undefined;
  size?: number;
}) {
  const percent = scorePercent(value);

  return (
    <div
      className="score-circle"
      style={{
        width: size,
        height: size,
        background: `conic-gradient(var(--brand-teal) ${percent}%, #e6edf0 ${percent}% 100%)`,
      }}
    >
      <div className="score-circle-inner">
        <strong>{Math.round(percent)}%</strong>
        <span>match</span>
      </div>
    </div>
  );
}

function FactorBar({
  label,
  value,
}: {
  label: string;
  value: number | null | undefined;
}) {
  const percent = scorePercent(value);

  return (
    <div className="factor-row">
      <div className="factor-label">
        <span>{label}</span>
        <strong>{Math.round(percent)}%</strong>
      </div>

      <div className="factor-track">
        <div
          className="factor-fill"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

function DestinationVisual({
  recommendation,
  large = false,
}: {
  recommendation: Recommendation;
  large?: boolean;
}) {
  const visual = getDestinationVisual(recommendation.category);

  return (
    <div
      className={`destination-visual ${
        large ? "destination-visual-large" : ""
      }`}
      style={{ background: visual.gradient }}
    >
      <img
        className="destination-photo"
        src={getDestinationImage(recommendation.category)}
        alt={`${recommendation.name} destination scenery`}
        loading="lazy"
        onError={(event) => {
          event.currentTarget.style.display = "none";
        }}
      />
      <span className="destination-photo-caption">
        <AppIcon name="pin" />
        {recommendation.district}
      </span>
    </div>
  );
}

function BreakdownItem({
  label,
  value,
}: {
  label: string;
  value: number | null | undefined;
}) {
  const percent = scorePercent(value);

  return (
    <div className="breakdown-item">
      <div className="breakdown-item-top">
        <span>{label}</span>
        <strong>{Math.round(percent)}%</strong>
      </div>

      <div className="breakdown-track">
        <div
          className="breakdown-fill"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

function RecommendationModal({
  recommendation,
  profile,
  onClose,
}: {
  recommendation: Recommendation;
  profile: ProfileData;
  onClose: () => void;
}) {
  const detailedExplanation = buildDetailedExplanation(
    recommendation,
    profile,
  );

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="recommendation-modal"
        onClick={(event) => event.stopPropagation()}
      >
        <button
          className="modal-close"
          onClick={onClose}
          aria-label="Close recommendation details"
        >
          ×
        </button>

        <div className="modal-hero">
          <DestinationVisual
            recommendation={recommendation}
            large
          />

          <div className="modal-hero-content">
            <div className="modal-rank">
              AI Rank #{recommendation.rank}
            </div>

            <h2>{recommendation.name}</h2>

            <p>
              {recommendation.category} ·{" "}
              {recommendation.district}
            </p>

            <div className="modal-score-row">
              <ScoreCircle
                value={recommendation.demand_aware_score}
                size={100}
              />

              <div>
                <span className="eyebrow">DEMAND-AWARE SCORE</span>
                <h3>
                  {getScoreLabel(
                    recommendation.demand_aware_score,
                  )}
                </h3>
                <p>
                  {Math.round(
                    scorePercent(
                      recommendation.demand_aware_score,
                    ),
                  )}
                  % overall match
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="modal-stat-grid">
          <div className="modal-stat">
            <span>Distance from start (straight line)</span>
            <strong>
              {recommendation.distance_km == null
                ? "N/A"
                : `~${Math.round(recommendation.distance_km)} km`}
            </strong>
          </div>

          <div className="modal-stat">
            <span>Estimated Cost</span>
            <strong>
              {formatCurrency(
                recommendation.estimated_cost_lkr,
              )}
            </strong>
          </div>

          <div className="modal-stat">
            <span>Predicted Crowd</span>
            <strong>
              {formatNumber(
                recommendation.predicted_crowd_score,
                1,
              )}
            </strong>
          </div>

          <div className="modal-stat">
            <span>Crowd Level</span>
            <strong>
              {recommendation.predicted_crowd_level || "N/A"}
            </strong>
          </div>

          <div className="modal-stat">
            <span>Temperature</span>
            <strong>
              {recommendation.weather_temp_c !== null
                ? `${formatNumber(
                    recommendation.weather_temp_c,
                    1,
                  )}°C`
                : "N/A"}
            </strong>
          </div>
        </div>

        <div className="modal-section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">EXPLAINABLE AI</span>
              <h3>Why this destination?</h3>
            </div>
          </div>

          <div className="explanation-box">
            <div className="explanation-icon">✦</div>

            <div>
              <p>{detailedExplanation}</p>

              {recommendation.explanation &&
                recommendation.explanation !==
                  detailedExplanation && (
                  <p className="secondary-explanation">
                    {recommendation.explanation}
                  </p>
                )}
            </div>
          </div>
        </div>

        <div className="modal-section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">MODEL BREAKDOWN</span>
              <h3>Recommendation factors</h3>
            </div>
          </div>

          <div className="breakdown-grid">
            <BreakdownItem
              label="Preference Match"
              value={recommendation.preference_score}
            />

            <BreakdownItem
              label="Budget Fit"
              value={recommendation.budget_fit}
            />

            <BreakdownItem
              label="Crowd Suitability"
              value={recommendation.predicted_crowd_fit}
            />

            <BreakdownItem
              label="Weather Fit"
              value={recommendation.weather_fit}
            />

            <BreakdownItem
              label="Sustainability"
              value={recommendation.sustainability_fit}
            />

            <BreakdownItem
              label="Distance Fit"
              value={recommendation.distance_fit}
            />

            <BreakdownItem
              label="Travel Pace"
              value={recommendation.pace_fit}
            />

            <BreakdownItem
              label="Sentiment Fit"
              value={recommendation.sentiment_fit}
            />

            <BreakdownItem
              label="Demand Suitability"
              value={recommendation.demand_suitability}
            />
          </div>
        </div>

        <div className="modal-section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">SIGNAL ANALYSIS</span>
              <h3>AI factor scores</h3>
            </div>
          </div>

          <div className="factor-list">
            <FactorBar
              label="Preference"
              value={recommendation.preference_score}
            />

            <FactorBar
              label="Budget"
              value={recommendation.budget_fit}
            />

            <FactorBar
              label="Crowd"
              value={recommendation.predicted_crowd_fit}
            />

            <FactorBar
              label="Weather"
              value={recommendation.weather_fit}
            />

            <FactorBar
              label="Sustainability"
              value={recommendation.sustainability_fit}
            />

            <FactorBar
              label="Sentiment"
              value={recommendation.sentiment_fit}
            />

            <FactorBar
              label="Demand"
              value={recommendation.demand_suitability}
            />
          </div>
        </div>

        <div className="modal-footer">
          <div>
            <span className="eyebrow">DESTINATION ID</span>
            <strong>{recommendation.destination_id}</strong>
          </div>

          <button
            className="primary-button"
            onClick={onClose}
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}

/* =========================================================
   APP
========================================================= */

function App() {
  const [page, setPage] =
    useState<Page>("dashboard");

  const [users, setUsers] = useState<string[]>([]);
  const [selectedUser, setSelectedUser] =
    useState("U001");

  const [authSession, setAuthSession] = useState<AuthSession | null>(() => {
    try {
      const stored = window.sessionStorage.getItem("travelmind.auth");
      return stored ? JSON.parse(stored) as AuthSession : null;
    } catch {
      return null;
    }
  });
  const [authMode, setAuthMode] = useState<"login" | "register">("register");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authLoading, setAuthLoading] = useState(false);
  const [authMessage, setAuthMessage] = useState("");
  const [accountProfiles, setAccountProfiles] = useState<AccountProfileSummary[]>([]);

  const [recommendations, setRecommendations] =
    useState<Recommendation[]>([]);
  const [scenarioRecommendations, setScenarioRecommendations] = useState<Recommendation[]>([]);
  const [scenarioRankingLoading, setScenarioRankingLoading] = useState(false);
  const [scenarioRankingError, setScenarioRankingError] = useState("");

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState("");

  const [
    selectedRecommendation,
    setSelectedRecommendation,
  ] = useState<Recommendation | null>(null);

  const [profile, setProfile] =
    useState<ProfileData>(defaultProfile);

  const [profileSaved, setProfileSaved] =
    useState(false);
  const [profileMessage, setProfileMessage] =
    useState("");

  const [searchTerm, setSearchTerm] =
    useState("");

  const [categoryFilter, setCategoryFilter] =
    useState("All");

  const [crowdFilter, setCrowdFilter] =
    useState("All");

  const [sortBy, setSortBy] =
    useState("rank");

  const [
    showOnlyStrongMatches,
    setShowOnlyStrongMatches,
  ] = useState(false);
  const [recommendationLens, setRecommendationLens] = useState<"balanced" | "crowd" | "weather" | "sustainability" | "scenario">("balanced");
  const [recommendationView, setRecommendationView] = useState<"grid" | "map">("grid");
  const [savedDestinationIds, setSavedDestinationIds] = useState<string[]>([]);
  const [scenarioWeights, setScenarioWeights] = useState({ preference: 60, crowd: 25, sustainability: 15 });
  const [comparisonIds, setComparisonIds] = useState<string[]>([]);
  const [preferenceFeedback, setPreferenceFeedback] = useState<Record<string, number>>({});
  const [feedbackNotice, setFeedbackNotice] = useState("");
  const [crowdDisplayFilter, setCrowdDisplayFilter] = useState("All");
  const [weatherScenario, setWeatherScenario] = useState<"profile" | "sunny" | "rainy" | "cloudy" | "cool">("profile");

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(`travelmind.saved.${selectedUser}`);
      const parsed: unknown = stored ? JSON.parse(stored) : [];
      setSavedDestinationIds(Array.isArray(parsed) ? parsed.filter((id): id is string => typeof id === "string") : []);
    } catch {
      setSavedDestinationIds([]);
    }
  }, [selectedUser]);

  /* =======================================================
     EVALUATION STATE
  ======================================================= */

  const [evaluation, setEvaluation] =
    useState<EvaluationResponse | null>(null);

  const [evaluationLoading, setEvaluationLoading] =
    useState(false);

  const [evaluationError, setEvaluationError] =
    useState("");

  const [assistantMessages, setAssistantMessages] =
    useState<AssistantMessage[]>([
      {
        role: "assistant",
        content: "Ask me why a destination was recommended or how its ranking factors compare. I use the current profile and recommendation records, and show the evidence behind each answer.",
      },
    ]);
  const [assistantInput, setAssistantInput] = useState("");
  const [assistantLoading, setAssistantLoading] = useState(false);
  const [assistantError, setAssistantError] = useState("");
  const [itinerary, setItinerary] = useState<ItineraryResponse | null>(null);
  const [itineraryLoading, setItineraryLoading] = useState(false);
  const [itineraryError, setItineraryError] = useState("");
  const [itineraryShareMessage, setItineraryShareMessage] = useState("");
  const [alternativeSearch, setAlternativeSearch] = useState("");
  const [alternativeDay, setAlternativeDay] = useState(0);

  /* =======================================================
     LOAD USERS
  ======================================================= */

  useEffect(() => {
    void loadUsers();
    if (authSession) void loadAccountProfiles();
    else setAccountProfiles([]);
  }, [authSession]);

  useEffect(() => {
    let active = true;
    const loadProfile = async () => {
      if (selectedUser.startsWith("TRV-")) {
        try {
          const response = await fetch(`${API_URL}/profiles/${encodeURIComponent(selectedUser)}`, { headers: authHeaders() });
          if (!response.ok) throw new Error("Could not load this traveler profile.");
          const data = await response.json();
          if (active) setProfile({ ...defaultProfile, ...data.profile });
        } catch (profileError) {
          console.error(profileError);
          if (active) setProfileMessage("Could not load this saved traveler profile.");
        }
      } else {
        try {
          const savedProfile = window.localStorage.getItem(`travelmind.profile.${selectedUser}`);
          if (active) setProfile(savedProfile ? { ...defaultProfile, ...JSON.parse(savedProfile) } : defaultProfile);
        } catch (storageError) {
          console.error("Could not load the saved traveler profile.", storageError);
          if (active) {
            setProfile(defaultProfile);
            setProfileMessage("Saved preferences could not be read from this browser.");
          }
        }
      }
    };
    void loadProfile();
    return () => { active = false; };
  }, [selectedUser]);

  useEffect(() => {
    try {
      const savedFeedback = window.localStorage.getItem(`travelmind.feedback.${selectedUser}`);
      setPreferenceFeedback(savedFeedback ? JSON.parse(savedFeedback) as Record<string, number> : {});
      const savedWeights = window.localStorage.getItem(`travelmind.weights.${selectedUser}`);
      if (savedWeights) {
        const parsed = JSON.parse(savedWeights) as { preference?: number; crowd?: number; sustainability?: number };
        if ([parsed.preference, parsed.crowd, parsed.sustainability].every((value) => Number.isFinite(value) && (value as number) >= 0 && (value as number) <= 100)) {
          setScenarioWeights({ preference: parsed.preference as number, crowd: parsed.crowd as number, sustainability: parsed.sustainability as number });
        }
      } else setScenarioWeights({ preference: 60, crowd: 25, sustainability: 15 });
    } catch {
      setPreferenceFeedback({});
      setScenarioWeights({ preference: 60, crowd: 25, sustainability: 15 });
    }
  }, [selectedUser]);

  useEffect(() => {
    if (recommendationLens !== "scenario" || !selectedUser) {
      setScenarioRankingLoading(false);
      return;
    }
    const controller = new AbortController();
    setScenarioRankingLoading(true);
    setScenarioRankingError("");
    void fetch(`${API_URL}/recommendations/${encodeURIComponent(selectedUser)}/scenario`, {
      method: "POST",
      signal: controller.signal,
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({
        profile,
        scenario_weights: scenarioWeights,
        preference_feedback: preferenceFeedback,
      }),
    }).then(async (response) => {
      const data = await response.json();
      if (!response.ok) {
        if (response.status === 401 && authSession) clearExpiredSession();
        throw new Error(data.detail || "Could not calculate this recommendation scenario.");
      }
      setScenarioRecommendations(data.recommendations || []);
    }).catch((requestError) => {
      if (requestError instanceof Error && requestError.name !== "AbortError") {
        setScenarioRankingError(requestError.message || "Could not calculate this recommendation scenario.");
      }
    }).finally(() => {
      if (!controller.signal.aborted) setScenarioRankingLoading(false);
    });
    return () => controller.abort();
  }, [recommendationLens, selectedUser, profile, scenarioWeights, preferenceFeedback, authSession]);

  /* =======================================================
     LOAD RECOMMENDATIONS
  ======================================================= */

  useEffect(() => {
    if (selectedUser) {
      loadRecommendations(selectedUser);
    }
    setItinerary(null);
  }, [selectedUser]);

  useEffect(() => {
    setAssistantMessages([
      {
        role: "assistant",
        content: `I’m ready to explain recommendations for ${selectedUser}. Answers use the current profile and recommendation evidence.`,
      },
    ]);
    setAssistantError("");
  }, [selectedUser]);

  /* =======================================================
     LOAD EVALUATION WHEN PAGE IS OPENED
  ======================================================= */

  useEffect(() => {
    if (page === "evaluation" && !evaluation) {
      loadEvaluation();
    }
  }, [page, evaluation]);

  /* =======================================================
     API FUNCTIONS
  ======================================================= */

  function authHeaders(token = authSession?.access_token): Record<string, string> {
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  function clearExpiredSession() {
    window.sessionStorage.removeItem("travelmind.auth");
    setAuthSession(null);
    setAccountProfiles([]);
    setSelectedUser("U001");
    setAuthMessage("Your saved sign-in has expired. Sign in again to access your account; public recommendations remain available.");
  }

  async function loadUsers(token?: string) {
    try {
      const savedToken = token ?? authSession?.access_token;
      let response = await fetch(`${API_URL}/users`, { headers: authHeaders(savedToken) });
      if (response.status === 401 && savedToken) {
        clearExpiredSession();
        response = await fetch(`${API_URL}/users`);
      }

      if (!response.ok) {
        throw new Error("Failed to load users.");
      }

      const data: UsersResponse =
        await response.json();

      setUsers(data.users || []);

      if (
        data.users &&
        data.users.length > 0 &&
        !data.users.includes(selectedUser)
      ) {
        setSelectedUser(data.users[0]);
      }
    } catch (err) {
      console.error(err);
      setError(
        "Unable to connect to the recommendation API.",
      );
    }
  }

  async function loadRecommendations(userId: string) {
    setLoading(true);
    setError("");

    try {
      const savedToken = authSession?.access_token;
      let response = await fetch(`${API_URL}/recommendations/${encodeURIComponent(userId)}`, { headers: authHeaders(savedToken) });
      if (response.status === 401 && savedToken) {
        clearExpiredSession();
        response = await fetch(`${API_URL}/recommendations/${encodeURIComponent(userId)}`);
      }

      if (!response.ok) {
        throw new Error(
          `Failed to load recommendations for ${userId}.`,
        );
      }

      const data: RecommendationsResponse =
        await response.json();

      setRecommendations(
        data.recommendations || [],
      );
    } catch (err) {
      console.error(err);

      setRecommendations([]);

      setError(
        "Unable to load recommendations. Please make sure the FastAPI server is running.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function loadEvaluation() {
    setEvaluationLoading(true);
    setEvaluationError("");

    try {
      const response = await fetch(
        `${API_URL}/evaluation`,
      );

      if (!response.ok) {
        throw new Error(
          `Evaluation API returned ${response.status}`,
        );
      }

      const data: EvaluationResponse =
        await response.json();

      setEvaluation(data);
    } catch (err) {
      console.error(err);

      setEvaluationError(
        "Unable to load model evaluation results. Make sure the /evaluation endpoint is available in FastAPI.",
      );
    } finally {
      setEvaluationLoading(false);
    }
  }

  async function loadAccountProfiles(token?: string) {
    if (!token && !authSession) return;
    try {
      const savedToken = token ?? authSession?.access_token;
      const response = await fetch(`${API_URL}/account/profiles`, {
        headers: authHeaders(savedToken),
      });
      if (response.status === 401 && savedToken) {
        clearExpiredSession();
        return;
      }
      if (!response.ok) throw new Error("Could not load account profiles.");
      const data = await response.json();
      setAccountProfiles(data.profiles || []);
    } catch (error) {
      console.error(error);
    }
  }

  async function submitAccountAuth() {
    setAuthLoading(true);
    setAuthMessage("");
    try {
      if (authMode === "register" && (!profile.name.trim() || !profile.startingLocation.trim() || !profile.interests.trim() || !Number.isFinite(Number(profile.budget)) || Number(profile.budget) <= 0)) {
        throw new Error("Add your name, starting location, interests, and a valid daily budget to finish your traveler profile.");
      }
      const claimProfile = authMode === "register" && selectedUser.startsWith("TRV-")
        ? selectedUser
        : null;
      const response = await fetch(`${API_URL}/auth/${authMode === "register" ? "register" : "login"}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: authEmail, password: authPassword, claim_profile_id: claimProfile }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Account request failed.");
      const session = data as AuthSession;
      if (authMode === "register") {
        const claimedProfile = Boolean(claimProfile);
        const profileResponse = await fetch(
          claimedProfile ? `${API_URL}/profiles/${encodeURIComponent(selectedUser)}` : `${API_URL}/profiles`,
          {
            method: claimedProfile ? "PUT" : "POST",
            headers: { "Content-Type": "application/json", ...authHeaders(session.access_token) },
            body: JSON.stringify(profile),
          },
        );
        const profileData = await profileResponse.json();
        if (!profileResponse.ok) throw new Error(profileData.detail || "Account created, but traveler profile setup failed. Sign in to finish setup.");
        setProfile({ ...defaultProfile, ...profileData.profile });
        setSelectedUser(profileData.user_id);
      }
      setAuthSession(session);
      window.sessionStorage.setItem("travelmind.auth", JSON.stringify(session));
      await Promise.all([loadUsers(session.access_token), loadAccountProfiles(session.access_token)]);
      setAuthPassword("");
      setAuthMessage(authMode === "register" ? "Account and traveler profile created. Your recommendations are ready." : "Signed in successfully.");
      if (authMode === "register") setPage("dashboard");
    } catch (error) {
      setAuthMessage(error instanceof Error ? error.message : "Account request failed.");
    } finally {
      setAuthLoading(false);
    }
  }

  async function signOut() {
    if (authSession) {
      try {
        await fetch(`${API_URL}/auth/logout`, {
          method: "POST",
          headers: authHeaders(),
        });
      } catch (error) {
        console.error("Could not revoke the sign-out token.", error);
      }
    }
    window.sessionStorage.removeItem("travelmind.auth");
    setAuthSession(null);
    setAccountProfiles([]);
    setSelectedUser("U001");
    setAuthMessage("You are signed out. Guest profiles remain available on this device.");
  }

  async function loadItinerary() {
    setItineraryLoading(true);
    setItineraryError("");
    try {
      const response = await fetch(`${API_URL}/itinerary/${encodeURIComponent(selectedUser)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ profile }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not build your itinerary.");
      setItinerary(data as ItineraryResponse);
    } catch (error) {
      setItineraryError(error instanceof Error ? error.message : "Could not build your itinerary.");
    } finally {
      setItineraryLoading(false);
    }
  }

  function itineraryReportHtml() {
    if (!itinerary) return "";
    const days = itinerary.days.map((day) => `<section><h2>Day ${day.day}: ${escapeHtml(day.area)}</h2><p class="meta">About ${day.estimated_visit_hours} visit hours · grouped around ${escapeHtml(day.area)} to reduce unnecessary backtracking.</p>${day.stops.length ? `<ol>${day.stops.map((stop) => `<li><strong>${escapeHtml(stop.name)}</strong> <span class="meta">${escapeHtml(stop.district)} · about ${stop.visit_duration_hours} hours · ${escapeHtml(formatCurrency(stop.estimated_cost_lkr))}${stop.straight_line_distance_km == null ? "" : ` · approximately ${Math.round(stop.straight_line_distance_km)} km from your start`}</span><p>${escapeHtml(stop.recommendation_reason)}</p></li>`).join("")}</ol>` : `<p>No destinations fit this day’s pace and distance settings.</p>`}</section>`).join("");
    return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>${escapeHtml(profile.name || itinerary.traveler_name)} · Sri Lanka itinerary</title><style>body{font:15px/1.65 system-ui,sans-serif;color:#17372a;max-width:850px;margin:36px auto;padding:0 22px}h1,h2{font-family:system-ui,sans-serif}h1{font-size:32px}h2{font-size:20px}section{margin:24px 0;padding:18px;border:1px solid #dce9e0;border-radius:14px}li{padding:9px 0}.meta{color:#60766a}aside{padding:14px;background:#f2f8f4;border-left:3px solid #00b894}@media print{body{margin:0;max-width:none}}</style></head><body><p class="meta">TRAVELMIND · PERSONALIZED TRIP DRAFT</p><h1>${escapeHtml(profile.name || itinerary.traveler_name)}’s Sri Lanka itinerary</h1><p>${escapeHtml(profile.tripDuration)} days · ${escapeHtml(profile.travelPace)} pace · starting in ${escapeHtml(profile.startingLocation)}</p>${days}<aside><strong>How to use this plan</strong><p>${escapeHtml(itinerary.planning_note)}</p><p>Distances are approximate straight-line distances from your starting point. Visit durations and costs are estimates; this draft does not include verified opening hours, transport routes, or booking details.</p></aside></body></html>`;
  }

  function downloadItinerary() {
    if (!itinerary) return;
    downloadHtmlReport(`travelmind-itinerary-${new Date().toISOString().slice(0, 10)}.html`, itineraryReportHtml());
  }

  function downloadItineraryPdf() {
    if (!itinerary) return;
    const lines = [
      "TRAVELMIND | PERSONALIZED SRI LANKA TRIP DRAFT",
      `${profile.name || itinerary.traveler_name} | ${profile.tripDuration} days | ${profile.travelPace} pace | Start: ${profile.startingLocation}`,
      "",
      ...itinerary.days.flatMap((day) => [
        `DAY ${day.day}: ${day.area} | Estimated visit time: ${day.estimated_visit_hours} hours`,
        ...(day.stops.length ? day.stops.flatMap((stop) => [
          `- ${stop.name} (${stop.district}) | ${stop.visit_duration_hours} hours | ${formatCurrency(stop.estimated_cost_lkr)}${stop.straight_line_distance_km == null ? "" : ` | about ${Math.round(stop.straight_line_distance_km)} km from start`}`,
          `  Why it is included: ${stop.recommendation_reason}`,
        ]) : ["No destinations were assigned to this day."]),
        "",
      ]),
      "PLANNING NOTES",
      itinerary.planning_note,
      "Costs and visit times are estimates. Distances are straight-line approximations, not road routes or travel times. Verify transport, opening hours, weather, and current prices before travel.",
    ];
    downloadPdfReport(`travelmind-itinerary-${new Date().toISOString().slice(0, 10)}.pdf`, lines);
  }

  function addAlternativeToDay(recommendation: Recommendation) {
    if (!itinerary) return;
    const dayIndex = Math.max(0, Math.min(alternativeDay, itinerary.days.length - 1));
    const day = itinerary.days[dayIndex];
    if (itinerary.days.some((item) => item.stops.some((stop) => stop.destination_id === recommendation.destination_id))) return;
    const duration = recommendation.duration_hours && recommendation.duration_hours > 0 ? recommendation.duration_hours : 2;
    const stop: ItineraryStop = {
      destination_id: recommendation.destination_id,
      name: recommendation.name,
      district: recommendation.district,
      rank: recommendation.rank,
      estimated_cost_lkr: recommendation.estimated_cost_lkr,
      visit_duration_hours: duration,
      straight_line_distance_km: recommendation.distance_km,
      recommendation_reason: `Added by you from the alternative search. ${recommendation.explanation || "It appears in your personalized destination ranking."}`,
    };
    const areas = day.area && !day.area.startsWith("No destination") ? day.area.split(" · ") : [];
    const updatedDays = itinerary.days.map((item, index) => index !== dayIndex ? item : {
      ...item,
      area: areas.includes(stop.district) ? areas.join(" · ") : [...areas, stop.district].join(" · "),
      estimated_visit_hours: Math.round((item.estimated_visit_hours + duration) * 10) / 10,
      stops: [...item.stops, stop],
    });
    setItinerary({ ...itinerary, days: updatedDays });
    setAlternativeSearch("");
  }

  async function shareItinerary() {
    if (!itinerary) return;
    const text = `${profile.name || itinerary.traveler_name}’s ${profile.tripDuration}-day Sri Lanka itinerary\nStarting in ${profile.startingLocation} · ${profile.travelPace} pace\n\n${itinerary.days.map((day) => `Day ${day.day}: ${day.area}\n${day.stops.map((stop) => `• ${stop.name} — ${stop.recommendation_reason}`).join("\n")}`).join("\n\n")}\n\n${itinerary.planning_note}\n\nDraft estimates only; check routes, opening hours, and costs before travel.`;
    try {
      if (navigator.share) await navigator.share({ title: "My TravelMind itinerary", text });
      else { await navigator.clipboard.writeText(text); setItineraryShareMessage("Itinerary copied to clipboard."); }
    } catch (shareError) {
      if (shareError instanceof Error && shareError.name !== "AbortError") setItineraryShareMessage("Could not share automatically. Download the plan to send it.");
    }
  }

  function downloadResearchReport() {
    if (!evaluation) return;

    const generatedAt = new Date().toLocaleString();
    const modelRows = evaluation.models.map((model) => `
      <tr><td>${escapeHtml(model.id)}</td><td>${escapeHtml(model.name)}</td>
      <td>${(model.precision_at_5 * 100).toFixed(2)}%</td>
      <td>${(model.recall_at_5 * 100).toFixed(2)}%</td>
      <td>${(model.ndcg_at_5 * 100).toFixed(2)}%</td></tr>`).join("");
    const ndcgRows = evaluation.ndcg_by_k.map((point) => `
      <tr><td>${point.k}</td><td>${(point.b5_ndcg * 100).toFixed(2)}%</td>
      <td>${(point.demand_aware_ndcg * 100).toFixed(2)}%</td>
      <td>${(point.ndcg_change * 100).toFixed(2)} pp</td></tr>`).join("");
    const statsRows = Object.entries(evaluation.demand_aware_statistics)
      .map(([key, value]) => `<tr><td>${escapeHtml(key.replace(/_/g, " "))}</td><td>${value == null ? "Not available" : Number(value).toFixed(3)}</td></tr>`)
      .join("");
    const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>TravelMind model evaluation</title>
      <style>body{font:15px/1.6 system-ui,sans-serif;color:#19352b;max-width:1000px;margin:40px auto;padding:0 24px}h1,h2{font-family:Manrope,system-ui,sans-serif}h1{font-size:32px}h2{margin-top:32px;font-size:20px}p,.meta{color:#60746a}.meta{font-size:13px}table{width:100%;border-collapse:collapse;margin:14px 0 24px}th,td{padding:10px 12px;text-align:left;border-bottom:1px solid #e1eae5}th{background:#edf6f0;color:#315344}.notice{padding:14px;border-left:3px solid #00b894;background:#f2f8f4}@media print{body{margin:0;max-width:none}}</style></head><body>
      <p class="meta">TRAVELMIND · RESEARCH EVALUATION REPORT</p><h1>Recommendation model evaluation</h1>
      <p class="meta">Generated ${escapeHtml(generatedAt)} · Source: current evaluation results returned by the project API.</p>
      <p>This report summarizes the saved offline benchmark metrics. It does not claim statistical significance because confidence intervals, p-values and participant study results are not included in the current API response.</p>
      <h2>Ranking model comparison (K = 5)</h2><table><thead><tr><th>ID</th><th>Model</th><th>Precision@5</th><th>Recall@5</th><th>NDCG@5</th></tr></thead><tbody>${modelRows}</tbody></table>
      <h2>NDCG by recommendation depth</h2><table><thead><tr><th>K</th><th>B5 semantic</th><th>Demand-aware</th><th>Change</th></tr></thead><tbody>${ndcgRows}</tbody></table>
      <h2>Demand-aware system statistics</h2><table><thead><tr><th>Metric</th><th>Value</th></tr></thead><tbody>${statsRows}</tbody></table>
      <h2>Research interpretation limits</h2><p class="notice">These metrics describe the stored evaluation dataset and ranking outputs. They do not establish user trust, explanation fidelity, causal effects, or generalization to new travelers. The next validation step is an evidence-fidelity audit followed by a controlled user study, reporting effect sizes and confidence intervals as specified in the proposal.</p>
      </body></html>`;
    downloadHtmlReport(
      `travelmind-evaluation-${new Date().toISOString().slice(0, 10)}.html`,
      html,
    );
  }

  async function saveProfile() {
    const budget = Number(profile.budget);
    if (!Number.isFinite(budget) || budget <= 0) {
      setProfileSaved(false);
      setProfileMessage("Enter a daily budget greater than zero.");
      return;
    }
    if (!profile.name.trim() || !profile.startingLocation.trim() || !profile.interests.trim()) {
      setProfileSaved(false);
      setProfileMessage("Add your name, starting location, and at least one interest.");
      return;
    }

    try {
      const isSavedTraveler = selectedUser.startsWith("TRV-");
      const response = await fetch(
        isSavedTraveler
          ? `${API_URL}/profiles/${encodeURIComponent(selectedUser)}`
          : `${API_URL}/profiles`,
        {
          method: isSavedTraveler ? "PUT" : "POST",
          headers: { "Content-Type": "application/json", ...authHeaders() },
          body: JSON.stringify(profile),
        },
      );
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not save your traveler profile.");
      setProfile({ ...defaultProfile, ...data.profile });
      setProfileMessage("Profile saved. Personalized recommendations are ready.");
      setProfileSaved(true);
      setSelectedUser(data.user_id);
      void loadUsers();
      if (authSession) void loadAccountProfiles();
    } catch (storageError) {
      console.error("Could not save the traveler profile.", storageError);
      setProfileSaved(false);
      setProfileMessage(storageError instanceof Error ? storageError.message : "Could not save your traveler profile.");
      return;
    }

    window.setTimeout(() => {
      setProfileSaved(false);
    }, 4000);
  }

  async function askAssistant(question = assistantInput) {
    const cleanQuestion = question.trim();
    if (!cleanQuestion || assistantLoading) return;

    const history = assistantMessages.slice(-6).map(({ role, content }) => ({
      role,
      content,
    }));
    setAssistantMessages((current) => [
      ...current,
      { role: "user", content: cleanQuestion },
    ]);
    setAssistantInput("");
    setAssistantLoading(true);
    setAssistantError("");

    try {
      const response = await fetch(
        `${API_URL}/assistant/chat/${encodeURIComponent(selectedUser)}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeaders() },
          body: JSON.stringify({
            question: cleanQuestion,
            profile,
            history,
          }),
        },
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || `Chat request failed (${response.status}).`);
      }

      const result = data as AssistantResponse;
      setAssistantMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: result.answer,
          sources: result.sources,
          latencyMs: result.latency_ms,
        },
      ]);
    } catch (chatError) {
      setAssistantError(
        chatError instanceof Error
          ? chatError.message
          : "The explainability assistant is unavailable.",
      );
    } finally {
      setAssistantLoading(false);
    }
  }

  /* =======================================================
     COMPUTED DATA
  ======================================================= */

  const currentRecommendationSet = recommendationLens === "scenario" && scenarioRecommendations.length > 0
    ? scenarioRecommendations
    : recommendations;

  const categories = useMemo(() => {
    return [
      "All",
      ...Array.from(
        new Set(
          recommendations
            .map((item) => item.category)
            .filter(Boolean),
        ),
      ),
    ];
  }, [recommendations]);

  const filteredRecommendations = useMemo(() => {
    let results = [...currentRecommendationSet];

    if (searchTerm.trim()) {
      const query =
        searchTerm.trim().toLowerCase();

      results = results.filter((item) => {
        return (
          item.name
            .toLowerCase()
            .includes(query) ||
          item.category
            .toLowerCase()
            .includes(query) ||
          item.district
            .toLowerCase()
            .includes(query)
        );
      });
    }

    if (categoryFilter !== "All") {
      results = results.filter(
        (item) =>
          item.category === categoryFilter,
      );
    }

    if (crowdFilter !== "All") {
      results = results.filter((item) => {
        const level =
          item.predicted_crowd_level ||
          "";

        return (
          level.toLowerCase() ===
          crowdFilter.toLowerCase()
        );
      });
    }

    if (showOnlyStrongMatches) {
      results = results.filter(
        (item) =>
          scorePercent(
            item.demand_aware_score,
          ) >= 65,
      );
    }

    results.sort((a, b) => {
      if (sortBy === "score") {
        return (
          (recommendationLens === "scenario" ? (b.scenario_score || 0) : (b.demand_aware_score || 0)) -
          (recommendationLens === "scenario" ? (a.scenario_score || 0) : (a.demand_aware_score || 0))
        );
      }

      if (sortBy === "cost") {
        return (
          (a.estimated_cost_lkr || 0) -
          (b.estimated_cost_lkr || 0)
        );
      }

      if (sortBy === "crowd") {
        return (
          (a.predicted_crowd_score || 0) -
          (b.predicted_crowd_score || 0)
        );
      }

      return a.rank - b.rank;
    });

    return results;
  }, [
    currentRecommendationSet,
    searchTerm,
    categoryFilter,
    crowdFilter,
    sortBy,
    showOnlyStrongMatches,
  ]);

  const averageScore = useMemo(() => {
    if (!recommendations.length) return 0;

    const total = recommendations.reduce(
      (sum, item) =>
        sum +
        scorePercent(item.demand_aware_score),
      0,
    );

    return total / recommendations.length;
  }, [recommendations]);

  const averageSustainability = useMemo(() => {
    if (!recommendations.length) return 0;

    const values = recommendations
      .map((item) =>
        scorePercent(
          item.sustainability_score,
        ),
      )
      .filter((value) => value > 0);

    if (!values.length) return 0;

    return (
      values.reduce(
        (sum, value) => sum + value,
        0,
      ) / values.length
    );
  }, [recommendations]);

  const lowCrowdCount = useMemo(() => {
    return recommendations.filter((item) =>
      String(
        item.predicted_crowd_level || "",
      )
        .toLowerCase()
        .includes("low"),
    ).length;
  }, [recommendations]);

  /* =======================================================
     DASHBOARD
  ======================================================= */

  function renderDashboard() {
    const topRecommendations =
      recommendations.slice(0, 3);

    return (
      <div className="page-content dashboard-page">
        <div className="dashboard-welcome-row">
          <div>
            <span className="eyebrow">YOUR TRAVELMIND HOME</span>
            <h1>Welcome back{profile.name.trim() ? `, ${profile.name.trim().split(/\s+/)[0]}` : ""}</h1>
            <p>Your next Sri Lankan story starts here.</p>
          </div>
          <div className="dashboard-traveler-select"><span>Traveler profile</span><select aria-label="Active traveler profile" value={selectedUser} onChange={(event) => { setProfileMessage(""); setProfileSaved(false); setSelectedUser(event.target.value); }}>{users.map((user) => <option key={user} value={user}>{user === selectedUser && profile.name ? profile.name : user}</option>)}</select><button type="button" aria-label="Edit traveler profile" onClick={() => setPage("profile")}><AppIcon name="user" /></button></div>
        </div>

        <section className="travelmind-hero" style={{ backgroundImage: `linear-gradient(90deg,rgba(5,33,58,.70) 0%,rgba(5,38,63,.55) 50%,rgba(5,33,58,.70) 100%),url("${getDestinationImage(topRecommendations[0]?.category || "nature")}")` }}>
          <div className="travelmind-hero-copy">
            <span className="hero-kicker">PERSONAL TRAVEL, REIMAGINED</span>
            <h1 className="dashboard-hero-title">Find your own rhythm<br className="hero-desktop-break" /> in Sri Lanka.</h1>
            <p>Discover places that fit your style, uncover quieter options, and shape every day around what you love.</p>
            <button className="hero-button" onClick={() => setPage("recommendations")}>Discover destinations <span aria-hidden="true">&gt;</span></button>
          </div>
        </section>

        {error && (
          <div className="error-banner">
            <div>
              <strong>Connection issue</strong>
              <p>{error}</p>
            </div>

            <button
              onClick={() =>
                loadRecommendations(selectedUser)
              }
            >
              Retry
            </button>
          </div>
        )}

        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-card-icon">✦</div>

            <span>Average AI Match</span>

            <strong>
              {Math.round(averageScore)}%
            </strong>

            <small>
              Across your top recommendations
            </small>
          </div>

          <div className="stat-card">
            <div className="stat-card-icon">🌿</div>

            <span>Sustainability</span>

            <strong>
              {Math.round(averageSustainability)}%
            </strong>

            <small>
              Average sustainability score
            </small>
          </div>

          <div className="stat-card">
            <div className="stat-card-icon">🌤️</div>

            <span>Low Crowd Options</span>

            <strong>{lowCrowdCount}</strong>

            <small>
              Lower predicted crowd destinations
            </small>
          </div>

          <div className="stat-card">
            <div className="stat-card-icon">📍</div>

            <span>Recommendations</span>

            <strong>
              {recommendations.length}
            </strong>

            <small>
              AI-ranked destinations available
            </small>
          </div>
        </div>

        <section className="dashboard-section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">
                AI RECOMMENDATIONS
              </span>

              <h2>Top destinations for you</h2>
            </div>

            <button
              className="secondary-button"
              onClick={() =>
                setPage("recommendations")
              }
            >
              View all
            </button>
          </div>

          {loading ? (
            <div className="loading-state">
              Loading recommendations...
            </div>
          ) : (
            <div className="dashboard-recommendation-grid">
              {topRecommendations.map(
                (recommendation) => (
                  <button
                    key={`${recommendation.destination_id}-${recommendation.rank}`}
                    className="dashboard-recommendation-card"
                    onClick={() =>
                      setSelectedRecommendation(
                        recommendation,
                      )
                    }
                  >
                    <DestinationVisual
                      recommendation={
                        recommendation
                      }
                    />

                    <div className="dashboard-card-content">
                      <div className="recommendation-rank">
                        #{recommendation.rank}
                      </div>

                      <h3>
                        {recommendation.name}
                      </h3>

                      <p>
                        {recommendation.category} ·{" "}
                        {recommendation.district}
                      </p>

                      <div className="dashboard-card-bottom">
                        <strong>
                          {Math.round(
                            scorePercent(
                              recommendation.demand_aware_score,
                            ),
                          )}
                          %
                        </strong>

                        <span>
                          AI match
                        </span>
                      </div>
                    </div>
                  </button>
                ),
              )}
            </div>
          )}
        </section>

        <section className="dashboard-next-step">
          <div className="dashboard-next-icon"><AppIcon name="compass" /></div>
          <div><span className="eyebrow">YOUR NEXT ADVENTURE</span><h2>Turn your shortlist into a trip</h2><p>Build a day-by-day plan around your trip length, travel pace, interests, and ranked destinations. Review the reasoning and estimates before you go.</p></div>
          <button className="primary-button" onClick={() => setPage("itinerary")}>Plan my trip <span aria-hidden="true">→</span></button>
        </section>

        <section className="dashboard-section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">
                TRAVEL PROFILE
              </span>

              <h2>Your current preferences</h2>
            </div>

            <button
              className="secondary-button"
              onClick={() => setPage("profile")}
            >
              Edit profile
            </button>
          </div>

          <div className="profile-summary-grid">
            <div className="profile-summary-item">
              <span>Budget</span>
              <strong>
                {formatCurrency(
                  Number(profile.budget),
                )}
              </strong>
            </div>

            <div className="profile-summary-item">
              <span>Trip Duration</span>
              <strong>
                {profile.tripDuration} days
              </strong>
            </div>

            <div className="profile-summary-item">
              <span>Travel Style</span>
              <strong>
                {profile.travelStyle}
              </strong>
            </div>

            <div className="profile-summary-item">
              <span>Starting Location</span>
              <strong>
                {profile.startingLocation}
              </strong>
            </div>

            <div className="profile-summary-item">
              <span>Preferred Crowd</span>
              <strong>
                {profile.preferredCrowd}
              </strong>
            </div>

            <div className="profile-summary-item">
              <span>Preferred Weather</span>
              <strong>
                {profile.preferredWeather}
              </strong>
            </div>
          </div>
        </section>
      </div>
    );
  }

  /* =======================================================
     RECOMMENDATIONS
  ======================================================= */

  function recordPreferenceFeedback(item: Recommendation, signal: number) {
    const category = item.category.toLowerCase();
    const updated = { ...preferenceFeedback, [category]: Math.max(-3, Math.min(3, (preferenceFeedback[category] || 0) + signal)) };
    setPreferenceFeedback(updated);
    setRecommendationLens("scenario");
    setFeedbackNotice(`Saved locally for ${item.category}. Your next scenario ordering will adapt to this preference.`);
    try { window.localStorage.setItem(`travelmind.feedback.${selectedUser}`, JSON.stringify(updated)); } catch { setFeedbackNotice("Could not save this preference in browser storage."); }
  }

  function updateScenarioWeight(key: keyof typeof scenarioWeights, value: number) {
    const updated = { ...scenarioWeights, [key]: value };
    if (updated.preference + updated.crowd + updated.sustainability === 0) updated[key] = 1;
    setScenarioWeights(updated);
    setRecommendationLens("scenario");
    try { window.localStorage.setItem(`travelmind.weights.${selectedUser}`, JSON.stringify(updated)); }
    catch { setFeedbackNotice("Could not save scenario weights in browser storage."); }
  }

  function toggleSavedDestination(destinationId: string) {
    const updated = savedDestinationIds.includes(destinationId)
      ? savedDestinationIds.filter((id) => id !== destinationId)
      : [...savedDestinationIds, destinationId];
    setSavedDestinationIds(updated);
    try {
      window.localStorage.setItem(`travelmind.saved.${selectedUser}`, JSON.stringify(updated));
    } catch {
      setFeedbackNotice("Could not save this place in browser storage.");
    }
  }

  function renderRecommendations() {
    const mapPoints: Record<string, [number, number]> = {
      jaffna: [210, 43], kilinochchi: [211, 88], mullaitivu: [268, 112], mannar: [134, 147], vavuniya: [201, 151],
      anuradhapura: [165, 192], trincomalee: [275, 181], puttalam: [112, 243], polonnaruwa: [226, 237], kurunegala: [148, 280], batticaloa: [286, 258],
      matale: [213, 275], kandy: [210, 303], ampara: [271, 318], gampaha: [144, 334], kegalle: [179, 342], badulla: [236, 358], colombo: [139, 359],
      monaragala: [263, 383], ratnapura: [195, 383], kalutara: [148, 398], "nuwara eliya": [211, 367], galle: [157, 440], matara: [190, 456], hambantota: [233, 430],
      ella: [244, 372], sigiriya: [205, 221], dambulla: [205, 251], yala: [249, 412], mirissa: [180, 451], unawatuna: [151, 436],
    };
    const destinationPoint = (item: Recommendation, index: number): [number, number] => {
      const name = item.name.toLowerCase();
      const district = item.district.toLowerCase();
      const pointKey = Object.keys(mapPoints).find((key) => name.includes(key) || district.includes(key));
      const match = mapPoints[name] || mapPoints[district] || (pointKey ? mapPoints[pointKey] : undefined);
      return match || [165 + (index % 3) * 35, 295 + (index % 4) * 30];
    };
    const lensRecommendations = recommendationLens === "balanced" || recommendationLens === "scenario" ? filteredRecommendations : [...filteredRecommendations].sort((a, b) => {
      const values = { crowd: "predicted_crowd_fit", weather: "weather_fit", sustainability: "sustainability_fit" } as const;
      const key = values[recommendationLens];
      return (b[key] || 0) - (a[key] || 0);
    });
    const comparedRecommendations = currentRecommendationSet.filter((item) => comparisonIds.includes(item.destination_id));
    return (
      <div className="page-content">
        <div className="page-header">
          <div>
            <span className="eyebrow">
              PERSONALIZED DISCOVERY
            </span>

            <h1>AI recommendations</h1>

            <p>
              Explore destinations ranked using
              your preferences, context, weather,
              crowd prediction and sustainability.
            </p>
          </div>

          <div className="header-user-card">
            <span>Traveler</span>

            <strong>{profile.name || selectedUser}</strong>

            <select
              value={selectedUser}
              onChange={(event) => {
                setProfileMessage("");
                setProfileSaved(false);
                setSelectedUser(event.target.value);
              }}
            >
              {users.map((user) => (
                <option key={user} value={user}>
                  {user}
                </option>
              ))}
            </select>
          </div>
        </div>

        <nav className="dashboard-shortcuts" aria-label="Travel intelligence shortcuts">
          <button onClick={() => setPage("itinerary")}><span className="shortcut-icon"><AppIcon name="compass" /></span><span><strong>Plan a trip</strong><small>Build your itinerary</small></span><b aria-hidden="true">›</b></button>
          <button onClick={() => setPage("crowd")}><span className="shortcut-icon amber"><AppIcon name="people" /></span><span><strong>Check crowd levels</strong><small>Find quieter places</small></span><b aria-hidden="true">›</b></button>
          <button onClick={() => setPage("weather")}><span className="shortcut-icon sky"><AppIcon name="sun" /></span><span><strong>Weather insights</strong><small>Compare conditions</small></span><b aria-hidden="true">›</b></button>
          <button onClick={() => setPage("assistant")}><span className="shortcut-icon mint"><AppIcon name="sparkle" /></span><span><strong>Ask TravelMind</strong><small>Get an explainable answer</small></span><b aria-hidden="true">›</b></button>
        </nav>

        <section className="research-lens-panel"><div><span className="eyebrow">RESEARCH LENS</span><strong>Explore ranking trade-offs</strong><p>Reorder your current matches by one signal. Category feedback is saved in this browser; the scenario score and ranking are calculated by the API.</p></div><div className="research-lens-options" role="group" aria-label="Recommendation sorting lens">{([{ id: "balanced", label: "Balanced ranking" }, { id: "crowd", label: "Prefer lower crowd" }, { id: "weather", label: "Weather fit" }, { id: "sustainability", label: "Sustainability" }, { id: "scenario", label: "My weighted scenario" }] as const).map((lens) => <button key={lens.id} className={recommendationLens === lens.id ? "selected" : ""} onClick={() => setRecommendationLens(lens.id)}>{lens.label}</button>)}</div><div className="scenario-weight-controls"><label><span>Personalization <strong>{scenarioWeights.preference}%</strong></span><input type="range" min="0" max="100" value={scenarioWeights.preference} onChange={(event) => updateScenarioWeight("preference", Number(event.target.value))} /></label><label><span>Lower crowd <strong>{scenarioWeights.crowd}%</strong></span><input type="range" min="0" max="100" value={scenarioWeights.crowd} onChange={(event) => updateScenarioWeight("crowd", Number(event.target.value))} /></label><label><span>Sustainability <strong>{scenarioWeights.sustainability}%</strong></span><input type="range" min="0" max="100" value={scenarioWeights.sustainability} onChange={(event) => updateScenarioWeight("sustainability", Number(event.target.value))} /></label><small>Weights are normalized by the API and applied to the full destination catalog before returning the top 10. Original model scores are retained separately.</small></div>{feedbackNotice && <p className="feedback-notice" role="status">{feedbackNotice}</p>}</section>

        <div className="filter-bar">
          <div className="search-box">
            <span>⌕</span>

            <input
              value={searchTerm}
              onChange={(event) =>
                setSearchTerm(event.target.value)
              }
              placeholder="Search destinations..."
            />
          </div>

          <select
            value={categoryFilter}
            onChange={(event) =>
              setCategoryFilter(event.target.value)
            }
          >
            {categories.map((category) => (
              <option
                key={category}
                value={category}
              >
                {category}
              </option>
            ))}
          </select>

          <select
            value={crowdFilter}
            onChange={(event) =>
              setCrowdFilter(event.target.value)
            }
          >
            <option value="All">All crowds</option>
            <option value="Low">Low crowd</option>
            <option value="Medium">
              Medium crowd
            </option>
            <option value="High">High crowd</option>
          </select>

          <select
            value={sortBy}
            onChange={(event) =>
              setSortBy(event.target.value)
            }
          >
            <option value="rank">
              AI rank
            </option>
            <option value="score">
              {recommendationLens === "scenario" ? "Scenario score" : "Match score"}
            </option>
            <option value="cost">
              Lowest cost
            </option>
            <option value="crowd">
              Lowest crowd
            </option>
          </select>

          <label className="filter-checkbox">
            <input
              type="checkbox"
              checked={showOnlyStrongMatches}
              onChange={(event) =>
                setShowOnlyStrongMatches(
                  event.target.checked,
                )
              }
            />

            <span>Strong matches only</span>
          </label>
        </div>

        <div className="recommendation-view-switch" role="group" aria-label="Recommendation view">
          <span>Explore view</span>
          <button className={recommendationView === "grid" ? "selected" : ""} onClick={() => setRecommendationView("grid")}>Cards</button>
          <button className={recommendationView === "map" ? "selected" : ""} onClick={() => setRecommendationView("map")}>Map</button>
        </div>

        {scenarioRankingLoading && <div className="loading-state">Recalculating your weighted scenario in the recommendation API…</div>}
        {scenarioRankingError && <div className="error-banner" role="alert"><p>{scenarioRankingError}</p></div>}
        {loading ? (
          <div className="loading-state">
            Loading AI recommendations...
          </div>
        ) : filteredRecommendations.length ===
          0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">
              🔎
            </div>

            <h3>No destinations found</h3>

            <p>
              Try changing your search or filters.
            </p>
          </div>
        ) : recommendationView === "map" ? (
          <div className="destination-map-layout">
            <div className="destination-map-panel">
              <div className="destination-map-heading"><div><span className="eyebrow">SRI LANKA EXPLORER</span><strong>{lensRecommendations.length} places in your current shortlist</strong></div><span className="map-legend"><i /> Lower crowd <i className="map-legend-high" /> Higher crowd</span></div>
              <svg className="sri-lanka-map" viewBox="0 0 400 500" role="img" aria-label="Schematic map of Sri Lanka with recommendation markers">
                <path className="map-ocean-lines" d="M0 100H400M0 200H400M0 300H400M0 400H400M80 0V500M160 0V500M240 0V500M320 0V500" />
                <path className="sri-lanka-shape" d="M185 23 C169 45 178 68 161 87 C145 105 135 123 144 143 C127 159 131 177 143 194 C127 213 115 231 119 249 C103 268 107 284 124 299 C115 319 120 338 139 350 C127 371 137 394 151 408 C146 430 164 449 178 468 C190 485 208 492 220 476 C234 458 249 446 249 426 C268 414 275 395 264 379 C280 362 286 343 273 326 C289 308 296 288 281 269 C294 250 287 232 273 216 C286 195 279 176 265 160 C277 141 269 124 251 110 C257 91 243 75 225 64 C224 45 207 31 196 20 C192 15 188 17 185 23Z" />
                {lensRecommendations.map((item, index) => {
                  const [x, y] = destinationPoint(item, index);
                  return <g key={item.destination_id} className={`map-marker ${getCrowdClass(item.predicted_crowd_level)}`} role="button" tabIndex={0} aria-label={`Open ${item.name}, ${item.predicted_crowd_level || "unknown"} crowd`} onClick={() => setSelectedRecommendation(item)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") setSelectedRecommendation(item); }}><circle className="map-marker-halo" cx={x} cy={y} r="13" /><circle className="map-marker-dot" cx={x} cy={y} r="7" /><title>{item.name} · {item.district}</title></g>;
                })}
              </svg>
              <p className="map-disclaimer">Schematic map · pin placement is approximate and intended for discovery, not navigation.</p>
            </div>
            <aside className="destination-map-list"><h2>Recommended places</h2>{lensRecommendations.map((item, index) => <button key={item.destination_id} onClick={() => setSelectedRecommendation(item)}><span className={`map-list-pin ${getCrowdClass(item.predicted_crowd_level)}`}>{index + 1}</span><span><strong>{item.name}</strong><small>{item.district} · {item.predicted_crowd_level || "Crowd unknown"}</small></span><b>{Math.round(scorePercent(item.demand_aware_score))}%</b></button>)}</aside>
          </div>
        ) : (
          <div className="recommendation-grid">
            {lensRecommendations.map(
              (recommendation) => (
                <article
                  key={`${recommendation.destination_id}-${recommendation.rank}`}
                  className="recommendation-card"
                >
                  <div className="recommendation-card-visual">
                    <DestinationVisual
                      recommendation={
                        recommendation
                      }
                    />

                    <span className="rank-badge">
                      {recommendationLens === "scenario" ? `Scenario #${recommendation.rank}` : `AI #${recommendation.rank}`}
                    </span>
                  </div>

                  <div className="recommendation-card-body">
                    <div className="recommendation-title-row">
                      <div>
                        <h3>
                          {recommendation.name}
                        </h3>

                        <p>
                          {recommendation.category} ·{" "}
                          {recommendation.district}
                        </p>
                      </div>

                      <ScoreCircle
                        value={recommendationLens === "scenario" ? recommendation.scenario_score : recommendation.demand_aware_score}
                        size={70}
                      />
                    </div>

                    <button className={`save-destination-button ${savedDestinationIds.includes(recommendation.destination_id) ? "saved" : ""}`} onClick={() => toggleSavedDestination(recommendation.destination_id)} aria-pressed={savedDestinationIds.includes(recommendation.destination_id)}>{savedDestinationIds.includes(recommendation.destination_id) ? "♥ Saved place" : "♡ Save place"}</button>

                    <div className="recommendation-mini-stats">
                      <div>
                        <span>Cost</span>
                        <strong>
                          {formatCurrency(
                            recommendation.estimated_cost_lkr,
                          )}
                        </strong>
                      </div>

                      <div>
                        <span>Crowd</span>
                        <strong>
                          {formatNumber(
                            recommendation.predicted_crowd_score,
                            1,
                          )}
                        </strong>
                      </div>

                      <div>
                        <span>Weather</span>
                        <strong>
                          {Math.round(
                            scorePercent(
                              recommendation.weather_suitability,
                            ),
                          )}
                          %
                        </strong>
                      </div>
                    </div>

                    <div className="recommendation-tags">
                      <span
                        className={`crowd-tag ${getCrowdClass(
                          recommendation.predicted_crowd_level,
                        )}`}
                      >
                        {recommendation.predicted_crowd_level ||
                          "Unknown"}{" "}
                        crowd
                      </span>

                      <span
                        className={`weather-tag ${getWeatherClass(
                          recommendation.weather_suitability,
                        )}`}
                      >
                        Weather{" "}
                        {Math.round(
                          scorePercent(
                            recommendation.weather_suitability,
                          ),
                        )}
                        %
                      </span>

                      <span className="sustainability-tag">
                        🌿{" "}
                        {Math.round(
                          scorePercent(
                            recommendation.sustainability_score,
                          ),
                        )}
                        %
                      </span>
                    </div>

                    <button className={`recommendation-compare-toggle ${comparisonIds.includes(recommendation.destination_id) ? "selected" : ""}`} onClick={() => setComparisonIds((current) => current.includes(recommendation.destination_id) ? current.filter((id) => id !== recommendation.destination_id) : current.length < 3 ? [...current, recommendation.destination_id] : [...current.slice(1), recommendation.destination_id])}>{comparisonIds.includes(recommendation.destination_id) ? "✓ Added to comparison" : "＋ Compare destination"}</button>
                    <div className="recommendation-feedback"><span>Help tune this category</span><button onClick={() => recordPreferenceFeedback(recommendation, 1)}>Like this</button><button onClick={() => recordPreferenceFeedback(recommendation, -1)}>Less like this</button></div>

                    <button
                      className="card-action"
                      onClick={() =>
                        setSelectedRecommendation(
                          recommendation,
                        )
                      }
                    >
                      View AI explanation
                      <span>→</span>
                    </button>
                  </div>
                </article>
              ),
            )}
          </div>
        )}
        {comparedRecommendations.length > 0 && <section className="comparison-panel"><div className="section-heading"><div><span className="eyebrow">SIDE-BY-SIDE TRADE-OFFS</span><h2>Compare your shortlist</h2><p>Up to three destinations. Scores are ranking signals, not probabilities.</p></div><button className="secondary-button" onClick={() => setComparisonIds([])}>Clear</button></div><div className="comparison-grid">{comparedRecommendations.map((item) => <article className="comparison-card" key={item.destination_id}><button className="comparison-remove" aria-label={`Remove ${item.name} from comparison`} onClick={() => setComparisonIds((current) => current.filter((id) => id !== item.destination_id))}>×</button><span className="eyebrow">AI RANK #{item.rank}</span><h3>{item.name}</h3><p>{item.category} · {item.district}</p><div className="comparison-metrics"><span>Overall match<strong>{Math.round(scorePercent(item.demand_aware_score))}%</strong></span><span>Budget fit<strong>{Math.round(scorePercent(item.budget_fit))}%</strong></span><span>Crowd fit<strong>{Math.round(scorePercent(item.predicted_crowd_fit))}%</strong></span><span>Weather fit<strong>{Math.round(scorePercent(item.weather_fit))}%</strong></span><span>Sustainability<strong>{Math.round(scorePercent(item.sustainability_fit))}%</strong></span><span>Est. cost<strong>{formatCurrency(item.estimated_cost_lkr)}</strong></span></div><p className="comparison-reason">{item.explanation}</p></article>)}</div></section>}
      </div>
    );
  }

  /* =======================================================
     PROFILE
  ======================================================= */

  function renderProfile() {
    const interestOptions = [
      "Nature", "Hiking", "Wildlife", "Photography", "Heritage",
      "History", "Culture", "Beach", "Relaxation", "Adventure",
      "Religious", "Birdwatching", "Food", "Marine", "Snorkeling",
      "Surfing", "Water sports", "City", "Education", "Family",
      "Shopping", "Village", "Coastal", "Boat trip", "Rafting",
    ];
    const chosenInterests = profile.interests
      .split(/[;,]/)
      .map((interest) => interest.trim().toLowerCase())
      .filter(Boolean);
    const completion = [
      Boolean(profile.name.trim()),
      Number(profile.budget) > 0,
      Boolean(profile.startingLocation),
      chosenInterests.length > 0,
    ].filter(Boolean).length * 25;

    const toggleInterest = (interest: string) => {
      const current = profile.interests.split(/[;,]/).map((item) => item.trim()).filter(Boolean);
      const exists = current.some((item) => item.toLowerCase() === interest.toLowerCase());
      const next = exists
        ? current.filter((item) => item.toLowerCase() !== interest.toLowerCase())
        : [...current, interest];
      setProfile({ ...profile, interests: next.join(", ") });
    };

    return (
      <div className="page-content">
        <div className="page-header">
          <div>
            <span className="eyebrow">
              TRAVELER PROFILE
            </span>

            <h1>Personalize your travel AI</h1>

            <p>Create a guest traveler profile with your trip preferences. TravelMind saves it locally on this project server and reranks destinations for your profile. No password or email is required.</p>
          </div>
        </div>

        <div className="profile-layout">
          <section className="profile-form-card">
            <div className="section-heading">
              <div>
                <span className="eyebrow">
                  PREFERENCES
                </span>

                <h2>Trip preferences</h2>
                <p>Build a traveler profile that shapes your destination ranking.</p>
              </div>
            </div>

            <div className="profile-completion">
              <div><strong>Profile setup</strong><span>{completion}% complete</span></div>
              <div className="profile-completion-track"><span style={{ width: `${completion}%` }} /></div>
            </div>

            <div className="form-grid">
              <label className="form-field">
                <span>Daily budget (LKR)</span>

                <input
                  type="number"
                  value={profile.budget}
                  onChange={(event) =>
                    setProfile({
                      ...profile,
                      budget: event.target.value,
                    })
                  }
                />
              </label>

              <label className="form-field">
                <span>Your name</span>
                <input
                  value={profile.name}
                  onChange={(event) => setProfile({ ...profile, name: event.target.value })}
                  placeholder="e.g. Sathsarani"
                  maxLength={80}
                />
              </label>

              <label className="form-field">
                <span>Trip duration</span>

                <select
                  value={profile.tripDuration}
                  onChange={(event) =>
                    setProfile({
                      ...profile,
                      tripDuration:
                        event.target.value,
                    })
                  }
                >
                  <option value="1">1 day</option>
                  <option value="2">2 days</option>
                  <option value="3">3 days</option>
                  <option value="4">4 days</option>
                  <option value="5">5 days</option>
                  <option value="7">7 days</option>
                </select>
              </label>

              <label className="form-field">
                <span>Travel style</span>

                <select
                  value={profile.travelStyle}
                  onChange={(event) =>
                    setProfile({
                      ...profile,
                      travelStyle:
                        event.target.value,
                    })
                  }
                >
                  <option>
                    Nature & Adventure
                  </option>
                  <option>
                    Relaxation & Leisure
                  </option>
                  <option>
                    Culture & Heritage
                  </option>
                  <option>
                    Wildlife & Safari
                  </option>
                  <option>Beach & Coastal</option>
                  <option>Budget Explorer</option>
                </select>
              </label>

              <label className="form-field">
                <span>Starting location</span>

                <select
                  value={profile.startingLocation}
                  onChange={(event) =>
                    setProfile({
                      ...profile,
                      startingLocation:
                        event.target.value,
                    })
                  }
                >
                  {["Colombo", "Kandy", "Gampaha", "Galle", "Negombo", "Jaffna", "Trincomalee", "Batticaloa", "Anuradhapura", "Matara", "Kurunegala", "Ratnapura", "Badulla", "Nuwara Eliya"].map((city) => <option key={city}>{city}</option>)}
                </select>
              </label>

              <div className="form-field form-field-wide">
                <span>Choose your interests</span>
                <div className="interest-chip-list">
                  {interestOptions.map((interest) => {
                    const selected = chosenInterests.includes(interest.toLowerCase());
                    return (
                      <button
                        key={interest}
                        type="button"
                        className={`interest-chip${selected ? " selected" : ""}`}
                        aria-pressed={selected}
                        onClick={() => toggleInterest(interest)}
                      >
                        {interest}
                      </button>
                    );
                  })}
                </div>
                <input
                  aria-label="Other interests, separated by commas"
                  value={profile.interests.split(/[;,]/).map((item) => item.trim()).filter((item) => !interestOptions.some((option) => option.toLowerCase() === item.toLowerCase())).join(", ")}
                  onChange={(event) => {
                    const customInterests = event.target.value.split(/[;,]/).map((item) => item.trim()).filter(Boolean);
                    const selectedOptions = interestOptions.filter((option) => chosenInterests.includes(option.toLowerCase()));
                    setProfile({ ...profile, interests: [...selectedOptions, ...customInterests].join(", ") });
                  }}
                  placeholder="Add another interest (optional)"
                />
                <small>Select several interests to improve your match. These tags come from the destination catalog.</small>
              </div>

              <label className="form-field">
                <span>Preferred crowd</span>

                <select
                  value={profile.preferredCrowd}
                  onChange={(event) =>
                    setProfile({
                      ...profile,
                      preferredCrowd:
                        event.target.value,
                    })
                  }
                >
                  <option>Low</option>
                  <option>Medium</option>
                  <option>High</option>
                </select>
              </label>

              <label className="form-field">
                <span>Preferred weather</span>

                <select
                  value={profile.preferredWeather}
                  onChange={(event) =>
                    setProfile({
                      ...profile,
                      preferredWeather:
                        event.target.value,
                    })
                  }
                >
                  <option>Sunny</option>
                  <option>Cloudy</option>
                  <option>Rainy</option>
                  <option>Cool</option>
                </select>
              </label>

              <label className="form-field">
                <span>Travel pace</span>
                <select value={profile.travelPace} onChange={(event) => setProfile({ ...profile, travelPace: event.target.value })}>
                  <option>Relaxed</option>
                  <option>Balanced</option>
                  <option>Active</option>
                </select>
              </label>

              <label className="form-field">
                <span>Maximum distance from start</span>
                <select value={profile.maxDistanceKm} onChange={(event) => setProfile({ ...profile, maxDistanceKm: event.target.value })}>
                  <option>Any distance</option>
                  <option value="100">Within 100 km</option>
                  <option value="250">Within 250 km</option>
                  <option value="500">Within 500 km</option>
                  <option value="800">Within 800 km</option>
                </select>
              </label>

              <label className="form-field form-field-wide">
                <span>Sustainability importance: {Math.round(profile.sustainabilityImportance * 100)}%</span>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={profile.sustainabilityImportance}
                  onChange={(event) => setProfile({ ...profile, sustainabilityImportance: Number(event.target.value) })}
                />
              </label>
            </div>

            <div className="form-actions">
              {selectedUser.startsWith("TRV-") && (
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => {
                    setProfile({ ...defaultProfile });
                    setSelectedUser(users.find((user) => user.startsWith("U")) || "U001");
                    setProfileMessage("");
                    setProfileSaved(false);
                  }}
                >
                  Create another profile
                </button>
              )}
              <button
                className="primary-button"
                onClick={saveProfile}
              >
                {selectedUser.startsWith("TRV-") ? "Update profile & refresh recommendations" : "Create profile & get recommendations"}
              </button>

              {profileSaved && (
                <span className="save-success">
                  Profile saved. Personalized recommendations are ready.
                </span>
              )}
              {profileMessage && !profileSaved && (
                <span className="profile-error" role="alert">
                  {profileMessage}
                </span>
              )}
            </div>
          </section>

          <aside className="profile-insight-card">
            <div className="profile-insight-icon">
              ✦
            </div>

            <span className="eyebrow">
              AI PROFILE
            </span>

            <h2>
              Your recommendation strategy
            </h2>

            <p>
              Your profile shapes the ranking through
              interests, budget, crowd and weather fit,
              sustainability, travel pace and distance
              from your selected starting city.
            </p>

            <div className="profile-insight-list">
              <div>
                <span>Travel pace and length</span>
                <strong>{profile.travelPace} · {profile.tripDuration} days</strong>
              </div>

              <div>
                <span>Search radius</span>
                <strong>{profile.maxDistanceKm === "Any distance" ? "Across Sri Lanka" : `Within ${profile.maxDistanceKm} km`}</strong>
              </div>

              <div>
                <span>Selected interests</span>
                <strong>{chosenInterests.slice(0, 4).map((item) => item[0].toUpperCase() + item.slice(1)).join(" · ") || "Choose at least one"}</strong>
              </div>

              <div>
                <span>Budget</span>
                <strong>
                  {formatCurrency(
                    Number(profile.budget),
                  )}
                </strong>
              </div>

              <div>
                <span>Crowd preference</span>
                <strong>
                  {profile.preferredCrowd}
                </strong>
              </div>

              <div>
                <span>Weather</span>
                <strong>
                  {profile.preferredWeather}
                </strong>
              </div>
            </div>
            <p className="profile-distance-note">Distance limits use approximate straight-line distance from the selected city, not road distance or travel time.</p>
          </aside>
        </div>
      </div>
    );
  }

  /* =======================================================
     CROWD
  ======================================================= */

  function renderSavedPlaces() {
    const savedPlaces = recommendations.filter((item) => savedDestinationIds.includes(item.destination_id));
    return <div className="page-content"><div className="page-header"><div><span className="eyebrow">YOUR TRAVEL COLLECTION</span><h1>Saved places</h1><p>Keep a shortlist of destinations you want to revisit while shaping your Sri Lanka itinerary.</p></div><div className="header-user-card"><span>Saved destinations</span><strong>{savedPlaces.length}</strong></div></div>{savedPlaces.length ? <div className="recommendation-grid">{savedPlaces.map((item) => <article className="recommendation-card" key={item.destination_id}><div className="recommendation-card-visual"><DestinationVisual recommendation={item} /></div><div className="recommendation-card-body"><div className="recommendation-title-row"><div><h3>{item.name}</h3><p>{item.category} · {item.district}</p></div><ScoreCircle value={item.demand_aware_score} size={66} /></div><div className="recommendation-mini-stats"><div><span>Predicted crowd</span><strong>{item.predicted_crowd_level || "Unknown"}</strong></div><div><span>Weather suitability</span><strong>{Math.round(scorePercent(item.weather_suitability))}%</strong></div></div><button className="card-action" onClick={() => setSelectedRecommendation(item)}>View destination details</button><button className="save-destination-button saved" onClick={() => toggleSavedDestination(item.destination_id)}>♥ Remove from saved places</button></div></article>)}</div> : <section className="saved-empty"><span aria-hidden="true">♡</span><h2>Your travel shortlist starts here</h2><p>Save a destination from Recommendations to keep it here. Saved places stay in this browser for the selected traveler.</p><button className="primary-button" onClick={() => setPage("recommendations")}>Explore recommendations</button></section>}</div>;
  }

  function renderCrowd() {
    const averageCrowd =
      recommendations.length > 0
        ? recommendations.reduce(
            (sum, item) =>
              sum +
              (item.predicted_crowd_score || 0),
            0,
          ) / recommendations.length
        : 0;

    const low =
      recommendations.filter((item) =>
        String(
          item.predicted_crowd_level || "",
        )
          .toLowerCase()
          .includes("low"),
      ).length;

    const medium =
      recommendations.filter((item) =>
        String(
          item.predicted_crowd_level || "",
        )
          .toLowerCase()
          .includes("medium"),
      ).length;

    const high =
      recommendations.filter((item) =>
        String(
          item.predicted_crowd_level || "",
        )
          .toLowerCase()
          .includes("high"),
      ).length;
    const crowdItems = recommendations.filter((item) => crowdDisplayFilter === "All" || getCrowdClass(item.predicted_crowd_level) === crowdDisplayFilter.toLowerCase());
    const quieterAlternative = (item: Recommendation) => recommendations
      .filter((candidate) => candidate.destination_id !== item.destination_id && (candidate.predicted_crowd_score ?? 100) < (item.predicted_crowd_score ?? 0))
      .sort((a, b) => Number(b.category === item.category) - Number(a.category === item.category) || (a.predicted_crowd_score ?? 100) - (b.predicted_crowd_score ?? 100))[0];

    return (
      <div className="page-content">
        <div className="page-header">
          <div>
            <span className="eyebrow">
              CROWD INTELLIGENCE
            </span>

            <h1>Predicted destination crowd</h1>

            <p>
              Explore predicted crowd conditions
              incorporated into your demand-aware
              recommendations.
            </p>
          </div>
        </div>

        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-card-icon">
              👥
            </div>

            <span>Average Crowd Score</span>

            <strong>
              {formatNumber(averageCrowd, 1)}
            </strong>

            <small>
              Across recommended destinations
            </small>
          </div>

          <div className="stat-card">
            <div className="stat-card-icon">
              🌿
            </div>

            <span>Low Crowd</span>

            <strong>{low}</strong>

            <small>
              Lower-density recommendations
            </small>
          </div>

          <div className="stat-card">
            <div className="stat-card-icon">
              ◌
            </div>

            <span>Medium Crowd</span>

            <strong>{medium}</strong>

            <small>
              Moderate expected activity
            </small>
          </div>

          <div className="stat-card">
            <div className="stat-card-icon">
              🔥
            </div>

            <span>High Crowd</span>

            <strong>{high}</strong>

            <small>
              Higher expected activity
            </small>
          </div>
        </div>

        <section className="dashboard-section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">
                DESTINATION SIGNALS
              </span>

              <h2>Crowd forecast by recommendation</h2>
            </div>
            <label className="crowd-filter"><span>Show</span><select value={crowdDisplayFilter} onChange={(event) => setCrowdDisplayFilter(event.target.value)}><option value="All">All levels</option><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option></select></label>
          </div>

          <p className="crowd-research-context">Quieter-alternative analysis compares destinations in this personalized shortlist. These scores are not live visitor counts or date-specific forecasts. The current data has no time series, holiday or Poya calendar, school-break schedule, or forecast horizon, so today/tomorrow/7-day alerts are not available.</p>

          <div className="crowd-table">
            {crowdItems.map(
              (recommendation) => (
                <div
                  className="crowd-row"
                  key={`${recommendation.destination_id}-${recommendation.rank}`}
                >
                  <div>
                    <strong>
                      {recommendation.name}
                    </strong>

                    <span>
                      {recommendation.district}
                    </span>
                  </div>

                  <div className="crowd-meter">
                    <div className="crowd-meter-label">
                      <span>
                        {recommendation.predicted_crowd_level ||
                          "Unknown"}
                      </span>

                      <strong>
                        {formatNumber(
                          recommendation.predicted_crowd_score,
                          1,
                        )}
                      </strong>
                    </div>

                    <div className="factor-track">
                      <div
                        className="factor-fill"
                        style={{
                          width: `${Math.min(
                            100,
                            Math.max(
                              0,
                              recommendation.predicted_crowd_score ||
                                0,
                            ),
                          )}%`,
                        }}
                      />
                    </div>
                  </div>
                  <div className="crowd-relative-option">{quieterAlternative(recommendation) ? <button className="crowd-alt-button" onClick={() => { const alternative = quieterAlternative(recommendation); if (alternative) setSelectedRecommendation(alternative); }}>Quieter option: <strong>{quieterAlternative(recommendation)?.name}</strong><small>{quieterAlternative(recommendation)?.category === recommendation.category ? "Same category" : "Different category"} · crowd score lower by {Math.max(0, Math.round((recommendation.predicted_crowd_score ?? 0) - (quieterAlternative(recommendation)?.predicted_crowd_score ?? 0)))} points</small><small>Preference fit {Math.round(scorePercent(quieterAlternative(recommendation)?.preference_score))}% · {recommendation.estimated_cost_lkr && quieterAlternative(recommendation)?.estimated_cost_lkr != null ? (recommendation.estimated_cost_lkr >= (quieterAlternative(recommendation)?.estimated_cost_lkr || 0) ? `estimated cost ~${Math.round((recommendation.estimated_cost_lkr - (quieterAlternative(recommendation)?.estimated_cost_lkr || 0)) / recommendation.estimated_cost_lkr * 100)}% lower` : `estimated cost ~${Math.round(((quieterAlternative(recommendation)?.estimated_cost_lkr || 0) - recommendation.estimated_cost_lkr) / recommendation.estimated_cost_lkr * 100)}% higher`) : "cost comparison unavailable"} · view details</small></button> : <span>No lower-scored option in this shortlist</span>}</div>
                </div>
              ),
            )}
            {crowdItems.length === 0 && <p className="alternative-empty">No recommended destinations match this crowd level.</p>}
          </div>
        </section>

        <section className="itinerary-research-note"><span className="eyebrow">RESEARCH APPLICATION</span><h2>Explainable crowd-aware substitution</h2><p>For each higher-pressure destination, the module surfaces a lower-scored crowd alternative from the same shortlist and prefers the same category when available. This supports a testable question: can relative crowd guidance help travelers choose lower-pressure options while preserving destination relevance?</p><small>Evaluate with shortlist choice rate, preference-fit change, and traveler-rated usefulness. The current data has no visitor counts, timestamps, or live crowd feed.</small></section>
      </div>
    );
  }

  /* =======================================================
     WEATHER
  ======================================================= */

  function renderWeather() {
    const scenarioFit = (item: Recommendation) => {
      if (weatherScenario === "profile") return item.weather_fit ?? item.weather_suitability ?? 0;
      const rain = Math.max(0, Math.min(1, item.weather_rain_risk ?? 0.5));
      const temperature = item.weather_temp_c ?? 25;
      if (weatherScenario === "rainy") return rain;
      if (weatherScenario === "cloudy") return Math.max(0, 1 - Math.abs(rain - 0.5) * 2);
      if (weatherScenario === "cool") return Math.max(0, 1 - Math.abs(temperature - 20) / 20);
      return 1 - rain;
    };
    const weatherSorted = [
      ...recommendations,
    ].sort(
      (a, b) => scenarioFit(b) - scenarioFit(a),
    );
    const scenarioLabels = { profile: `Your profile (${profile.preferredWeather})`, sunny: "Sunny conditions", rainy: "Rainy conditions", cloudy: "Cloudy conditions", cool: "Cool conditions" };
    const leadingDestination = weatherSorted[0];

    return (
      <div className="page-content">
        <div className="page-header">
          <div>
            <span className="eyebrow">
              WEATHER INTELLIGENCE
            </span>

            <h1>Weather-aware recommendations</h1>

            <p>
              Explore how destination ordering changes across weather preference scenarios using the dataset’s temperature and rain-risk signals.
            </p>
          </div>
        </div>

        <div className="weather-hero-card">
          <div className="weather-hero-icon">
            ☀️
          </div>

          <div>
            <span className="eyebrow">
              PREFERRED WEATHER
            </span>

            <h2>
              {profile.preferredWeather}
            </h2>

            <p>
              Compare stored weather signals against a scenario. This is a sensitivity view, not a live forecast.
            </p>
          </div>
          <label className="weather-scenario-control"><span>Explore scenario</span><select value={weatherScenario} onChange={(event) => setWeatherScenario(event.target.value as typeof weatherScenario)}><option value="profile">Use my profile preference</option><option value="sunny">Sunny</option><option value="rainy">Rainy</option><option value="cloudy">Cloudy</option><option value="cool">Cool</option></select></label>
        </div>

        {leadingDestination && <div className="weather-scenario-summary"><span className="eyebrow">TOP FIT · {scenarioLabels[weatherScenario].toUpperCase()}</span><strong>{leadingDestination.name}</strong><span>{Math.round(scorePercent(scenarioFit(leadingDestination)))}% fit from available temperature and rain-risk signals</span></div>}

        <section className="dashboard-section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">
                WEATHER SIGNALS
              </span>

              <h2>Destination suitability</h2>
            </div>
          </div>

          <div className="weather-grid">
            {weatherSorted.map(
              (recommendation) => (
                <div
                  className="weather-card"
                  key={`${recommendation.destination_id}-${recommendation.rank}`}
                >
                  <DestinationVisual
                    recommendation={
                      recommendation
                    }
                  />

                  <div className="weather-card-content">
                    <h3>
                      {recommendation.name}
                    </h3>

                    <p>
                      {recommendation.district}
                    </p>

                    <div className="weather-main-stat">
                      <strong>
                        {recommendation.weather_temp_c !==
                        null
                          ? `${formatNumber(
                              recommendation.weather_temp_c,
                              1,
                            )}°C`
                          : "N/A"}
                      </strong>

                      <span>
                        Temperature
                      </span>
                    </div>

                    <div className="weather-card-row">
                      <span>
                        Suitability
                      </span>

                      <strong>
                      {Math.round(scorePercent(scenarioFit(recommendation)))}
                        %
                      </strong>
                    </div>

                    <div className="weather-card-row">
                      <span>
                        Rain risk
                      </span>

                      <strong>
                        {recommendation.weather_rain_risk !==
                        null
                          ? `${Math.round(scorePercent(recommendation.weather_rain_risk))}%`
                          : "N/A"}
                      </strong>
                    </div>
                  </div>
                </div>
              ),
            )}
          </div>
        </section>
        <section className="itinerary-research-note"><span className="eyebrow">RESEARCH APPLICATION</span><h2>Weather-preference sensitivity analysis</h2><p>Scenario switching reuses the available rain-risk and temperature fields to show how the shortlist changes under sunny, rainy, cloudy, or cool preferences. Compare rank stability and destination changes across scenarios to study how weather preferences affect recommendation outcomes.</p><small>Weather records have no forecast date or update timestamp; results describe the current dataset signals and should not be interpreted as trip-date forecasts.</small></section>
      </div>
    );
  }

  /* =======================================================
     ANALYTICS
  ======================================================= */

  function renderAnalytics() {
    const top =
      recommendations.length > 0
        ? recommendations[0]
        : null;

    const averageCrowd =
      recommendations.length > 0
        ? recommendations.reduce(
            (sum, item) =>
              sum +
              (item.predicted_crowd_score || 0),
            0,
          ) / recommendations.length
        : 0;

    const averageCost =
      recommendations.length > 0
        ? recommendations.reduce(
            (sum, item) =>
              sum +
              (item.estimated_cost_lkr || 0),
            0,
          ) / recommendations.length
        : 0;

    return (
      <div className="page-content">
        <div className="page-header">
          <div>
            <span className="eyebrow">
              TRAVEL ANALYTICS
            </span>

            <h1>Recommendation insights</h1>

            <p>
              Understand the destination signals used
              across your current AI recommendation set.
            </p>
          </div>
        </div>

        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-card-icon">
              ✦
            </div>

            <span>Top Match</span>

            <strong>
              {top
                ? `${Math.round(
                    scorePercent(
                      top.demand_aware_score,
                    ),
                  )}%`
                : "N/A"}
            </strong>

            <small>
              {top?.name || "No recommendation"}
            </small>
          </div>

          <div className="stat-card">
            <div className="stat-card-icon">
              💰
            </div>

            <span>Average Cost</span>

            <strong>
              {formatCurrency(averageCost)}
            </strong>

            <small>
              Across current recommendations
            </small>
          </div>

          <div className="stat-card">
            <div className="stat-card-icon">
              👥
            </div>

            <span>Average Crowd</span>

            <strong>
              {formatNumber(averageCrowd, 1)}
            </strong>

            <small>
              Predicted crowd score
            </small>
          </div>

          <div className="stat-card">
            <div className="stat-card-icon">
              🌱
            </div>

            <span>Sustainability</span>

            <strong>
              {Math.round(
                averageSustainability,
              )}
              %
            </strong>

            <small>
              Average destination score
            </small>
          </div>
        </div>

        <section className="dashboard-section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">
                MODEL SIGNALS
              </span>

              <h2>Recommendation factor analysis</h2>
            </div>
          </div>

          <div className="analytics-factor-grid">
            <div className="analytics-card">
              <h3>Preference Fit</h3>

              <FactorBar
                label="Average preference"
                value={
                  recommendations.length
                    ? recommendations.reduce(
                        (sum, item) =>
                          sum +
                          (item.preference_score ||
                            0),
                        0,
                      ) /
                      recommendations.length
                    : 0
                }
              />
            </div>

            <div className="analytics-card">
              <h3>Budget Fit</h3>

              <FactorBar
                label="Average budget"
                value={
                  recommendations.length
                    ? recommendations.reduce(
                        (sum, item) =>
                          sum +
                          (item.budget_fit || 0),
                        0,
                      ) /
                      recommendations.length
                    : 0
                }
              />
            </div>

            <div className="analytics-card">
              <h3>Crowd Fit</h3>

              <FactorBar
                label="Average crowd suitability"
                value={
                  recommendations.length
                    ? recommendations.reduce(
                        (sum, item) =>
                          sum +
                          (item.predicted_crowd_fit ||
                            0),
                        0,
                      ) /
                      recommendations.length
                    : 0
                }
              />
            </div>

            <div className="analytics-card">
              <h3>Weather Fit</h3>

              <FactorBar
                label="Average weather suitability"
                value={
                  recommendations.length
                    ? recommendations.reduce(
                        (sum, item) =>
                          sum +
                          (item.weather_fit ||
                            0),
                        0,
                      ) /
                      recommendations.length
                    : 0
                }
              />
            </div>
          </div>
        </section>
      </div>
    );
  }

  /* =======================================================
     EVALUATION
  ======================================================= */

  function renderAssistant() {
    const suggestedQuestions = [
      `Draft a ${profile.tripDuration || "short"}-day high-level itinerary using my highest-ranked destinations. Use only the supplied evidence, explain why each destination fits, and clearly state what schedule, activity, distance, and cost details are unavailable.`,
      "Why is my highest-ranked destination recommended?",
      "Compare the top two destinations for crowd and weather fit.",
      "Which recommendation best matches my budget?",
    ];

    return (
      <div className="page-content assistant-page">
        <div className="page-header">
          <div>
            <span className="eyebrow">EVIDENCE-GROUNDED XAI</span>
            <h1>Plan with your recommendations</h1>
            <p>Get a high-level itinerary or ask why places were recommended. Answers use the current profile and ranked destination records, with evidence you can inspect.</p>
          </div>
          <div className="assistant-user-badge"><AppIcon name="user" /><span>Traveler <strong>{profile.name || selectedUser}</strong></span></div>
        </div>

        <div className="assistant-layout">
          <section className="assistant-panel">
            <div className="assistant-panel-heading">
              <div className="assistant-bot-icon"><AppIcon name="sparkle" /></div>
              <div><strong>TravelMind research assistant</strong><span>OpenAI · answers limited to supplied evidence</span></div>
              <button className="secondary-button" onClick={() => {
                setAssistantMessages([{ role: "assistant", content: `I’m ready to explain recommendations for ${selectedUser}. Answers use the current profile and recommendation evidence.` }]);
                setAssistantError("");
              }}>Clear chat</button>
            </div>

            <div className="assistant-messages" aria-live="polite" aria-relevant="additions text">
              {assistantMessages.map((message, index) => (
                <article className={`assistant-message ${message.role}`} key={`${message.role}-${index}`}>
                  <div className="assistant-message-avatar">{message.role === "assistant" ? <AppIcon name="sparkle" /> : <AppIcon name="user" />}</div>
                  <div className="assistant-message-body">
                    <span className="assistant-message-label">{message.role === "assistant" ? "TravelMind" : "You"}</span>
                    <p>{message.content}</p>
                    {message.sources && message.sources.length > 0 && (
                      <details className="assistant-sources">
                        <summary>Evidence used ({message.sources.length})</summary>
                        <div className="assistant-source-list">
                          {message.sources.map((source) => (
                            <div className="assistant-source" key={source.id}>
                              <strong><span>{source.id}</span> {source.title}</strong>
                              <p>{source.details}</p>
                            </div>
                          ))}
                        </div>
                      </details>
                    )}
                    {message.role === "assistant" && message.latencyMs !== undefined && (
                      <span className="assistant-response-meta">{message.sources?.length || 0} evidence sources · {message.latencyMs} ms</span>
                    )}
                  </div>
                </article>
              ))}
              {assistantLoading && <div className="assistant-thinking"><span /> Checking recommendation evidence…</div>}
            </div>

            {assistantError && <div className="assistant-error" role="alert">{assistantError}</div>}

            {assistantMessages.length <= 1 && (
              <div className="assistant-prompts">
                <span>Try asking</span>
                {suggestedQuestions.map((question) => (
                  <button key={question} onClick={() => void askAssistant(question)} disabled={assistantLoading}>{question}</button>
                ))}
              </div>
            )}

            <form className="assistant-composer" onSubmit={(event) => {
              event.preventDefault();
              void askAssistant();
            }}>
              <textarea
                value={assistantInput}
                onChange={(event) => setAssistantInput(event.target.value)}
                placeholder="Ask why a place was recommended…"
                maxLength={1200}
                rows={2}
                aria-label="Ask the recommendation assistant"
              />
              <button className="primary-button" type="submit" disabled={assistantLoading || !assistantInput.trim()}>
                {assistantLoading ? "Thinking…" : "Ask"}
              </button>
            </form>
            <p className="assistant-disclaimer">Itinerary suggestions use ranked destinations only. They do not include verified activity schedules, routes, travel times, or total trip costs. Scores describe ranking signals, not probabilities.</p>
          </section>

          <aside className="assistant-context-card">
            <span className="eyebrow">CURRENT EVIDENCE</span>
            <h2>What the assistant can use</h2>
            <div className="assistant-context-item"><AppIcon name="user" /><div><strong>Traveler profile</strong><span>{profile.travelStyle} · {profile.preferredCrowd} crowd · {profile.preferredWeather}</span></div></div>
            <div className="assistant-context-item"><AppIcon name="pin" /><div><strong>{recommendations.length} ranked destinations</strong><span>{recommendations.slice(0, 3).map((item) => item.name).join(" · ") || "Waiting for recommendation data"}</span></div></div>
            <div className="assistant-context-note"><strong>Grounding limit</strong><p>The current dataset has scores, predicted crowd and weather fields, but no verified opening hours, route distances, activities, or schedules. The assistant will not invent those details.</p></div>
          </aside>
        </div>
      </div>
    );
  }

  function renderItinerary() {
    return (
      <div className="page-content itinerary-page">
        <div className="page-header">
          <div>
            <span className="eyebrow">PERSONALIZED TRIP PLANNER</span>
            <h1>Your Sri Lanka itinerary</h1>
            <p>Build a day-by-day draft from your ranked recommendations, trip length, and preferred travel pace.</p>
          </div>
          <div className="assistant-user-badge"><AppIcon name="user" /><span>Traveler <strong>{profile.name || selectedUser}</strong></span></div>
        </div>

        <section className="itinerary-overview">
          <div><span className="eyebrow">TRIP SETTINGS</span><strong>{profile.tripDuration} days</strong><span>{profile.travelPace} pace · starting in {profile.startingLocation}</span></div>
          <div><span className="eyebrow">PREFERENCES</span><strong>{profile.interests.split(/[;,]/).filter(Boolean).length} interests</strong><span>{profile.preferredCrowd} crowd · {profile.preferredWeather} weather</span></div>
          <button className="primary-button" onClick={() => void loadItinerary()} disabled={itineraryLoading || recommendations.length === 0}>
            {itineraryLoading ? "Planning…" : itinerary ? "Refresh itinerary" : "Build my itinerary"}
          </button>
        </section>


        {itinerary && <section className="itinerary-explainer"><span className="eyebrow">HOW THIS DRAFT WAS BUILT</span><h2>A plan shaped around your travel style</h2><p>The planner distributes your highest-ranked destinations across {profile.tripDuration} days, groups stops by area, and considers your {profile.travelPace.toLowerCase()} pace, preferred distance, and travel interests. Each stop includes the recommendation reason and an estimated visit time so you can see why it made the plan.</p><div className="itinerary-caveat"><strong>Planning note</strong><span>Costs and visit times are estimates. Distances are straight-line approximations from your start, not road routes or travel times. Confirm transport, opening hours, weather, and current prices before you set out.</span></div><div className="itinerary-share-actions"><button className="secondary-button" onClick={downloadItinerary}>Download HTML</button><button className="secondary-button" onClick={downloadItineraryPdf}>Download PDF</button><button className="primary-button" onClick={() => void shareItinerary()}>Share plan</button></div>{itineraryShareMessage && <p className="itinerary-share-message" role="status">{itineraryShareMessage}</p>}</section>}
        {itinerary && <section className="itinerary-alternatives"><div className="section-heading"><div><span className="eyebrow">PERSONALIZE YOUR DRAFT</span><h2>Find an alternative destination</h2><p>Search your ranked matches, compare estimated time and fit, then add a stop to a day.</p></div></div><div className="alternative-controls"><label className="form-field"><span>Search ranked places</span><input type="search" value={alternativeSearch} onChange={(event) => setAlternativeSearch(event.target.value)} placeholder="Try Ella, beach, or wildlife" /></label><label className="form-field"><span>Add to day</span><select value={alternativeDay} onChange={(event) => setAlternativeDay(Number(event.target.value))}>{itinerary.days.map((day, index) => <option key={day.day} value={index}>Day {day.day} · {day.area}</option>)}</select></label></div><p className="alternative-day-load">Selected day currently has about {itinerary.days[alternativeDay]?.estimated_visit_hours ?? 0} visit hours. Adding a destination updates this estimate; check the day’s pace before you travel.</p>{alternativeSearch.trim() && <div className="alternative-results">{recommendations.filter((item) => !itinerary.days.some((day) => day.stops.some((stop) => stop.destination_id === item.destination_id))).filter((item) => `${item.name} ${item.category} ${item.district}`.toLowerCase().includes(alternativeSearch.trim().toLowerCase())).slice(0, 6).map((item) => <article className="alternative-result" key={item.destination_id}><div><strong>{item.name}</strong><span>{item.category} · {item.district}</span><small>{item.duration_hours ?? 2} estimated visit hours · {formatCurrency(item.estimated_cost_lkr)} · {Math.round(scorePercent(item.demand_aware_score))}% profile match</small><p>{item.explanation || "Included in your personalized ranking."}</p></div><button className="secondary-button" onClick={() => addAlternativeToDay(item)}>Add to day {alternativeDay + 1}</button></article>)}{recommendations.filter((item) => !itinerary.days.some((day) => day.stops.some((stop) => stop.destination_id === item.destination_id))).filter((item) => `${item.name} ${item.category} ${item.district}`.toLowerCase().includes(alternativeSearch.trim().toLowerCase())).length === 0 && <p className="alternative-empty">No unplanned ranked destinations match that search. Try another name, category, or district.</p>}</div>}</section>}
        {itineraryError && <div className="assistant-error" role="alert">{itineraryError}</div>}
        {itineraryLoading && <div className="loading-state">Arranging your top-ranked destinations…</div>}
        {!itineraryLoading && !itinerary && (
          <section className="itinerary-empty">
            <div className="profile-insight-icon"><AppIcon name="compass" /></div>
            <h2>Ready when you are</h2>
            <p>We’ll distribute your personalized destinations across your trip days and keep each day within your preferred pace where possible.</p>
            <button className="primary-button" onClick={() => void loadItinerary()} disabled={recommendations.length === 0}>Build my itinerary</button>
          </section>
        )}
        {itinerary && !itineraryLoading && (
          <>
            <div className="itinerary-days">
              {itinerary.days.map((day) => (
                <section className="itinerary-day-card" key={day.day}>
                  <div className="itinerary-day-heading">
                    <div><span className="eyebrow">DAY {day.day}</span><h2>{day.area}</h2></div>
                    <span className="itinerary-duration">~{day.estimated_visit_hours} visit hours</span>
                  </div>
                  {day.stops.length === 0 ? <p className="itinerary-no-stops">No destination fit this day’s pace and distance settings.</p> : (
                    <div className="itinerary-stops">
                      {day.stops.map((stop) => (
                        <article className="itinerary-stop" key={stop.destination_id}>
                          <span className="itinerary-stop-rank">#{stop.rank}</span>
                          <div className="itinerary-stop-main">
                            <h3>{stop.name}</h3>
                            <p>{stop.district} · estimated visit {stop.visit_duration_hours} hours · {formatCurrency(stop.estimated_cost_lkr)}</p>
                            <small>{stop.recommendation_reason}</small>
                          </div>
                          {stop.straight_line_distance_km != null && <span className="itinerary-distance">~{Math.round(stop.straight_line_distance_km)} km from start</span>}
                        </article>
                      ))}
                    </div>

                  )}
                </section>
              ))}
            </div>
            <p className="itinerary-note">{itinerary.planning_note}</p>
            <section className="itinerary-research-note"><span className="eyebrow">RESEARCH NOVELTY · PROPOSED CONTRIBUTION</span><h2>Explainable, traveler-in-the-loop itinerary adaptation</h2><p>Beyond one-shot ranking, this prototype lets a traveler search alternatives and add a selected destination to a chosen day while exposing its personalized match, estimated time, cost, and recommendation rationale. A research evaluation can compare this interactive workflow with a fixed top-ranked itinerary and measure preference alignment, accepted plan edits, estimated time and budget changes, and traveler-rated usefulness.</p><small>These are proposed evaluation dimensions; effectiveness and novelty claims require comparison with prior work and empirical validation.</small></section>
          </>
        )}
      </div>
    );
  }

  function renderAccount() {
    return (
      <div className="page-content account-page">
        <div className="page-header">
          <div>
            <span className="eyebrow">TRAVELMIND ACCOUNT</span>
            <h1>{authSession ? "Your travel account" : "Sign in or create an account"}</h1>
            <p>Access your saved traveler profiles and recommendations when you return to the app.</p>
          </div>
        </div>

        {authSession ? (
          <section className="account-card">
            <div className="account-avatar"><AppIcon name="user" /></div>
            <div className="account-details">
              <span className="eyebrow">SIGNED IN</span>
              <h2>{authSession.account.email}</h2>
              <p>Traveler profiles linked to this account are listed below.</p>
            </div>
            <button className="secondary-button" onClick={signOut}>Sign out</button>
            <div className="account-profile-list">
              <div className="section-heading"><div><span className="eyebrow">SAVED PROFILES</span><h2>Your travelers</h2></div></div>
              {accountProfiles.length === 0 ? (
                <div className="account-empty"><p>No traveler profiles are linked yet.</p><button className="primary-button" onClick={() => setPage("profile")}>Create a traveler profile</button></div>
              ) : accountProfiles.map((item) => (
                <button className="account-profile-row" key={item.user_id} onClick={() => { setSelectedUser(item.user_id); setPage("recommendations"); }}>
                  <span className="account-avatar small"><AppIcon name="user" /></span>
                  <span><strong>{item.name}</strong><small>{item.user_id}</small></span>
                  <span>Open recommendations →</span>
                </button>
              ))}
            </div>
          </section>
        ) : (
          <section className="account-card account-auth-card">
            <div className="account-auth-heading">
              <span className="eyebrow">{authMode === "register" ? "NEW TO TRAVELMIND" : "WELCOME BACK"}</span>
              <h2>{authMode === "register" ? "Create your account" : "Sign in to your account"}</h2>
              <p>{authMode === "register" ? "Use an email and a password with at least 10 characters." : "Sign in to access your linked traveler profiles."}</p>
            </div>
            <form className="account-auth-form" onSubmit={(event) => { event.preventDefault(); void submitAccountAuth(); }}>
              <label className="form-field"><span>Email</span><input type="email" autoComplete="email" required maxLength={254} value={authEmail} onChange={(event) => setAuthEmail(event.target.value)} placeholder="you@example.com" /></label>
              <label className="form-field"><span>Password</span><input type="password" autoComplete={authMode === "register" ? "new-password" : "current-password"} required minLength={authMode === "register" ? 10 : 1} maxLength={128} value={authPassword} onChange={(event) => setAuthPassword(event.target.value)} placeholder={authMode === "register" ? "At least 10 characters" : "Your password"} /></label>
              {authMode === "register" && <div className="signup-profile-fields"><div className="signup-profile-heading"><span className="eyebrow">TRAVELER PROFILE</span><strong>Personalize your recommendations</strong><span>Your account and profile will be created together.</span></div><label className="form-field"><span>Your name</span><input required maxLength={80} autoComplete="name" value={profile.name} onChange={(event) => setProfile({ ...profile, name: event.target.value })} placeholder="e.g. Sathsarani" /></label><label className="form-field"><span>Daily budget (LKR)</span><input type="number" min="1" required value={profile.budget} onChange={(event) => setProfile({ ...profile, budget: event.target.value })} /></label><label className="form-field"><span>Starting location</span><input required value={profile.startingLocation} onChange={(event) => setProfile({ ...profile, startingLocation: event.target.value })} placeholder="Colombo" /></label><label className="form-field"><span>Trip duration (days)</span><input type="number" min="1" max="30" required value={profile.tripDuration} onChange={(event) => setProfile({ ...profile, tripDuration: event.target.value })} /></label><label className="form-field form-field-wide"><span>Interests</span><input required value={profile.interests} onChange={(event) => setProfile({ ...profile, interests: event.target.value })} placeholder="Nature, hiking, wildlife" /></label></div>}
              {authMode === "register" && selectedUser.startsWith("TRV-") && <p className="account-claim-note">Your current guest profile ({profile.name || selectedUser}) will be linked to this account.</p>}
              {authMessage && <p className="account-message" role="status">{authMessage}</p>}
              <button className="primary-button" type="submit" disabled={authLoading}>{authLoading ? "Please wait…" : authMode === "register" ? "Create account & profile" : "Sign in"}</button>
            </form>
            <button className="account-mode-toggle" onClick={() => { setAuthMode(authMode === "register" ? "login" : "register"); setAuthMessage(""); }}>
              {authMode === "register" ? "Already have an account? Sign in" : "New to TravelMind? Create an account"}
            </button>
            <p className="account-security-note">This prototype stores account data on the project server. Password reset and email verification are not configured yet.</p>
          </section>
        )}
      </div>
    );
  }

  function renderEvaluation() {
    if (evaluationLoading) {
      return (
        <div className="page-content">
          <div className="page-header">
            <div>
              <span className="eyebrow">
                MODEL EVALUATION
              </span>

              <h1>
                Recommendation model evaluation
              </h1>

              <p>
                Loading validated research results...
              </p>
            </div>
          </div>

          <div className="loading-state">
            Loading evaluation metrics...
          </div>
        </div>
      );
    }

    if (evaluationError) {
      return (
        <div className="page-content">
          <div className="page-header">
            <div>
              <span className="eyebrow">
                MODEL EVALUATION
              </span>

              <h1>
                Recommendation model evaluation
              </h1>

              <p>
                Compare the baseline models with the
                proposed Demand-Aware AI model.
              </p>
            </div>

            <button
              className="primary-button"
              onClick={loadEvaluation}
            >
              Refresh evaluation
            </button>
          </div>

          <div className="error-banner">
            <div>
              <strong>
                Evaluation data unavailable
              </strong>

              <p>{evaluationError}</p>
            </div>

            <button
              onClick={loadEvaluation}
            >
              Retry
            </button>
          </div>
        </div>
      );
    }

    if (!evaluation) {
      return (
        <div className="page-content">
          <div className="empty-state">
            <div className="empty-state-icon">
              📊
            </div>

            <h3>No evaluation data</h3>

            <p>
              Click below to load the validated model
              evaluation results.
            </p>

            <button
              className="primary-button"
              onClick={loadEvaluation}
            >
              Load evaluation
            </button>
          </div>
        </div>
      );
    }

    const stats =
      evaluation.demand_aware_statistics;

    const proposedModel =
      evaluation.models.find(
        (model) => model.id === "PROPOSED",
      );

    const b5Model =
      evaluation.models.find(
        (model) => model.id === "B5",
      );

    return (
      <div className="page-content">
        <div className="page-header">
          <div>
            <span className="eyebrow">
              RESEARCH MODEL EVALUATION
            </span>

            <h1>
              Recommendation model evaluation
            </h1>

            <p>
              Validated comparison of the baseline
              recommendation models and the proposed
              Demand-Aware AI approach.
            </p>
          </div>

          <div className="report-actions">
            <button
              className="secondary-button"
              onClick={downloadResearchReport}
            >
              Download research report
            </button>
            <button
              className="secondary-button"
              onClick={loadEvaluation}
              disabled={evaluationLoading}
            >
              {evaluationLoading
                ? "Refreshing..."
                : "Refresh evaluation"}
            </button>
          </div>
        </div>

        {/* =================================================
            MODEL OVERVIEW
        ================================================= */}

        <section className="evaluation-hero">
          <div>
            <span className="eyebrow">
              EXPERIMENTAL RESULTS
            </span>

            <h2>
              Benchmarking recommendation approaches
            </h2>

            <p>
              The evaluation compares general,
              content-based, context-aware, hybrid
              and demand-aware recommendation
              approaches using Precision@5, Recall@5
              and NDCG@5.
            </p>
          </div>

          <div className="evaluation-hero-stat">
            <span>Validated recommendations</span>

            <strong>
              {Math.round(
                stats.total_recommendations,
              )}
            </strong>

            <small>
              across{" "}
              {Math.round(stats.unique_users)}{" "}
              travelers
            </small>
          </div>
        </section>

        {/* =================================================
            MODEL CARDS
        ================================================= */}

        <section className="dashboard-section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">
                MODEL COMPARISON
              </span>

              <h2>
                Precision, recall and ranking quality
              </h2>
            </div>
          </div>

          <div className="evaluation-grid">
            {evaluation.models.map((model) => {
              const isProposed =
                model.id === "PROPOSED";

              return (
                <div
                  className={`evaluation-card ${
                    isProposed
                      ? "evaluation-card-proposed"
                      : ""
                  }`}
                  key={model.id}
                >
                  <div className="evaluation-model-header">
                    <div>
                      <span className="evaluation-model-id">
                        {model.id}
                      </span>

                      <h3>{model.name}</h3>
                    </div>

                    {isProposed && (
                      <span className="evaluation-proposed-badge">
                        Proposed
                      </span>
                    )}
                  </div>

                  <p>
                    {isProposed
                      ? "Preference + context + crowd + sustainability + demand-aware ranking."
                      : model.id === "B1"
                        ? "Generic recommendation baseline."
                        : model.id === "B2"
                          ? "Destination content similarity."
                          : model.id === "B3"
                            ? "Traveler context and destination signals."
                            : "Combined recommendation signals."}
                  </p>

                  <div className="evaluation-tags">
                    <span>
                      Precision@5
                    </span>

                    <span>
                      Recall@5
                    </span>

                    <span>NDCG@5</span>
                  </div>

                  <div className="evaluation-metrics">
                    <div className="evaluation-metric">
                      <span>
                        Precision@5
                      </span>

                      <strong>
                        {(
                          model.precision_at_5 *
                          100
                        ).toFixed(2)}
                        %
                      </strong>
                    </div>

                    <div className="evaluation-metric">
                      <span>
                        Recall@5
                      </span>

                      <strong>
                        {(
                          model.recall_at_5 * 100
                        ).toFixed(2)}
                        %
                      </strong>
                    </div>

                    <div className="evaluation-metric">
                      <span>NDCG@5</span>

                      <strong>
                        {(
                          model.ndcg_at_5 * 100
                        ).toFixed(2)}
                        %
                      </strong>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* =================================================
            METRIC TABLE
        ================================================= */}

        <section className="dashboard-section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">
                BENCHMARK TABLE
              </span>

              <h2>Model performance at K = 5</h2>
            </div>
          </div>

          <div
            style={{
              width: "100%",
              overflowX: "auto",
              borderRadius: "18px",
              border: "1px solid #e5ece8",
              background: "#ffffff",
            }}
          >
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                minWidth: "720px",
              }}
            >
              <thead>
                <tr>
                  {[
                    "Model",
                    "Precision@5",
                    "Recall@5",
                    "NDCG@5",
                  ].map((heading) => (
                    <th
                      key={heading}
                      style={{
                        padding: "18px 20px",
                        textAlign:
                          heading === "Model"
                            ? "left"
                            : "right",
                        borderBottom:
                          "1px solid #e5ece8",
                        fontSize: "13px",
                        textTransform:
                          "uppercase",
                        letterSpacing:
                          "0.06em",
                        color: "#718078",
                        background:
                          "#f8fbf9",
                      }}
                    >
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>

              <tbody>
                {evaluation.models.map(
                  (model) => (
                    <tr
                      key={`table-${model.id}`}
                    >
                      <td
                        style={{
                          padding:
                            "18px 20px",
                          borderBottom:
                            "1px solid #edf2ef",
                          fontWeight: 700,
                          color: "#173b2d",
                        }}
                      >
                        <div>
                          <strong>
                            {model.id}
                          </strong>

                          <div
                            style={{
                              marginTop:
                                "4px",
                              fontWeight: 500,
                              color:
                                "#718078",
                            }}
                          >
                            {model.name}
                          </div>
                        </div>
                      </td>

                      <td
                        style={{
                          padding:
                            "18px 20px",
                          textAlign: "right",
                          borderBottom:
                            "1px solid #edf2ef",
                          fontWeight: 700,
                        }}
                      >
                        {(
                          model.precision_at_5 *
                          100
                        ).toFixed(2)}
                        %
                      </td>

                      <td
                        style={{
                          padding:
                            "18px 20px",
                          textAlign: "right",
                          borderBottom:
                            "1px solid #edf2ef",
                          fontWeight: 700,
                        }}
                      >
                        {(
                          model.recall_at_5 *
                          100
                        ).toFixed(2)}
                        %
                      </td>

                      <td
                        style={{
                          padding:
                            "18px 20px",
                          textAlign: "right",
                          borderBottom:
                            "1px solid #edf2ef",
                          fontWeight: 700,
                        }}
                      >
                        {(
                          model.ndcg_at_5 * 100
                        ).toFixed(2)}
                        %
                      </td>
                    </tr>
                  ),
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* =================================================
            NDCG BY K
        ================================================= */}

        <section className="dashboard-section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">
                RANKING QUALITY
              </span>

              <h2>NDCG by recommendation depth</h2>

              <p>
                Comparing the B5 semantic model with
                the final Demand-Aware model across
                different recommendation depths.
              </p>
            </div>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns:
                "repeat(auto-fit, minmax(210px, 1fr))",
              gap: "18px",
              marginBottom: "24px",
            }}
          >
            {evaluation.ndcg_by_k.map(
              (point) => {
                const change =
                  point.ndcg_change * 100;

                return (
                  <div
                    key={point.k}
                    className="analytics-card"
                    style={{
                      border:
                        "1px solid #e5ece8",
                      borderRadius: "18px",
                      padding: "22px",
                      background:
                        "#ffffff",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent:
                          "space-between",
                        alignItems:
                          "center",
                        marginBottom:
                          "18px",
                      }}
                    >
                      <span
                        className="eyebrow"
                      >
                        TOP {point.k}
                      </span>

                      <strong
                        style={{
                          color:
                            change >= 0
                              ? "#00b894"
                              : "#b45309",
                        }}
                      >
                        {change >= 0
                          ? "+"
                          : ""}
                        {change.toFixed(2)} pp
                      </strong>
                    </div>

                    <div
                      style={{
                        display: "grid",
                        gap: "12px",
                      }}
                    >
                      <div>
                        <span
                          style={{
                            display:
                              "block",
                            fontSize:
                              "12px",
                            color:
                              "#718078",
                            marginBottom:
                              "4px",
                          }}
                        >
                          B5 Semantic
                        </span>

                        <strong
                          style={{
                            fontSize:
                              "25px",
                            color:
                              "#173b2d",
                          }}
                        >
                          {(
                            point.b5_ndcg *
                            100
                          ).toFixed(2)}
                          %
                        </strong>
                      </div>

                      <div>
                        <span
                          style={{
                            display:
                              "block",
                            fontSize:
                              "12px",
                            color:
                              "#718078",
                            marginBottom:
                              "4px",
                          }}
                        >
                          Demand-Aware
                        </span>

                        <strong
                          style={{
                            fontSize:
                              "25px",
                            color:
                              "#00b894",
                          }}
                        >
                          {(
                            point.demand_aware_ndcg *
                            100
                          ).toFixed(2)}
                          %
                        </strong>
                      </div>
                    </div>
                  </div>
                );
              },
            )}
          </div>

          <div
            style={{
              width: "100%",
              overflowX: "auto",
              borderRadius: "18px",
              border: "1px solid #e5ece8",
              background: "#ffffff",
            }}
          >
            <table
              style={{
                width: "100%",
                borderCollapse:
                  "collapse",
                minWidth: "650px",
              }}
            >
              <thead>
                <tr>
                  <th
                    style={{
                      padding:
                        "18px 20px",
                      textAlign: "left",
                      borderBottom:
                        "1px solid #e5ece8",
                      color: "#718078",
                      background:
                        "#f8fbf9",
                    }}
                  >
                    K
                  </th>

                  <th
                    style={{
                      padding:
                        "18px 20px",
                      textAlign: "right",
                      borderBottom:
                        "1px solid #e5ece8",
                      color: "#718078",
                      background:
                        "#f8fbf9",
                    }}
                  >
                    B5 NDCG
                  </th>

                  <th
                    style={{
                      padding:
                        "18px 20px",
                      textAlign: "right",
                      borderBottom:
                        "1px solid #e5ece8",
                      color: "#718078",
                      background:
                        "#f8fbf9",
                    }}
                  >
                    Demand-Aware NDCG
                  </th>

                  <th
                    style={{
                      padding:
                        "18px 20px",
                      textAlign: "right",
                      borderBottom:
                        "1px solid #e5ece8",
                      color: "#718078",
                      background:
                        "#f8fbf9",
                    }}
                  >
                    Change
                  </th>
                </tr>
              </thead>

              <tbody>
                {evaluation.ndcg_by_k.map(
                  (point) => {
                    const change =
                      point.ndcg_change *
                      100;

                    return (
                      <tr
                        key={`ndcg-${point.k}`}
                      >
                        <td
                          style={{
                            padding:
                              "18px 20px",
                            borderBottom:
                              "1px solid #edf2ef",
                            fontWeight: 800,
                            color:
                              "#173b2d",
                          }}
                        >
                          {point.k}
                        </td>

                        <td
                          style={{
                            padding:
                              "18px 20px",
                            textAlign:
                              "right",
                            borderBottom:
                              "1px solid #edf2ef",
                          }}
                        >
                          {(
                            point.b5_ndcg *
                            100
                          ).toFixed(2)}
                          %
                        </td>

                        <td
                          style={{
                            padding:
                              "18px 20px",
                            textAlign:
                              "right",
                            borderBottom:
                              "1px solid #edf2ef",
                            fontWeight: 700,
                          }}
                        >
                          {(
                            point.demand_aware_ndcg *
                            100
                          ).toFixed(2)}
                          %
                        </td>

                        <td
                          style={{
                            padding:
                              "18px 20px",
                            textAlign:
                              "right",
                            borderBottom:
                              "1px solid #edf2ef",
                            fontWeight: 700,
                            color:
                              change >= 0
                                ? "#00b894"
                                : "#b45309",
                          }}
                        >
                          {change >= 0
                            ? "+"
                            : ""}
                          {change.toFixed(
                            2,
                          )}{" "}
                          pp
                        </td>
                      </tr>
                    );
                  },
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* =================================================
            DEMAND-AWARE STATISTICS
        ================================================= */}

        <section className="dashboard-section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">
                DEMAND-AWARE SYSTEM
              </span>

              <h2>Validated system statistics</h2>

              <p>
                Summary statistics generated from the
                final demand-aware recommendation
                pipeline.
              </p>
            </div>
          </div>

          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-card-icon">
                📌
              </div>

              <span>
                Total Recommendations
              </span>

              <strong>
                {Math.round(
                  stats.total_recommendations,
                )}
              </strong>

              <small>
                Final validated recommendation rows
              </small>
            </div>

            <div className="stat-card">
              <div className="stat-card-icon">
                👤
              </div>

              <span>Unique Users</span>

              <strong>
                {Math.round(
                  stats.unique_users,
                )}
              </strong>

              <small>
                Travelers included in evaluation
              </small>
            </div>

            <div className="stat-card">
              <div className="stat-card-icon">
                📍
              </div>

              <span>Unique Destinations</span>

              <strong>
                {Math.round(
                  stats.unique_destinations,
                )}
              </strong>

              <small>
                Destinations represented in output
              </small>
            </div>

            <div className="stat-card">
              <div className="stat-card-icon">
                👥
              </div>

              <span>Mean Predicted Crowd</span>

              <strong>
                {formatNumber(
                  stats.mean_predicted_crowd_score,
                  1,
                )}
              </strong>

              <small>
                Predicted crowd score
              </small>
            </div>

            <div className="stat-card">
              <div className="stat-card-icon">
                🌿
              </div>

              <span>Crowd Suitability</span>

              <strong>
                {Math.round(
                  stats.mean_crowd_suitability *
                    100,
                )}
                %
              </strong>

              <small>
                Mean crowd suitability
              </small>
            </div>

            <div className="stat-card">
              <div className="stat-card-icon">
                ✦
              </div>

              <span>
                Demand-Aware Score
              </span>

              <strong>
                {Math.round(
                  stats.mean_demand_aware_score *
                    100,
                )}
                %
              </strong>

              <small>
                Mean final recommendation score
              </small>
            </div>

            <div className="stat-card">
              <div className="stat-card-icon">
                ↕
              </div>

              <span>Changed Rankings</span>

              <strong>
                {Math.round(
                  stats.changed_rankings,
                )}
              </strong>

              <small>
                Rankings modified by demand-aware
                adjustment
              </small>
            </div>

            <div className="stat-card">
              <div className="stat-card-icon">
                =
              </div>

              <span>Unchanged Rankings</span>

              <strong>
                {Math.round(
                  stats.unchanged_rankings,
                )}
              </strong>

              <small>
                Rankings retained after adjustment
              </small>
            </div>
          </div>
        </section>

        {/* =================================================
            SEMANTIC + DEMAND SIGNALS
        ================================================= */}

        <section className="dashboard-section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">
                MODEL SIGNAL SUMMARY
              </span>

              <h2>Demand-aware ranking signals</h2>
            </div>
          </div>

          <div className="analytics-factor-grid">
            <div className="analytics-card">
              <h3>SBERT Hybrid Similarity</h3>

              <FactorBar
                label="Mean semantic score"
                value={
                  stats.mean_sbert_hybrid_score
                }
              />

              <p
                style={{
                  marginTop: "12px",
                  color: "#718078",
                  fontSize: "14px",
                }}
              >
                Semantic similarity captures how
                closely destination information aligns
                with traveler preferences.
              </p>
            </div>

            <div className="analytics-card">
              <h3>Crowd Suitability</h3>

              <FactorBar
                label="Mean suitability"
                value={
                  stats.mean_crowd_suitability
                }
              />

              <p
                style={{
                  marginTop: "12px",
                  color: "#718078",
                  fontSize: "14px",
                }}
              >
                Crowd prediction is incorporated into
                the final ranking to account for
                destination demand.
              </p>
            </div>

            <div className="analytics-card">
              <h3>Demand-Aware Score</h3>

              <FactorBar
                label="Mean final score"
                value={
                  stats.mean_demand_aware_score
                }
              />

              <p
                style={{
                  marginTop: "12px",
                  color: "#718078",
                  fontSize: "14px",
                }}
              >
                The final score combines recommendation
                relevance with demand-sensitive
                destination suitability.
              </p>
            </div>
          </div>
        </section>

        {/* =================================================
            RESEARCH NOTE
        ================================================= */}

        <section className="research-note">
          <div className="research-note-icon">
            ✦
          </div>

          <div>
            <span className="eyebrow">
              RESEARCH OUTPUT
            </span>

            <h3>
              Evaluation results are connected to the
              validated ML pipeline
            </h3>

            <p>
              These metrics are based on the completed
              recommendation evaluation, including
              baseline comparisons, NDCG evaluation and
              demand-aware ranking analysis.
            </p>
          </div>
        </section>

        <section className="evaluation-coverage-note"><span className="eyebrow">METRIC COVERAGE & LIMITS</span><div className="evaluation-coverage-grid"><div><strong>Reported by this benchmark</strong><p>Precision@5, Recall@5, NDCG@5, and NDCG changes across the provided ranking depths.</p></div><div><strong>Not supported by current evaluation data</strong><p>No time-aligned actual crowd observations for forecast MAE/RMSE; no crowd forecast horizon; and no reported catalog coverage, intra-list diversity, or user trust study. Collect labeled temporal data and define a held-out evaluation protocol before making those claims.</p></div></div></section>

      </div>
    );
  }

  /* =======================================================
     PAGE ROUTER
  ======================================================= */

  function renderPage() {
    switch (page) {
      case "dashboard":
        return renderDashboard();

      case "recommendations":
        return renderRecommendations();

      case "saved":
        return renderSavedPlaces();

      case "profile":
        return renderProfile();

      case "itinerary":
        return renderItinerary();

      case "account":
        return renderAccount();

      case "crowd":
        return renderCrowd();

      case "weather":
        return renderWeather();

      case "analytics":
        return renderAnalytics();

      case "evaluation":
        return renderEvaluation();

      case "assistant":
        return renderAssistant();

      default:
        return renderDashboard();
    }
  }

  /* =======================================================
     NAVIGATION
  ======================================================= */

  const navItems: {
    id: Page;
    label: string;
    icon: string;
  }[] = [
    {
      id: "dashboard",
      label: "Dashboard",
      icon: "⌂",
    },
    {
      id: "recommendations",
      label: "Recommendations",
      icon: "✦",
    },
    {
      id: "saved",
      label: "Saved Places",
      icon: "heart",
    },
    {
      id: "profile",
      label: "Traveler Profile",
      icon: "◉",
    },
    {
      id: "itinerary",
      label: "Itinerary Planner",
      icon: "compass",
    },
    {
      id: "account",
      label: "Account",
      icon: "user",
    },
    {
      id: "crowd",
      label: "Crowd Prediction",
      icon: "👥",
    },
    {
      id: "weather",
      label: "Weather Intelligence",
      icon: "☀",
    },
    {
      id: "analytics",
      label: "Analytics",
      icon: "◫",
    },
    {
      id: "assistant",
      label: "Explainable AI Chat",
      icon: "assistant",
    },
    {
      id: "evaluation",
      label: "Model Evaluation",
      icon: "▥",
    },
  ];

  const iconNameByPage: Record<Page, string> = {
    dashboard: "dashboard",
    recommendations: "compass",
    saved: "heart",
    profile: "user",
    itinerary: "compass",
    account: "user",
    crowd: "people",
    weather: "sun",
    analytics: "chart",
    evaluation: "award",
    assistant: "sparkle",
  };

  /* =======================================================
     MAIN LAYOUT
  ======================================================= */

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <img className="brand-logo" src="/travelmind-logo.svg" alt="" />
          <div>
            <strong><span className="brand-travel">Travel</span><span className="brand-mind">Mind</span></strong>
            <span>Sri Lanka, your way.</span>
          </div>
        </div>

        <div className="sidebar-section-label">
          MAIN MENU
        </div>

        <nav className="sidebar-nav">
          {navItems.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${
                page === item.id
                  ? "active"
                  : ""
              }`}
              onClick={() =>
                setPage(item.id)
              }
            >
              <span className="nav-icon">
                <AppIcon name={iconNameByPage[item.id]} />
              </span>

              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="ai-status-card">
            <div className="ai-status-dot" />

            <div>
              <strong>
                AI System Online
              </strong>

              <span>
                Recommendation engine active
              </span>
            </div>
          </div>

          <div className="sidebar-footer">
            <span>
              TravelMind · Sri Lanka
            </span>

            <span>v1.0</span>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="breadcrumb">
            <span>
              TravelMind
            </span>

            <span>/</span>

            <strong>
              {navItems.find(
                (item) =>
                  item.id === page,
              )?.label}
            </strong>
          </div>

          <div className="topbar-actions">
            <button className="topbar-user" onClick={() => setPage("profile")} aria-label="Open traveler profile">
              <div className="topbar-avatar">
                {(profile.name.trim() ? profile.name.trim().slice(0, 1) : selectedUser.slice(-2)).toUpperCase()}
              </div>

              <div>
                <span>Traveler</span>
                <strong>
                  {profile.name || selectedUser}
                </strong>
            </div>
            </button>
          </div>
        </header>

        {renderPage()}
      </main>

      {selectedRecommendation && (
        <RecommendationModal
          recommendation={
            selectedRecommendation
          }
          profile={profile}
          onClose={() =>
            setSelectedRecommendation(null)
          }
        />
      )}
    </div>
  );
}

export default App;
