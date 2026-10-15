"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Billboard, OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import { BODY_FILL, BODY_OUTLINE, SELECT_GLOW, statusColor } from "./anatomy/palette";
import { SELECTED_SCALE, easeFactor, isSettled, organOpacity, pulse, stepSpring, type SpringState } from "./anatomy/motion";
import { figure, organLabel, organsFor, type Anatomy, type OrganSpec, type Part } from "./anatomy/presets";

// Load with next/dynamic({ ssr: false }) behind an error boundary: three.js is heavy and WebGL can fail on any device.
// The accessible source of truth is the list view rendered by the caller; this canvas is a visual extra.
// The shapes live in ./anatomy/presets (data), the colours in ./anatomy/palette and the bump / pulse maths in ./anatomy/motion,
// each with its own tests.

const HOME_TARGET = new THREE.Vector3(0, -0.12, 0);
const HOME_DISTANCE = 3.9;
const FOCUS_DISTANCE = 3.0;

function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return reduced;
}

function PartGeometry({ part }: { part: Part }) {
  return part.geometry === "sphere" ? (
    <sphereGeometry args={[part.args[0], 32, 24]} />
  ) : (
    <capsuleGeometry args={[part.args[0], part.args[1], 8, 20]} />
  );
}

const OUTLINE = 0.013;

/** The part grown by the outline width: a sphere's scale, a capsule's radius. Used for the back-face shell that draws the silhouette line. */
function shellOf(part: Part): { args: number[]; scale: [number, number, number] | undefined } {
  if (part.geometry === "capsule") return { args: [part.args[0] + OUTLINE, part.args[1]], scale: part.scale };
  const grow = 1 + OUTLINE / part.args[0];
  const [x, y, z] = part.scale ?? [1, 1, 1];
  return { args: part.args, scale: [x * grow, y * grow, z * grow] };
}

/** The silhouette: translucent, but clearly drawn (fill + outline). Organs are drawn after it and are always visible through it. */
function Body({ anatomy }: { anatomy: Anatomy }) {
  const parts = useMemo(() => figure(anatomy), [anatomy]);
  return (
    <group>
      {parts.map((part) => {
        const shell = shellOf(part);
        return (
          <group key={part.id}>
            <mesh position={part.position} scale={shell.scale} rotation={part.rotation} renderOrder={-1}>
              <PartGeometry part={{ ...part, args: shell.args }} />
              <meshBasicMaterial color={BODY_OUTLINE} side={THREE.BackSide} transparent opacity={0.9} depthWrite={false} />
            </mesh>
            <mesh position={part.position} scale={part.scale} rotation={part.rotation} renderOrder={0}>
              <PartGeometry part={part} />
              <meshStandardMaterial color={BODY_FILL} emissive={BODY_FILL} emissiveIntensity={0.2} transparent opacity={0.93} depthWrite={false} roughness={0.85} />
            </mesh>
          </group>
        );
      })}
    </group>
  );
}

