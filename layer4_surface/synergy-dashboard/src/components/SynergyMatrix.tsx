"use client";

import type { DashboardFrame } from "../hooks/useWebsocket";

type SynergyMatrixProps = {
  frame: DashboardFrame | null;
};

function edgeKey(left: string, right: string) {
  return [left, right].sort().join("::");
}

function colorForValue(value: number) {
  const green = 148 - Math.round(value * 72);
  const red = 255 - Math.round(value * 35);
  const blue = 240 - Math.round(value * 110);
  return `rgba(${red}, ${green}, ${blue}, 0.92)`;
}

export function SynergyMatrix({ frame }: SynergyMatrixProps) {
  if (!frame) {
    return (
      <section className="section-card">
        <div className="empty-state">The synergy matrix will appear after the first live telemetry batch arrives.</div>
      </section>
    );
  }

  const labels = frame.synergy_matrix.labels;
  const lookup = new Map(frame.synergy_matrix.edges.map((edge) => [edgeKey(edge.source, edge.target), edge.friction]));

  return (
    <section className="section-card">
      <div className="section-head">
        <div>
          <h3>Synergy Friction Matrix</h3>
          <p className="section-copy">
            Pairwise friction estimates computed from load imbalance, context switching, distraction overlap, and burnout spread.
          </p>
        </div>
      </div>
      <div className="matrix-shell">
        <table className="matrix-grid">
          <thead>
            <tr>
              <th className="matrix-header">Pair</th>
              {labels.map((label) => (
                <th key={label}>{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {labels.map((rowLabel) => (
              <tr key={rowLabel}>
                <th>{rowLabel}</th>
                {labels.map((columnLabel) => {
                  const value = rowLabel === columnLabel ? 0 : lookup.get(edgeKey(rowLabel, columnLabel)) ?? 0;
                  return (
                    <td key={`${rowLabel}-${columnLabel}`}>
                      <div
                        className="matrix-cell"
                        style={{
                          background: colorForValue(value),
                        }}
                      >
                        {value.toFixed(2)}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
