"use client";

import type { DashboardFrame } from "../hooks/useWebsocket";

type BurnoutHeatmapProps = {
  frame: DashboardFrame | null;
};

function percent(value: number) {
  return `${(value * 100).toFixed(0)}%`;
}

export function BurnoutHeatmap({ frame }: BurnoutHeatmapProps) {
  if (!frame) {
    return (
      <section className="section-card">
        <div className="empty-state">Burnout heatmap will populate as soon as the bridge emits a dashboard frame.</div>
      </section>
    );
  }

  const employees = [...frame.employees].sort((left, right) => right.burnout_risk - left.burnout_risk);

  return (
    <section className="section-card">
      <div className="section-head">
        <div>
          <h3>Burnout Heatmap</h3>
          <p className="section-copy">
            A live, person-level surface of fatigue pressure, focus decay, and context switching hotspots.
          </p>
        </div>
        <span className="risk-chip">{frame.headline.risk_band} risk band</span>
      </div>
      <div className="employee-grid">
        {employees.map((employee) => (
          <article
            className="employee-card"
            key={employee.user_id}
            style={{
              background: `linear-gradient(145deg, rgba(255,255,255,0.92), rgba(255, ${245 - Math.round(
                employee.burnout_risk * 70,
              )}, ${232 - Math.round(employee.burnout_risk * 120)}, 0.92))`,
            }}
          >
            <header>
              <div>
                <h4>{employee.display_name}</h4>
                <span className="window-chip">{employee.active_window}</span>
              </div>
              <span className="risk-chip">{percent(employee.burnout_risk)} burnout</span>
            </header>
            <div className="metric-row">
              <div className="metric-label">
                <span>Focus score</span>
                <span>{percent(employee.focus_score)}</span>
              </div>
              <div className="meter-track">
                <div className="meter-fill" style={{ width: `${employee.focus_score * 100}%` }} />
              </div>
            </div>
            <div className="metric-row">
              <div className="metric-label">
                <span>Activity load</span>
                <span>{percent(employee.activity_load)}</span>
              </div>
              <div className="meter-track">
                <div className="meter-fill" style={{ width: `${employee.activity_load * 100}%` }} />
              </div>
            </div>
            <div className="metric-row">
              <div className="metric-label">
                <span>Context switches</span>
                <span>{employee.context_switches}/18</span>
              </div>
              <div className="meter-track">
                <div className="meter-fill" style={{ width: `${(employee.context_switches / 18) * 100}%` }} />
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
