"use client";

import { useEffect, useRef } from "react";
import { FrameMonitor, demote, promote, writeStoredTier } from "../perf/tier";
import { onStoryFrame, story } from "../story/store";
import { hexToOklab } from "./palette";
import { SKY_FRAG, SKY_UNIFORMS, SKY_VERT } from "./sky.glsl";
import { hexToUnit, newSkyParams, skyCanvasSize, skyParams } from "./sky";

/** Frames are not judged while the page is still loading (hydration, shader compile, textures). */
const WARMUP_S = 1.5;

function program(gl: WebGL2RenderingContext) {
  const shader = (type: number, src: string) => {
    const s = gl.createShader(type);
    if (!s) return null;
    gl.shaderSource(s, src);
    gl.compileShader(s);
    return gl.getShaderParameter(s, gl.COMPILE_STATUS) ? s : null;
  };
  const vs = shader(gl.VERTEX_SHADER, SKY_VERT);
  const fs = shader(gl.FRAGMENT_SHADER, SKY_FRAG);
  const p = gl.createProgram();
  if (!vs || !fs || !p) return null;
  gl.attachShader(p, vs);
  gl.attachShader(p, fs);
  gl.linkProgram(p);
  gl.deleteShader(vs);
  gl.deleteShader(fs);
  return gl.getProgramParameter(p, gl.LINK_STATUS) ? p : null;
}

/**
 * The live sky: one full-screen fragment shader on its own small canvas inside `.cw-bg`, under the
 * 3D world. It is drawn from the scroll director's frame loop (no second rAF), at a fraction of the
 * screen resolution (the sky is smooth), and it reads the colours the director publishes in
 * `story.sky`. If WebGL2 or the shader fails, it hides itself and the CSS gradient underneath is the sky.
 *
 * It also runs the tier frame monitor (perf/tier.ts) for the page, after a warm-up: slow frames
 * demote full to lite and lite to static (which stops this canvas); a fast desktop is promoted to full.
 */
export default function Sky({ mobile, promotable }: { mobile: boolean; promotable: boolean }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const gl = canvas.getContext("webgl2", { alpha: false, antialias: false, depth: false, stencil: false, powerPreference: "low-power" });
    const prog = gl ? program(gl) : null;
    if (!gl || !prog) {
      story.tier = "static";
      canvas.hidden = true;
      return;
    }
    gl.useProgram(prog);
    const loc = {} as Record<(typeof SKY_UNIFORMS)[number], WebGLUniformLocation | null>;
    for (const name of SKY_UNIFORMS) loc[name] = gl.getUniformLocation(prog, name);

    const params = newSkyParams();
    const monitor = new FrameMonitor({ mobile, promotable });
    let seen = -1; // last story.sky.v uploaded
    let drawnTier = "";
    let resize = true;
    let time = 0;
    let age = 0;
    let skip = 0;

    const observer = new ResizeObserver(() => {
      resize = true;
    });
    observer.observe(canvas);

    const lost = (event: Event) => {
      event.preventDefault();
      story.tier = "static";
      canvas.hidden = true;
    };
    canvas.addEventListener("webglcontextlost", lost);

    const setTier = (to: typeof story.tier, remember: boolean) => {
      story.tier = to;
      monitor.reset();
      if (remember) writeStoredTier(window.sessionStorage, to);
    };

    const off = onStoryFrame((dt) => {
      age += dt;
      if (!story.paused) time += dt;
      if (age > WARMUP_S && story.tier !== "static") {
        monitor.push(dt * 1000);
        if (monitor.shouldDemote()) setTier(demote(story.tier), true);
        else if (story.tier === "lite" && monitor.shouldPromote()) setTier(promote(story.tier), false);
      }

      const tier = story.tier;
      if (tier === "static") {
        canvas.hidden = true;
        return;
      }
      canvas.hidden = false;
      if (drawnTier !== tier) {
        drawnTier = tier;
        resize = true;
      }
      const s = story.sky;
      const changed = s.v !== seen || resize;
      if (story.paused && !changed) return;
      // While only the slow drift moves, the lite tier draws every other frame (about 30 fps).
      if (tier === "lite" && !changed && (skip += 1) % 2 === 1) return;

      if (resize) {
        resize = false;
        const { w, h } = skyCanvasSize(canvas.clientWidth, canvas.clientHeight, tier, window.devicePixelRatio);
        if (canvas.width !== w) canvas.width = w;
        if (canvas.height !== h) canvas.height = h;
        gl.viewport(0, 0, w, h);
      }
      if (s.v !== seen) {
        seen = s.v;
        gl.uniform3fv(loc.uLabTop, hexToOklab(s.top));
        gl.uniform3fv(loc.uLabMid, hexToOklab(s.mid));
        gl.uniform3fv(loc.uLabHor, hexToOklab(s.horizon));
        gl.uniform3fv(loc.uSun, hexToUnit(s.sun));
      }
      skyParams(s.dark, tier, params);
      gl.uniform2f(loc.uRes, canvas.width, canvas.height);
      gl.uniform1f(loc.uTime, time);
      gl.uniform2f(loc.uSunPos, params.sunX, params.sunY);
      gl.uniform1f(loc.uSunSize, params.sunSize);
      gl.uniform1f(loc.uDisc, params.discAlpha);
      gl.uniform1f(loc.uRays, params.rays);
      gl.uniform1f(loc.uHaze, params.haze);
      gl.uniform1f(loc.uCap, params.cap);
      gl.uniform1f(loc.uFull, tier === "full" ? 1 : 0);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    });

    return () => {
      off();
      observer.disconnect();
      canvas.removeEventListener("webglcontextlost", lost);
      gl.deleteProgram(prog); // (the context is not force-lost: a dev double-mount reuses this canvas's context)
    };
  }, [mobile, promotable]);

  return <canvas ref={ref} className="cw-sky" />;
}
