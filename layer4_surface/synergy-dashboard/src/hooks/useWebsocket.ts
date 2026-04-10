"use client";

import { startTransition, useEffect, useState } from "react";

export type EmployeeTelemetry = {
  user_id: string;
  display_name: string;
  focus_score: number;
  burnout_risk: number;
  activity_load: number;
  context_switches: number;
  keystroke_entropy: number;
  flow_minutes: number;
  active_window: string;
  distractions: string[];
  productivity_index: number;
};

export type SynergyEdge = {
  source: string;
  target: string;
  friction: number;
};

export type DashboardFrame = {
  type: "dashboard_frame";
  timestamp: string;
  received_at: string;
  sequence: number;
  headline: {
    team_productivity: number;
    burnout_pressure: number;
    context_switch_pressure: number;
    employees_online: number;
    risk_band: string;
  };
  trend: {
    throughput_delta: number;
    burnout_delta: number;
    focus_stability: number;
  };
  system_load: {
    cpu: number;
    memory: number;
    network_mbps: number;
  };
  employees: EmployeeTelemetry[];
  synergy_matrix: {
    labels: string[];
    edges: SynergyEdge[];
  };
  alerts: Array<{
    user_id: string;
    display_name: string;
    message: string;
    severity: string;
  }>;
  flags: string[];
  source: {
    zmq_topic: string;
    sensor_id: string;
    team: string;
  };
};

type ConnectionState = "connecting" | "open" | "closed" | "error";

const DEFAULT_URL = process.env.NEXT_PUBLIC_BRIDGE_URL ?? "ws://127.0.0.1:8765";

export function useWebsocket(url: string = DEFAULT_URL) {
  const [frame, setFrame] = useState<DashboardFrame | null>(null);
  const [history, setHistory] = useState<number[]>([]);
  const [connectionState, setConnectionState] = useState<ConnectionState>("connecting");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const socket = new WebSocket(url);

    setConnectionState("connecting");
    setError(null);

    socket.onopen = () => {
      if (!active) {
        return;
      }
      setConnectionState("open");
    };

    socket.onclose = () => {
      if (!active) {
        return;
      }
      setConnectionState("closed");
    };

    socket.onerror = () => {
      if (!active) {
        return;
      }
      setConnectionState("error");
      setError("Bridge connection failed. Start the Python broadcaster on ws://127.0.0.1:8765.");
    };

    socket.onmessage = (event) => {
      if (!active) {
        return;
      }

      try {
        const nextFrame = JSON.parse(event.data) as DashboardFrame;
        if (nextFrame.type !== "dashboard_frame") {
          return;
        }

        startTransition(() => {
          setFrame(nextFrame);
          setHistory((previous) => [...previous.slice(-17), nextFrame.headline.team_productivity]);
        });
      } catch {
        setError("Received a malformed dashboard frame.");
      }
    };

    return () => {
      active = false;
      socket.close();
    };
  }, [url]);

  return {
    frame,
    history,
    connectionState,
    error,
  };
}
