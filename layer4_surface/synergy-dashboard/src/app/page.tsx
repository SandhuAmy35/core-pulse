"use client";

import { useDeferredValue } from "react";

import { useWebsocket } from "../hooks/useWebsocket";

type WeatherCard = {
  mode: string;
  team: string;
  summary: string;
  score: number;
  tone: "good" | "warn" | "cool";
};

type PairingCard = {
  label: string;
  compatibility: number;
  tone: "lime" | "cyan";
};

const FALLBACK_WEATHER: WeatherCard[] = [
  {
    mode: "SUNNY",
    team: "Frontend Team",
    summary: "Delivery flow is clean and cross-functional handoffs are steady.",
    score: 92,
    tone: "good",
  },
  {
    mode: "STORM",
    team: "Backend Team",
    summary: "Incident noise is interrupting deep work and raising response fatigue.",
    score: 38,
    tone: "warn",
  },
  {
    mode: "CLOUDY",
    team: "Design Unit",
    summary: "Momentum is solid, but review cycles are still slowing execution.",
    score: 74,
    tone: "cool",
  },
];

const FALLBACK_PAIRINGS: PairingCard[] = [
  { label: "Frontend + Design", compatibility: 92, tone: "lime" },
  { label: "Platform + Security", compatibility: 87, tone: "cyan" },
];

const FALLBACK_LOGS = [
  "eBPF telemetry streaming...",
  "NASA SOLAR FLARE DATA: 3.4e-6 W/m2 (X-RAY FLUX)",
  "LOCAL TRNG SEED GENERATED...",
];

