"use client";

import { useEffect, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";

// Load with next/dynamic({ ssr: false }) behind an error boundary: three.js is heavy
// and WebGL can fail on any device. The accessible source of truth is the list view
// rendered by the caller; this canvas is a visual extra.

const STATUS_COLOR: Record<string, string> = {
  unknown: "#E6DDF0",
  no_major_risk_signal: "#22C39A",
  watch: "#FFC83D",
  needs_attention: "#FF9F6B",
};

// Organ positions inside a simple standing body (y up, ~2 units tall).
const ORGAN_POSITIONS: Record<string, [number, number, number]> = {
  brain: [0, 1.02, 0.05],
  lungs: [0.2, 0.45, 0.08],
  heart: [-0.12, 0.38, 0.16],
  liver: [-0.2, 0.12, 0.12],
  pancreas: [0.14, 0.02, 0.14],
  kidneys: [0.24, -0.06, -0.06],
  digestive_system: [0, -0.2, 0.14],
  reproductive_system: [0, -0.48, 0.12],
  musculoskeletal_system: [0.24, -0.95, 0.04],
};

export default function Anatomy3D({
  onSelect,
  organStatus,
  selected,
}: {
  onSelect: (id: string) => void;
  organStatus: Record<string, string>;
  selected?: string;
}) {
  const [webgl, setWebgl] = useState<"checking" | "ok" | "unsupported">("checking");

  useEffect(() => {
    try {
      setWebgl(document.createElement("canvas").getContext("webgl2") ? "ok" : "unsupported");
    } catch {
      setWebgl("unsupported");
    }
    return () => {
      document.body.style.cursor = "";
    };
  }, []);

  if (webgl !== "ok") {
    return (
      <div className="flex h-full min-h-[320px] w-full items-center justify-center rounded-3xl bg-blush p-6 text-center">
        <p className="max-w-xs text-body-sm font-bold text-muted" role="status">
          {webgl === "checking"
            ? "Getting the 3D body ready…"
            : "3D isn't supported in this browser. The list view shows everything."}
        </p>
      </div>
    );
  }

  return (
    <div className="relative h-full min-h-[320px] w-full overflow-hidden rounded-3xl bg-blush" aria-hidden="true">
      <Canvas camera={{ position: [0, 0.1, 3.4], fov: 45 }} dpr={[1, 2]} style={{ width: "100%", height: "100%" }}>
        <ambientLight intensity={0.85} />
        <directionalLight position={[2, 3, 4]} intensity={0.9} />
        <OrbitControls enablePan={false} minDistance={2.4} maxDistance={5} />

        {/* Soft body silhouette */}
        <group>
          <mesh position={[0, 1.02, 0]}>
            <sphereGeometry args={[0.26, 32, 32]} />
            <meshStandardMaterial color="#FFFFFF" transparent opacity={0.55} />
          </mesh>
          <mesh position={[0, 0.05, 0]}>
            <capsuleGeometry args={[0.42, 0.9, 12, 24]} />
            <meshStandardMaterial color="#FFE3EF" transparent opacity={0.45} />
          </mesh>
          {[-0.2, 0.2].map((x) => (
            <mesh key={x} position={[x, -0.95, 0]}>
              <capsuleGeometry args={[0.13, 0.7, 8, 16]} />
              <meshStandardMaterial color="#FFE3EF" transparent opacity={0.45} />
            </mesh>
          ))}
        </group>

        {Object.entries(ORGAN_POSITIONS).map(([organ, position]) => {
          const isSelected = organ === selected;
          return (
            <mesh
              key={organ}
              position={position}
              scale={isSelected ? 1.35 : 1}
              onClick={(event) => {
                event.stopPropagation();
                onSelect(organ);
              }}
              onPointerOver={() => (document.body.style.cursor = "pointer")}
              onPointerOut={() => (document.body.style.cursor = "")}
            >
              <sphereGeometry args={[0.1, 32, 32]} />
              <meshStandardMaterial
                color={STATUS_COLOR[organStatus[organ] ?? "unknown"] ?? STATUS_COLOR.unknown}
                emissive={isSelected ? "#6A45F5" : "#000000"}
                emissiveIntensity={isSelected ? 0.35 : 0}
              />
            </mesh>
          );
        })}
      </Canvas>
      <p className="pointer-events-none absolute bottom-3 left-0 right-0 text-center text-[0.8125rem] font-bold text-muted">
        Drag to turn · tap a dot to select
      </p>
    </div>
  );
}
