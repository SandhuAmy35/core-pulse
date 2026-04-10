"use client";

import { useDeferredValue } from "react";

import { BurnoutHeatmap } from "../components/BurnoutHeatmap";
import { StatCards } from "../components/StatCards";
import { SynergyMatrix } from "../components/SynergyMatrix";
import { useWebsocket } from "../hooks/useWebsocket";

function formatConnectionState(state: string) {
  if (state === "open") {
    return "Bridge live";
  }
  if (state === "connecting") {
    return "Connecting";
  }
  if (state === "error") {
    return "Connection error";
  }
  return "Bridge offline";
}

export default function Page() {
  const { frame, history, connectionState, error } = useWebsocket();
  const deferredFrame = useDeferredValue(frame);

  const activeWindows =
    deferredFrame?.employees
      .slice()
      .sort((left, right) => right.productivity_index - left.productivity_index)
      .slice(0, 4) ?? [];

  const distractions =
    deferredFrame?.employees
      .flatMap((employee) =>
        employee.distractions.map((domain) => ({
          employee: employee.display_name,
          domain,
          burnout: employee.burnout_risk,
        })),
      )
      .sort((left, right) => right.burnout - left.burnout)
      .slice(0, 4) ?? [];

  return (
    <main className="dashboard-shell">
      <section className="hero-panel">
        <div className="hero-copy">
          <div className="eyebrow">
            <span className="live-dot" />
            CORE-PULSE / live dashboard
          </div>
          <h1 className="hero-title">Watch productivity pulse, fatigue drift, and team friction in one surface.</h1>
          <p className="hero-subtitle">
            This dashboard is fed by the integration-first mock pipe: Layer 0 publishes synthetic telemetry over ZeroMQ,
            the Python bridge reshapes it into dashboard frames, and the frontend renders the stream over WebSockets.
          </p>
          <div className="hero-meta">
            <span className="meta-pill">ZMQ topic: telemetry_raw</span>
            <span className="meta-pill">WebSocket: ws://127.0.0.1:8765</span>
            <span className="meta-pill">Risk band: {deferredFrame?.headline.risk_band ?? "waiting"}</span>
          </div>
        </div>
        <div className="hero-side">
          <div className="hero-side-card">
            <h3>Connection state</h3>
            <div className="connection-line">
              <span className="connection-badge">{formatConnectionState(connectionState)}</span>
              <span>{deferredFrame ? `Frame #${deferredFrame.sequence}` : "No frames yet"}</span>
            </div>
            <p style={{ marginTop: 10 }}>
              {error ?? "Once the bridge is running, the dashboard updates automatically with no manual refresh."}
            </p>
          </div>
          <div className="hero-side-card">
            <h3>System pressure</h3>
            <p>
              CPU {deferredFrame?.system_load.cpu ?? "--"}% / memory {deferredFrame?.system_load.memory ?? "--"}% /
              network {deferredFrame?.system_load.network_mbps ?? "--"} Mbps
            </p>
          </div>
          <div className="hero-side-card">
            <h3>Telemetry source</h3>
            <p>{deferredFrame?.source.sensor_id ?? "sentinel-sim-01"} emitting live mock batches for integration.</p>
          </div>
        </div>
      </section>

      <StatCards frame={deferredFrame} history={history} />

      <section className="dashboard-grid">
        <BurnoutHeatmap frame={deferredFrame} />
        <SynergyMatrix frame={deferredFrame} />
      </section>

      <section className="stream-grid">
        <article className="stream-card">
          <h3>Attention drains and active windows</h3>
          <p>Top windows and distraction domains pulled from the latest employee batch.</p>
          {deferredFrame ? (
            <ul className="feed-list" style={{ marginTop: 18 }}>
              {activeWindows.map((employee) => (
                <li key={employee.user_id}>
                  <strong>{employee.display_name}</strong> is concentrated in <span className="window-chip">{employee.active_window}</span>
                  <div className="feed-meta">
                    <span>Productivity {Math.round(employee.productivity_index * 100)}%</span>
                    <span>Flow block {employee.flow_minutes} min</span>
                  </div>
                </li>
              ))}
              {distractions.map((entry) => (
                <li key={`${entry.employee}-${entry.domain}`}>
                  <strong>{entry.employee}</strong> surfaced <span className="window-chip">{entry.domain}</span>
                  <div className="feed-meta">
                    <span>Burnout risk {Math.round(entry.burnout * 100)}%</span>
                    <span>Flagged by live mock telemetry</span>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <div className="empty-state" style={{ marginTop: 18 }}>
              Start the publisher and bridge to populate the live activity feed.
            </div>
          )}
        </article>

        <article className="stream-card">
          <h3>Alert ledger</h3>
          <p>Highest-risk alerts surfaced by the bridge transformation layer.</p>
          {deferredFrame ? (
            <ul className="bullet-list" style={{ marginTop: 18 }}>
              {deferredFrame.alerts.map((alert) => (
                <li key={alert.user_id}>
                  <strong>{alert.display_name}</strong>
                  <div className="feed-meta">
                    <span>{alert.message}</span>
                    <span>{alert.severity.toUpperCase()}</span>
                  </div>
                </li>
              ))}
              <li>
                <strong>Bridge flags</strong>
                <div className="feed-meta">
                  <span>{deferredFrame.flags.join(" / ")}</span>
                  <span>{deferredFrame.received_at}</span>
                </div>
              </li>
            </ul>
          ) : (
            <div className="empty-state" style={{ marginTop: 18 }}>
              No alert frames yet.
            </div>
          )}
        </article>
      </section>
    </main>
  );
}
