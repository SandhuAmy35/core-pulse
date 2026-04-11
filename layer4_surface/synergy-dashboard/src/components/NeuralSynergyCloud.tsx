"use client";

import { useEffect, useRef } from "react";

type NeuralSynergyCloudProps = {
  signalState: "ACTIVE" | "SYNCING" | "FAULT" | "OFFLINE";
};

type CloudSide = "left" | "right" | "bridge";

type CloudParticle = {
  side: CloudSide;
  x: number;
  y: number;
  depth: number;
  radius: number;
  phase: number;
  speed: number;
  driftX: number;
  driftY: number;
  jitter: number;
};

type StarParticle = {
  x: number;
  y: number;
  radius: number;
  alpha: number;
  twinkle: number;
  phase: number;
  drift: number;
};

type Size = {
  width: number;
  height: number;
};

const CLOUD_PARTICLE_COUNT = 3600;
const STAR_PARTICLE_COUNT = 320;
const FILAMENT_COUNT = 28;
const CONTOUR_STEPS = 72;

function randomBetween(min: number, max: number) {
  return min + Math.random() * (max - min);
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function gaussianRandom() {
  let u = 0;
  let v = 0;
  while (u === 0) {
    u = Math.random();
  }
  while (v === 0) {
    v = Math.random();
  }
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

function createCloudParticle(): CloudParticle {
  const seed = Math.random();
  const side: CloudSide = seed < 0.46 ? "left" : seed < 0.92 ? "right" : "bridge";

  return {
    side,
    x: side === "bridge" ? gaussianRandom() * 0.35 : gaussianRandom() * 0.76,
    y: side === "bridge" ? gaussianRandom() * 0.5 : gaussianRandom() * 0.64,
    depth: randomBetween(0.25, 1),
    radius: side === "bridge" ? randomBetween(0.25, 1.3) : randomBetween(0.4, 1.8),
    phase: randomBetween(0, Math.PI * 2),
    speed: randomBetween(0.45, 1.9),
    driftX: randomBetween(-0.02, 0.02),
    driftY: randomBetween(-0.015, 0.015),
    jitter: randomBetween(0, 1),
  };
}

function createStarParticle(): StarParticle {
  return {
    x: randomBetween(0, 1),
    y: randomBetween(0, 1),
    radius: randomBetween(0.2, 1.55),
    alpha: randomBetween(0.16, 0.75),
    twinkle: randomBetween(0.4, 1.5),
    phase: randomBetween(0, Math.PI * 2),
    drift: randomBetween(2, 9),
  };
}

function signalOpacity(signalState: NeuralSynergyCloudProps["signalState"]) {
  if (signalState === "ACTIVE") {
    return 1;
  }
  if (signalState === "SYNCING") {
    return 0.78;
  }
  if (signalState === "FAULT") {
    return 0.48;
  }
  return 0.28;
}

function drawHalo(
  context: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  radius: number,
  colorInner: string,
  colorOuter: string,
  alpha: number,
) {
  const gradient = context.createRadialGradient(cx, cy, radius * 0.08, cx, cy, radius);
  gradient.addColorStop(0, colorInner);
  gradient.addColorStop(1, colorOuter);
  context.globalAlpha = alpha;
  context.fillStyle = gradient;
  context.beginPath();
  context.arc(cx, cy, radius, 0, Math.PI * 2);
  context.fill();
  context.globalAlpha = 1;
}

function drawContour(
  context: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  scaleX: number,
  scaleY: number,
  elapsed: number,
  color: string,
  jagged: boolean,
) {
  context.strokeStyle = color;
  context.lineWidth = jagged ? 1.6 : 1.25;
  context.beginPath();

  for (let index = 0; index <= CONTOUR_STEPS; index += 1) {
    const theta = (index / CONTOUR_STEPS) * Math.PI * 2;
    const low = Math.sin(theta * 5 + elapsed * 1.35) * 0.09;
    const mid = Math.sin(theta * 9 - elapsed * 1.9) * 0.06;
    const high = jagged ? Math.sin(theta * 22 + elapsed * 4.8) * 0.045 : Math.sin(theta * 14 + elapsed * 2.9) * 0.025;
    const radiusScale = 1 + low + mid + high;
    const x = cx + Math.cos(theta) * scaleX * radiusScale;
    const y = cy + Math.sin(theta) * scaleY * (1 + low * 0.55 + mid * 0.5 + high * 0.35);

    if (index === 0) {
      context.moveTo(x, y);
    } else {
      context.lineTo(x, y);
    }
  }

  context.closePath();
  context.stroke();
}

export function NeuralSynergyCloud({ signalState }: NeuralSynergyCloudProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const frameRef = useRef<number | null>(null);
  const startRef = useRef<number>(0);
  const cloudRef = useRef<CloudParticle[] | null>(null);
  const starsRef = useRef<StarParticle[] | null>(null);
  const sizeRef = useRef<Size>({ width: 0, height: 0 });

  useEffect(() => {
    if (!cloudRef.current) {
      cloudRef.current = Array.from({ length: CLOUD_PARTICLE_COUNT }, createCloudParticle);
    }
    if (!starsRef.current) {
      starsRef.current = Array.from({ length: STAR_PARTICLE_COUNT }, createStarParticle);
    }
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !cloudRef.current || !starsRef.current) {
      return;
    }

    const context = canvas.getContext("2d");
    if (!context) {
      return;
    }
    const stars = starsRef.current;
    const clouds = cloudRef.current;
    if (!stars || !clouds) {
      return;
    }

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.max(1, Math.min(window.devicePixelRatio || 1, 2));
      canvas.width = Math.floor(rect.width * dpr);
      canvas.height = Math.floor(rect.height * dpr);
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
      sizeRef.current = { width: rect.width, height: rect.height };
    };

    resize();

    const observer = new ResizeObserver(resize);
    observer.observe(canvas);

    const draw = (timestamp: number) => {
      if (!startRef.current) {
        startRef.current = timestamp;
      }

      const elapsed = (timestamp - startRef.current) * 0.001;
      const { width, height } = sizeRef.current;
      const alphaScale = signalOpacity(signalState);

      const centerY = height * 0.54 + Math.sin(elapsed * 0.72) * height * 0.018;
      const leftCenterX = width * 0.35 + Math.sin(elapsed * 0.48) * width * 0.012;
      const rightCenterX = width * 0.65 + Math.cos(elapsed * 0.42) * width * 0.014;

      const leftBreath = 1 + 0.08 * Math.sin(elapsed * 1.45);
      const rightBreath = 1 + 0.09 * Math.sin(elapsed * 1.2 + 1.4);

      const leftScaleX = width * 0.17 * leftBreath;
      const leftScaleY = height * 0.22 * leftBreath;
      const rightScaleX = width * 0.18 * rightBreath;
      const rightScaleY = height * 0.24 * rightBreath;

      context.clearRect(0, 0, width, height);

      const ambientGradient = context.createLinearGradient(0, 0, width, 0);
      ambientGradient.addColorStop(0, `rgba(18, 80, 72, ${0.2 * alphaScale})`);
      ambientGradient.addColorStop(0.5, `rgba(34, 48, 64, ${0.16 * alphaScale})`);
      ambientGradient.addColorStop(1, `rgba(98, 22, 38, ${0.22 * alphaScale})`);
      context.fillStyle = ambientGradient;
      context.fillRect(0, 0, width, height);

      for (const star of stars) {
        const twinkle = 0.45 + 0.55 * Math.sin(elapsed * star.twinkle + star.phase);
        const driftX = Math.sin(elapsed * 0.08 + star.phase) * star.drift;
        const x = star.x * width + driftX;
        const y = star.y * height;
        context.fillStyle = `rgba(196, 226, 252, ${star.alpha * twinkle * alphaScale * 0.72})`;
        context.beginPath();
        context.arc(x, y, star.radius, 0, Math.PI * 2);
        context.fill();
      }

      drawHalo(
        context,
        leftCenterX,
        centerY,
        Math.max(leftScaleX, leftScaleY) * 1.35,
        "rgba(98, 255, 209, 0.24)",
        "rgba(36, 255, 196, 0)",
        alphaScale,
      );

      drawHalo(
        context,
        rightCenterX,
        centerY,
        Math.max(rightScaleX, rightScaleY) * 1.32,
        "rgba(246, 86, 112, 0.2)",
        "rgba(246, 86, 112, 0)",
        alphaScale,
      );

      context.lineCap = "round";
      for (let index = 0; index < FILAMENT_COUNT; index += 1) {
        const t = index / (FILAMENT_COUNT - 1);
        const startX = leftCenterX + leftScaleX * 0.66 + Math.sin(elapsed * 2.1 + t * 7.4) * 4;
        const endX = rightCenterX - rightScaleX * 0.66 + Math.cos(elapsed * 2.2 + t * 6.5) * 6;
        const startY = centerY + (t - 0.5) * leftScaleY * 1.2 + Math.sin(elapsed * 1.7 + t * 9.2) * 8;
        const endY = centerY + (t - 0.5) * rightScaleY * 1.15 + Math.cos(elapsed * 1.5 + t * 7.8) * 8;
        const control1X = width * 0.48 + Math.sin(elapsed * 1.05 + t * 4.6) * 24;
        const control2X = width * 0.52 + Math.cos(elapsed * 0.9 + t * 5.3) * 24;
        const control1Y = centerY + Math.sin(elapsed * 1.2 + t * 11) * 20;
        const control2Y = centerY + Math.cos(elapsed * 1.15 + t * 10.5) * 20;

        context.beginPath();
        context.moveTo(startX, startY);
        context.bezierCurveTo(control1X, control1Y, control2X, control2Y, endX, endY);
        context.strokeStyle = `rgba(${Math.round(88 + t * 146)}, ${Math.round(236 - t * 170)}, ${Math.round(
          193 - t * 62,
        )}, ${(0.06 + 0.18 * Math.sin(elapsed * 0.9 + t * 8.8 + 0.6)) * alphaScale})`;
        context.lineWidth = 0.6 + 1.1 * Math.pow(Math.sin((t + 0.2) * Math.PI), 2);
        context.stroke();
      }

      context.globalCompositeOperation = "lighter";

      for (const particle of clouds) {
        const pulse = 0.55 + 0.45 * Math.sin(elapsed * particle.speed + particle.phase);
        const swirl = Math.sin(elapsed * (particle.speed * 0.72) + particle.phase);
        const wobble = Math.cos(elapsed * (particle.speed * 1.12) - particle.phase);

        let originX = leftCenterX;
        let originY = centerY;
        let scaleX = leftScaleX;
        let scaleY = leftScaleY;

        if (particle.side === "right") {
          originX = rightCenterX;
          scaleX = rightScaleX;
          scaleY = rightScaleY;
        } else if (particle.side === "bridge") {
          const blend = 0.5 + 0.5 * Math.sin(particle.phase + elapsed * 0.28);
          originX = leftCenterX * (1 - blend) + rightCenterX * blend;
          scaleX = width * 0.1;
          scaleY = height * 0.15;
          originY = centerY + Math.sin(elapsed * 0.6 + particle.phase) * 10;
        }

        const localX = particle.x + swirl * 0.11 + Math.sin(elapsed * 1.7 + particle.phase * 1.8) * 0.05;
        const localY = particle.y + wobble * 0.08 + Math.cos(elapsed * 1.5 + particle.phase * 1.4) * 0.04;

        const px = originX + localX * scaleX + Math.sin(elapsed * 0.5 + particle.phase) * particle.driftX * width;
        const py = originY + localY * scaleY + Math.cos(elapsed * 0.55 + particle.phase) * particle.driftY * height;

        const distance = Math.hypot((px - originX) / Math.max(scaleX, 1), (py - originY) / Math.max(scaleY, 1));
        if (distance > (particle.side === "bridge" ? 1.15 : 1.25)) {
          continue;
        }

        const edge = clamp(distance, 0, 1.3);
        const falloff = Math.max(0, 1 - edge * 0.8);
        const intensity = falloff * particle.depth * pulse;
        const radius = particle.radius * (0.45 + particle.depth * 1.7) * (particle.side === "bridge" ? 0.85 : 1);

        let red = 120;
        let green = 210;
        let blue = 185;

        if (particle.side === "left") {
          red = 90 + particle.jitter * 45;
          green = 230 + particle.jitter * 18;
          blue = 180 + particle.jitter * 48;
        } else if (particle.side === "right") {
          const smoke = 146 + particle.jitter * 72;
          const accent = Math.max(0, edge - 0.6) * 1.9;
          red = smoke + accent * 94;
          green = smoke - 9 - accent * 62;
          blue = smoke + 12 - accent * 74;
        } else {
          red = 188 + particle.jitter * 42;
          green = 230 + particle.jitter * 22;
          blue = 236 + particle.jitter * 20;
        }

        context.fillStyle = `rgba(${Math.round(clamp(red, 0, 255))}, ${Math.round(clamp(green, 0, 255))}, ${Math.round(
          clamp(blue, 0, 255),
        )}, ${clamp(0.06 + intensity * 0.4 * alphaScale, 0, 1)})`;
        context.beginPath();
        context.arc(px, py, radius, 0, Math.PI * 2);
        context.fill();
      }

      context.globalCompositeOperation = "source-over";

      drawContour(
        context,
        leftCenterX,
        centerY,
        leftScaleX * 0.92,
        leftScaleY * 0.9,
        elapsed,
        `rgba(108, 255, 212, ${0.52 * alphaScale})`,
        false,
      );
      drawContour(
        context,
        rightCenterX,
        centerY,
        rightScaleX * 0.94,
        rightScaleY * 0.92,
        elapsed,
        `rgba(255, 84, 116, ${0.58 * alphaScale})`,
        true,
      );

      for (let index = 0; index < 10; index += 1) {
        const y = centerY + (index - 4.5) * rightScaleY * 0.17 + Math.sin(elapsed * 2.4 + index * 1.2) * 3;
        const x = rightCenterX + rightScaleX * 0.18 + Math.cos(elapsed * 1.4 + index * 0.8) * 5;
        const length = 18 + (0.5 + 0.5 * Math.sin(elapsed * 3 + index * 2.4)) * 34;

        context.beginPath();
        context.moveTo(x, y);
        context.lineTo(x + length, y);
        context.strokeStyle = `rgba(255, 82, 118, ${0.18 + 0.26 * alphaScale})`;
        context.lineWidth = 0.9;
        context.stroke();
      }

      context.fillStyle = `rgba(232, 255, 249, ${0.82 * alphaScale})`;
      context.beginPath();
      context.arc(leftCenterX + leftScaleX * 0.02, centerY - 1, 1.75, 0, Math.PI * 2);
      context.fill();

      context.fillStyle = `rgba(248, 250, 252, ${0.62 * alphaScale})`;
      context.beginPath();
      context.arc(rightCenterX - rightScaleX * 0.04, centerY + 1, 1.5, 0, Math.PI * 2);
      context.fill();

      frameRef.current = window.requestAnimationFrame(draw);
    };

    frameRef.current = window.requestAnimationFrame(draw);

    return () => {
      observer.disconnect();
      if (frameRef.current) {
        window.cancelAnimationFrame(frameRef.current);
      }
    };
  }, [signalState]);

  return <canvas className="cloud-canvas" ref={canvasRef} aria-hidden="true" />;
}
