"use client";

import type { DashboardFrame } from "../hooks/useWebsocket";

type StatCardsProps = {
  frame: DashboardFrame | null;
  history: number[];
};

type CardSpec = {
  title: string;
  value: string;
  suffix?: string;
  delta: string;
  meter: number;
};

function clamp(value: number, lower: number, upper: number) {
  return Math.max(lower, Math.min(upper, value));
}

export function StatCards({ frame, history }: StatCardsProps) {
  if (!frame) {
    return <div className="empty-state">Waiting for live telemetry from the ZeroMQ bridge.</div>;
  }

  const cards: CardSpec[] = [
    {
      title: "Team Productivity",
      value: frame.headline.team_productivity.toFixed(1),
      suffix: "%",
      delta: `${frame.trend.throughput_delta >= 0 ? "+" : ""}${frame.trend.throughput_delta.toFixed(1)} vs last frame`,
      meter: frame.headline.team_productivity,
    },
    {
      title: "Burnout Pressure",
      value: frame.headline.burnout_pressure.toFixed(1),
      suffix: "%",
      delta: `${frame.trend.burnout_delta >= 0 ? "+" : ""}${frame.trend.burnout_delta.toFixed(1)} risk shift`,
      meter: frame.headline.burnout_pressure,
    },
    {
      title: "Context Switching",
      value: frame.headline.context_switch_pressure.toFixed(1),
      suffix: "%",
      delta: `${frame.trend.focus_stability.toFixed(1)} focus stability`,
      meter: frame.headline.context_switch_pressure,
    },
    {
      title: "Employees Online",
      value: frame.headline.employees_online.toString(),
      delta: frame.headline.risk_band,
      meter: clamp(frame.headline.employees_online * 12, 0, 100),
    },
  ];

  return (
    <section className="stat-grid" aria-label="Live headline metrics">
      {cards.map((card, index) => (
        <article className="stat-card" key={card.title}>
          <div className="stat-kicker">
            <span>{card.title}</span>
            <span className="stat-delta">{card.delta}</span>
          </div>
          <div className="stat-value">
            <strong>{card.value}</strong>
            {card.suffix ? <small>{card.suffix}</small> : null}
          </div>
          <div className="meter-track" style={{ marginTop: 18 }}>
            <div className="meter-fill" style={{ width: `${card.meter}%` }} />
          </div>
          {index === 0 ? (
            <div className="sparkline" aria-hidden="true" style={{ marginTop: 16 }}>
              {history.map((entry, itemIndex) => (
                <span
                  className="sparkline-bar"
                  key={`${entry}-${itemIndex}`}
                  style={{ height: `${clamp(entry, 8, 100)}%` }}
                />
              ))}
            </div>
          ) : null}
        </article>
      ))}
    </section>
  );
}