function OrganMesh({
  spec, status, selected, anySelected, reduced, onSelect,
}: {
  spec: OrganSpec;
  status: string | undefined;
  selected: boolean;
  anySelected: boolean;
  reduced: boolean;
  onSelect: (id: string) => void;
}) {
  const group = useRef<THREE.Group>(null);
  const halo = useRef<THREE.Mesh>(null);
  const spring = useRef<SpringState>({ x: 1, v: 0 });
  const glow = useRef(0);
  const opacity = useRef(1);
  // One material per organ, shared by its parts (a pair of lungs lights up as one).
  const material = useMemo(
    () => new THREE.MeshStandardMaterial({ roughness: 0.4, metalness: 0.05, transparent: true, emissive: new THREE.Color(SELECT_GLOW), emissiveIntensity: 0 }),
    [],
  );
  useEffect(() => {
    material.color.set(statusColor(status));
  }, [material, status]);
  useEffect(() => () => material.dispose(), [material]);

  useFrame((state, dt) => {
    const target = selected ? SELECTED_SCALE : 1;
    // Reduced motion: no spring, no pulse, no fade. The organ just takes its highlighted look.
    spring.current = reduced ? { x: target, v: 0 } : stepSpring(spring.current, target, dt);
    const beat = selected && !reduced ? pulse(spec.id, state.clock.elapsedTime) : 0;
    group.current?.scale.setScalar(spring.current.x * (1 + beat));

    const k = reduced ? 1 : easeFactor(dt, 10);
    const glowTarget = selected ? 0.55 : 0;
    const opacityTarget = organOpacity(selected, anySelected);
    glow.current += (glowTarget - glow.current) * k;
    opacity.current += (opacityTarget - opacity.current) * k;
    material.emissiveIntensity = glow.current;
    material.opacity = opacity.current;
    if (halo.current) {
      const haloMaterial = halo.current.material as THREE.MeshBasicMaterial;
      haloMaterial.opacity = (glow.current / 0.55) * 0.65;
      halo.current.visible = haloMaterial.opacity > 0.01;
    }

    const moving = !isSettled(spring.current, target) || Math.abs(glow.current - glowTarget) > 0.005 || Math.abs(opacity.current - opacityTarget) > 0.005;
    if (moving || (selected && !reduced)) state.invalidate();   // the canvas only draws when something changes
  });

  const [fx, fy, fz] = spec.focus;
  return (
    <group ref={group} position={spec.focus}>
      {spec.parts.map((part, i) => (
        <mesh
          key={`${spec.id}-${i}`}
          position={[part.position[0] - fx, part.position[1] - fy, part.position[2] - fz]}
          scale={part.scale}
          rotation={part.rotation}
          material={material}
          renderOrder={2}
        >
          <PartGeometry part={part} />
        </mesh>
      ))}
      {/* invisible, generous tap targets: tiny organs (eyes, thyroid) must be easy to hit */}
      {spec.parts.map((part, i) => (
        <mesh
          key={`hit-${spec.id}-${i}`}
          position={[part.position[0] - fx, part.position[1] - fy, part.position[2] - fz]}
          onClick={(event) => {
            event.stopPropagation();
            onSelect(spec.id);
          }}
          onPointerOver={(event) => {
            event.stopPropagation();
            document.body.style.cursor = "pointer";
          }}
          onPointerOut={() => {
            document.body.style.cursor = "";
          }}
        >
          <sphereGeometry args={[spec.hit, 12, 12]} />
          <meshBasicMaterial transparent opacity={0} depthWrite={false} />
        </mesh>
      ))}
      <Billboard>
        <mesh ref={halo} renderOrder={5} visible={false}>
          <ringGeometry args={[spec.hit * 0.9, spec.hit * 1.04, 48]} />
          <meshBasicMaterial color={SELECT_GLOW} transparent opacity={0} depthTest={false} toneMapped={false} />
        </mesh>
      </Billboard>
    </group>
  );
}