function clampPercent(value: number) {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function formatSignalState(state: string) {
  if (state === "open") {
    return "ACTIVE";
  }
  if (state === "connecting") {
    return "SYNCING";
  }
  if (state === "error") {
    return "FAULT";
  }
  return "OFFLINE";
}

function derivePairings(frame: ReturnType<typeof useWebsocket>["frame"]): PairingCard[] {
  if (!frame || frame.synergy_matrix.edges.length < 2) {
    return FALLBACK_PAIRINGS;
  }

  const topPairs = [...frame.synergy_matrix.edges]
    .sort((left, right) => left.friction - right.friction)
    .slice(0, 2);

  return topPairs.map((edge, index) => ({
    label: `${edge.source} + ${edge.target}`,
    compatibility: clampPercent((1 - edge.friction) * 100),
    tone: index === 0 ? "lime" : "cyan",
  }));
}

function deriveWeatherCards(teamProductivity: number, burnoutPressure: number): WeatherCard[] {
  return FALLBACK_WEATHER.map((card, index) => {
    const adjustedScore =
      index === 0
        ? teamProductivity
        : index === 1
          ? 100 - burnoutPressure
          : Math.round((teamProductivity + (100 - burnoutPressure)) / 2);

    return {
      ...card,
      score: clampPercent(adjustedScore),
    };
  });
}

export default function Page() {
  const { frame, connectionState } = useWebsocket();
  const deferredFrame = useDeferredValue(frame);

  const productivity = clampPercent(deferredFrame?.headline.team_productivity ?? 68);
  const burnoutPressure = clampPercent(deferredFrame?.headline.burnout_pressure ?? 76);
  const atRiskUnits = deferredFrame
    ? Math.max(
        deferredFrame.employees.filter((employee) => employee.burnout_risk >= 0.72).length,
        deferredFrame.alerts.length,
      )
    : 4;

  const weatherCards = deriveWeatherCards(productivity, burnoutPressure);
  const pairings = derivePairings(deferredFrame);
  const signalState = formatSignalState(connectionState);
  const nodeStatus =
    deferredFrame?.employees.slice(0, 12).map((employee, index) => ({
      node: `NODE_${100 + index}`,
      ok: employee.burnout_risk < 0.72,
    })) ??
    Array.from({ length: 12 }, (_, index) => ({
      node: `NODE_${100 + index}`,
      ok: true,
    }));

  const liveLogs = [
    FALLBACK_LOGS[0],
    `BRIDGE STATE: ${signalState}`,
    FALLBACK_LOGS[1],
    `RISK BAND: ${(deferredFrame?.headline.risk_band ?? "ELEVATED").toUpperCase()}`,
    FALLBACK_LOGS[2],
  ];

  return (
    <main className="surface-shell">
      <header className="surface-header panel-frame">
        <div className="brand-wrap">
          <h1 className="brand-title">
            <span className="brand-mark">+</span>
            CORE-PULSE <span className="brand-slash">//</span> SURFACE
          </h1>
          <p className="brand-subtitle">INTELLIGENT EMPLOYEE PRODUCTIVITY & BURNOUT ANALYTICS</p>
        </div>
        <div className="vault-pill">
          <span className="vault-dot" />
          ZK-VAULT LOCKED
        </div>
      </header>

      <section className="surface-grid-top">
        <aside className="left-stack">
          <article className="panel-frame stat-panel">
            <div className="panel-topline">
              <span>GLOBAL HEALTH INDEX</span>
              <small>LAYER 4B</small>
            </div>
            <p className="big-metric ok">{productivity}%</p>
          </article>

          <article className="panel-frame stat-panel">
            <div className="panel-topline">
              <span>AT-RISK UNITS</span>
            </div>
            <p className="big-metric alert">{atRiskUnits}</p>
            <div className="sub-divider" />
            <p className="micro-copy">ACTION REQUIRED: IMMEDIATE</p>
          </article>

          <article className="panel-frame stat-panel">
            <div className="shield-title">PRIVACY PROOFS</div>
            <p className="shield-copy">AES-256-GCM ACTIVE</p>
          </article>
        </aside>

        <section className="panel-frame cloud-panel">
          <div className="panel-topline">
            <span>LAYER 4B // STATCARDS</span>
            <span className="signal-pill">SIGNAL: {signalState}</span>
          </div>
          <p className="cloud-title">NEURAL SYNERGY CLOUD</p>
          <div className="cloud-field">
            <span className="cloud-core">{signalState === "ACTIVE" ? "BREATHING SYNC" : "AWAITING SYNC"}</span>
          </div>
          <div className="cloud-legend">
            <div>
              <p className="flow-label">FLOW STATE</p>
              <span>LOW FRICTION // OPTIMAL</span>
            </div>
            <div>
              <p className="burnout-label">BURNOUT CLOUD</p>
              <span>HIGH SOCIAL FRICTION</span>
            </div>
          </div>
        </section>

        <aside className="panel-frame matrix-panel">
          <h2 className="matrix-title">&gt; MATRIX TUI</h2>
          <div className="matrix-divider" />
          <div className="matrix-log">
            {liveLogs.map((line) => (
              <p key={line}>{line}</p>
            ))}
          </div>
          <div className="node-grid">
            {nodeStatus.map((entry) => (
              <div key={entry.node} className="node-row">
                <span>{entry.node}</span>
                <span className={entry.ok ? "node-ok" : "node-fail"}>{entry.ok ? "OK" : "WARN"}</span>
              </div>
            ))}
          </div>
          <span className="matrix-cursor" />
        </aside>
      </section>

      <section className="surface-grid-bottom">
        <article className="panel-frame weather-panel">
          <div className="panel-topline panel-inline">
            <h2>TEAM WEATHER MAP</h2>
            <span className="live-pill">LIVE FEED</span>
          </div>
          <div className="weather-grid">
            {weatherCards.map((card) => (
              <article key={card.mode} className={`weather-card tone-${card.tone}`}>
                <span className="weather-tag">{card.mode}</span>
                <h3>{card.team}</h3>
                <p>{card.summary}</p>
                <div className="focus-foot">
                  <span>FOCUS SCORE</span>
                  <strong>{card.score}%</strong>
                </div>
                <div className="focus-track">
                  <div className="focus-fill" style={{ width: `${card.score}%` }} />
                </div>
              </article>
            ))}
          </div>
        </article>

        <article className="panel-frame pairing-panel">
          <p className="pair-kicker">AI SYNERGY PAIRING</p>
          <h2>Recommended Pairings</h2>
          <div className="pair-list">
            {pairings.map((pair) => (
              <div key={pair.label} className="pair-card">
                <div className="pair-head">
                  <h3>{pair.label}</h3>
                  <strong>{pair.compatibility}%</strong>
                </div>
                <p>{pair.compatibility}% compatibility prediction</p>
                <div className="pair-track">
                  <span className={`pair-fill ${pair.tone}`} style={{ width: `${pair.compatibility}%` }} />
                </div>
              </div>
            ))}
          </div>
          <p className="pair-note">LOCKED: RAW LOGS REMAIN IN LOCAL USER VAULTS WHILE ONLY SAFE SIGNALS REACH THIS SURFACE.</p>
        </article>
      </section>
    </main>
  );
}
