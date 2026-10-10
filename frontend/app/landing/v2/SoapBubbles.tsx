"use client";

import { useEffect, useRef } from "react";

/** Iridescent soap bubbles drifting up behind the hero portrait. One small canvas, paused when off screen, still when motion is reduced. */
export function SoapBubbles({ count = 15 }: { count?: number }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;

    const sprite = document.createElement("canvas");
    sprite.width = sprite.height = 128;
    const s = sprite.getContext("2d")!;
    const g = s.createRadialGradient(64, 64, 22, 64, 64, 61);
    g.addColorStop(0, "rgba(255,255,255,0.05)");
    g.addColorStop(0.72, "rgba(255,214,236,0.22)");
    g.addColorStop(0.93, "rgba(255,150,205,0.7)");
    g.addColorStop(1, "rgba(255,190,225,0)");
    s.fillStyle = g;
    s.fillRect(0, 0, 128, 128);
    s.lineCap = "round";
    s.lineWidth = 4;
    s.strokeStyle = "rgba(140,225,255,0.65)";
    s.beginPath();
    s.arc(64, 64, 50, 0.15 * Math.PI, 0.55 * Math.PI);
    s.stroke();
    s.strokeStyle = "rgba(255,255,255,0.98)";
    s.lineWidth = 6;
    s.beginPath();
    s.arc(64, 64, 47, 1.12 * Math.PI, 1.42 * Math.PI);
    s.stroke();
    s.fillStyle = "rgba(255,255,255,0.95)";
    s.beginPath();
    s.arc(92, 92, 3.4, 0, Math.PI * 2);
    s.fill();

    const bubbles = Array.from({ length: count }, (_, i) => ({
      x: ((i * 37) % 100) / 100,
      r: 20 + ((i * 53) % 17) * 3.6,
      speed: 0.018 + ((i * 29) % 11) * 0.004,
      phase: ((i * 61) % 100) / 100,
    }));

    let w = 0;
    let h = 0;
    let raf = 0;
    let visible = true;
    const start = performance.now();

    const draw = (t: number) => {
      ctx.clearRect(0, 0, w, h);
      for (const b of bubbles) {
        const u = (t * b.speed + b.phase) % 1;
        const size = b.r * 2 * Math.min(1, u * 5, (1 - u) * 5);
        const x = b.x * w + Math.sin(t * 0.55 + b.phase * 6.28) * 16;
        const y = h * (1.08 - u * 1.2);
        ctx.drawImage(sprite, x - size / 2, y - size / 2, size, size);
      }
    };
    const loop = (now: number) => {
      raf = 0;
      if (!visible) return;
      draw((now - start) / 1000);
      raf = requestAnimationFrame(loop);
    };
    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = rect.width;
      h = rect.height;
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      draw(reduce ? 2.4 : (performance.now() - start) / 1000);
    };

    const io = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      if (visible && !reduce && !raf) raf = requestAnimationFrame(loop);
    });
    io.observe(canvas);
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);
    resize();
    if (!reduce) raf = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(raf);
      io.disconnect();
      ro.disconnect();
    };
  }, [count]);

  return <canvas ref={ref} className="lp-bubbles" aria-hidden="true" />;
}