/** Eases the view to the selected organ when the selection changes, and stops the moment the person drags. */
function CameraRig({
  focus, controls, reduced, dragging,
}: {
  focus: THREE.Vector3 | null;
  controls: React.RefObject<{ target: THREE.Vector3; update: () => boolean } | null>;
  reduced: boolean;
  dragging: React.RefObject<boolean>;
}) {
  const camera = useThree((state) => state.camera);
  const invalidate = useThree((state) => state.invalidate);
  const easing = useRef(false);
  const desired = useRef(new THREE.Vector3());
  const offset = useRef(new THREE.Vector3());
  const focusKey = focus ? `${focus.x},${focus.y},${focus.z}` : "home";

  useEffect(() => {
    if (reduced) return;               // reduced motion: the view never moves by itself
    easing.current = true;
    invalidate();
  }, [focusKey, reduced, invalidate]);

  useFrame((_state, dt) => {
    const orbit = controls.current;
    if (!orbit || !easing.current || reduced) return;
    if (dragging.current) {
      easing.current = false;          // never fight a hand on the model
      return;
    }
    if (focus) desired.current.set(focus.x * 0.8, focus.y * 0.8, focus.z * 0.5);
    else desired.current.copy(HOME_TARGET);
    const k = easeFactor(dt, 5);
    orbit.target.lerp(desired.current, k);
    offset.current.copy(camera.position).sub(orbit.target);
    const distance = offset.current.length();
    const wanted = focus ? FOCUS_DISTANCE : HOME_DISTANCE;
    camera.position.copy(orbit.target).add(offset.current.setLength(distance + (wanted - distance) * k));
    orbit.update();
    if (orbit.target.distanceTo(desired.current) < 0.004 && Math.abs(distance - wanted) < 0.01) easing.current = false;
    else invalidate();
  });
  return null;
}

export default function Anatomy3D({
  onSelect,
  organStatus,
  selected,
  anatomy = "neutral",
  organs,
}: {
  onSelect: (id: string) => void;
  organStatus: Record<string, string>;
  selected?: string;
  /** Which body to draw. Defaults to a neutral body. */
  anatomy?: Anatomy;
  /** Which body systems to draw. Defaults to the ones in `organStatus`. */
  organs?: readonly string[];
}) {
  const [webgl, setWebgl] = useState<"checking" | "ok" | "unsupported">("checking");
  const reduced = useReducedMotion();
  const controls = useRef<{ target: THREE.Vector3; update: () => boolean } | null>(null);
  const dragging = useRef(false);

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

  const wanted = organs ?? Object.keys(organStatus);
  const wantedKey = wanted.join(",");
  // eslint-disable-next-line react-hooks/exhaustive-deps -- wantedKey is the stable form of `wanted`
  const specs = useMemo(() => organsFor(anatomy, wanted), [anatomy, wantedKey]);
  const selectedSpec = specs.find((spec) => spec.id === selected);
  const focus = useMemo(() => (selectedSpec ? new THREE.Vector3(...selectedSpec.focus) : null), [selectedSpec]);

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
      <Canvas
        frameloop="demand"
        camera={{ position: [0, -0.05, HOME_DISTANCE], fov: 45 }}
        dpr={[1, 2]}
        style={{ width: "100%", height: "100%" }}
      >
        <ambientLight intensity={1.25} />
        <directionalLight position={[2, 3, 4]} intensity={0.8} />
        <directionalLight position={[-3, 2, -3]} intensity={0.4} />
        <OrbitControls
          ref={controls as never}
          target={HOME_TARGET.toArray()}
          enablePan={false}
          minDistance={2}
          maxDistance={5.2}
          onStart={() => {
            dragging.current = true;
          }}
          onEnd={() => {
            dragging.current = false;
          }}
        />
        <CameraRig focus={focus} controls={controls} reduced={reduced} dragging={dragging} />
        <Body anatomy={anatomy} />
        {specs.map((spec) => (
          <OrganMesh
            key={spec.id}
            spec={spec}
            status={organStatus[spec.id]}
            selected={spec.id === selected}
            anySelected={Boolean(selectedSpec)}
            reduced={reduced}
            onSelect={onSelect}
          />
        ))}
      </Canvas>
      {selectedSpec && (
        <p className="pointer-events-none absolute left-3 top-3 rounded-full bg-surface/90 px-3 py-1 text-[0.8125rem] font-extrabold text-bubbles-grape-deep">
          {organLabel(selectedSpec.id, anatomy)}
        </p>
      )}
      <p className="pointer-events-none absolute bottom-3 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full bg-surface/85 px-3 py-1 text-[0.8125rem] font-bold text-muted">
        Drag to turn · tap an organ to select it
      </p>
    </div>
  );
}
