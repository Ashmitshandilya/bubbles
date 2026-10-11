"use client";

import { Canvas } from "@react-three/fiber";
import * as THREE from "three";
import { Post } from "../post/Composer";
import { Governor } from "./Governor";
import { World } from "./World";
import { story } from "../story/store";

/**
 * The single, persistent WebGL canvas behind the story. Loaded lazily (client only). It renders on demand: the
 * Governor asks for frames from the scroll director's loop, so the page has one animation loop and an idle page
 * costs little. A lost context drops the page to the static tier and WorldMount shows the illustrated Bubbles instead.
 */
export default function WorldCanvas({ eventSource }: { eventSource: HTMLElement }) {
  return (
    <Canvas
      className="cw-canvas"
      eventSource={eventSource}
      eventPrefix="client"
      frameloop="demand"
      dpr={story.mobile ? [1, 1] : [1, 1.5]}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      camera={{ fov: 35, near: 0.1, far: 80, position: [0, 0.55, 10] }}
      onCreated={({ gl }) => {
        gl.toneMapping = THREE.NeutralToneMapping;
        gl.toneMappingExposure = 1.02;
        gl.setClearColor(0x000000, 0);
        gl.domElement.addEventListener("webglcontextlost", (event) => {
          event.preventDefault();
          story.tier = "static";
          story.worldLost = true;
        });
      }}
    >
      <Governor />
      <World />
      {/* full tier only: bloom and grade (post/Composer.tsx); nothing is drawn by it in lite */}
      <Post />
    </Canvas>
  );
}
