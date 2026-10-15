"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { Canvas, useFrame, useThree, type ThreeEvent } from "@react-three/fiber";
import { Bvh, Environment, Lightformer, OrbitControls, useGLTF } from "@react-three/drei";
import { Box3, Color, FrontSide, Group, MeshPhysicalMaterial, NeutralToneMapping, Vector3, type BufferGeometry, type Mesh, type Object3D } from "three";
import { ORGAN_TINT, STATUS_META, partOwners, partsOf, type Organ } from "../../app/lib/organ-map";
import type { BodyViewProps } from "./BodyFallback2D";
import { protrudes } from "./groin";
import { SELECTED_SCALE, isSettled, pulse, stepSpring, type SpringState } from "./motion";

// Load with next/dynamic({ ssr: false }) behind an error boundary. A failed model, a lost WebGL context or a missing
// decoder all surface as a thrown error, and the page swaps in the flat body.
//
// The model is quantized (KHR_mesh_quantization, scripts/anatomy) and needs no decoder. Meshopt is not used because its
// decoder compiles WebAssembly, which the site's CSP refuses; Draco is not used because its decoder would come from a
// Google CDN, which the CSP and the privacy notice rule out.

export const MODEL_URL = "/models/body.glb";

type View = "front" | "side" | "back";
const VIEWS: Record<View, [number, number, number]> = { front: [0, 0.06, 1], side: [1, 0.06, 0], back: [0, 0.06, -1] };
const VIEW_LABEL: Record<View, string> = { front: "Front", side: "Side", back: "Back" };
const HOME_TARGET = new Vector3(0, 1.25, 0); // high enough that the head clears the view controls
const HOME_DISTANCE = 2.3;
/** Narrow (phone) frames step back so the whole torso still fits across. */
const homeDistance = (aspect: number) => HOME_DISTANCE * Math.max(1, 0.95 / aspect);
const homePosition = (side: View, aspect: number) =>
  new Vector3(...VIEWS[side]).normalize().multiplyScalar(homeDistance(aspect)).add(HOME_TARGET);
// The skin is a soft pink veil: visible enough to read as a body against the pearl stage, light enough to see the organs through it.
const SHELL_OPACITY: Record<string, number> = { skin: 0.17, skeleton: 0.28 };
// The skin and skeleton wrap everything; a pointer only lands on them when no organ sits under it.
const SHELLS = new Set(["skin", "skeleton"]);
// Painted in the model itself (white of the eye, iris, pupil, nerve): the organ colour must not replace those colours.
const PAINTED = new Set(["eye_left", "eye_right"]);

interface Controls {
  target: Vector3;
  update: () => void;
  addEventListener: (type: "start", listener: () => void) => void;
  removeEventListener: (type: "start", listener: () => void) => void;
}

function useReducedMotion() {
  return useSyncExternalStore(
    (notify) => {
      const query = window.matchMedia("(prefers-reduced-motion: reduce)");
      query.addEventListener("change", notify);
      return () => query.removeEventListener("change", notify);
    },
    () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    () => true,
  );
}

const token = (name: string) => {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return new Color(value || "#ffffff");
};

/** Which organ a pointer means: the nearest organ under it, else the skeleton, else the skin. */
function pick(event: ThreeEvent<PointerEvent | MouseEvent>, owners: ReadonlyMap<string, Organ>): string | null {
  const parts = event.intersections.map((hit) => hit.object.name).filter((part) => owners.has(part));
  const part = parts.find((p) => !SHELLS.has(p)) ?? parts.find((p) => p === "skeleton") ?? parts[0];
  return part ? owners.get(part)!.id : null;
}

interface BodyProps extends BodyViewProps {
  onReady: () => void;
  reduced: boolean;
}

function Body({ anatomy = "neutral", organs, selected, hovered, onSelect, onHover, onReady, reduced }: BodyProps) {
  const { scene } = useGLTF(MODEL_URL, false, false);
  const invalidate = useThree((s) => s.invalidate);
  const canvas = useThree((s) => s.gl.domElement);
  const owners = useMemo(() => partOwners(organs), [organs]);
  const opening = useRef<string | null | undefined>(undefined);
  const moved = useRef(false);
  // The organ the person chose (never the page's opening pick): it bumps up and, on a computer, gently pulses.
  const pumpId = useRef<string | null>(null);
  const springs = useRef(new Map<string, SpringState>());
  const pivots = useRef(new Map<string, Group>());
  const phone = useRef(false);

  // One soft material per mesh. Organs are opaque satin; the skeleton is translucent ivory; the skin a faint pearl shell.
  const materials = useMemo(() => {
    const white = token("--bubbles-white");
    const phone = window.matchMedia("(pointer: coarse)").matches;
    const made = new Map<string, MeshPhysicalMaterial>();
    scene.traverse((object: Object3D) => {
      const mesh = object as Mesh;
      if (!mesh.isMesh) return;
      const id = mesh.name;
      let material: MeshPhysicalMaterial;
      if (id === "skin") {
        material = new MeshPhysicalMaterial({ color: white.clone().lerp(token("--tint-pink"), 0.45), roughness: 0.4, transparent: true, opacity: SHELL_OPACITY.skin, depthWrite: false, side: FrontSide });
      } else if (id === "skeleton") {
        material = new MeshPhysicalMaterial({ color: token("--tint-sun").lerp(white, 0.35), roughness: 0.55, transparent: true, opacity: SHELL_OPACITY.skeleton, depthWrite: false });
      } else if (PAINTED.has(id)) {
        material = new MeshPhysicalMaterial({ vertexColors: true, roughness: 0.28, clearcoat: phone ? 0 : 1, clearcoatRoughness: 0.12 });
      } else if (phone) {
        // ponytail: clearcoat and sheen are two extra lighting passes per pixel over ~400k triangles; phones get plain satin.
        // Unmeasured on a real mid-range Android: profile one there before bringing them back.
        material = new MeshPhysicalMaterial({ roughness: 0.5 });
      } else {
        material = new MeshPhysicalMaterial({ roughness: 0.48, clearcoat: 0.45, clearcoatRoughness: 0.45, sheen: 0.6, sheenColor: white, sheenRoughness: 0.6 });
      }
      material.userData.base = material.color.clone();
      made.set(id, material);
    });
    return made;
  }, [scene]);

  // Put on in an effect, not in the memo: a render may run twice (Strict Mode) and only the kept result may own the meshes.
  useEffect(() => {
    scene.traverse((object: Object3D) => {
      const mesh = object as Mesh;
      const material = mesh.isMesh ? materials.get(mesh.name) : undefined;
      if (!material) return;
      mesh.material = material;
      mesh.renderOrder = mesh.name === "skin" ? 2 : mesh.name === "skeleton" ? 1 : 0;
    });
    onReady();
    return () => {
      for (const material of materials.values()) material.dispose();
    };
  }, [scene, materials, onReady]);

  // Each organ part sits in a pivot at its own centre, so scaling it swells the organ in place instead of drifting it.
  useEffect(() => {
    phone.current = window.matchMedia("(pointer: coarse)").matches;
    const meshes: Mesh[] = [];
    scene.traverse((object: Object3D) => {
      const mesh = object as Mesh;
      if (mesh.isMesh && !SHELLS.has(mesh.name)) meshes.push(mesh);
    });
    for (const mesh of meshes) {
      let pivot = mesh.userData.pivot as Group | undefined;
      if (!pivot) {
        const parent = mesh.parent;
        if (!parent) continue;
        pivot = new Group();
        pivot.name = `pivot-${mesh.name}`;
        // A part may say where it turns from (the eyes: the middle of the eyeball, not of the eyeball plus its nerve).
        const own = mesh.userData.center as number[] | undefined;
        const center = Array.isArray(own) && own.length === 3 ? mesh.localToWorld(new Vector3(...own)) : new Box3().setFromObject(mesh).getCenter(new Vector3());
        pivot.position.copy(parent.worldToLocal(center));
        parent.add(pivot);
        mesh.position.sub(pivot.position);
        pivot.add(mesh);
        mesh.userData.pivot = pivot;
      }
      pivots.current.set(mesh.name, pivot);
    }
  }, [scene]);

  // A female profile leaves the protruding groin patch out of the skin shell (groin.ts); any other profile gets the model as it is.
  useEffect(() => {
    const skin = scene.getObjectByName("skin") as Mesh | undefined;
    if (!skin?.isMesh) return;
    const original = (skin.userData.originalGeometry ??= skin.geometry) as BufferGeometry;
    if (anatomy !== "female") {
      skin.geometry = original;
      invalidate();
      return;
    }
    const position = original.getAttribute("position");
    skin.updateWorldMatrix(true, false);
    const point = new Vector3();
    const out = new Uint8Array(position.count);
    for (let i = 0; i < position.count; i += 1) {
      point.fromBufferAttribute(position, i).applyMatrix4(skin.matrixWorld);
      out[i] = protrudes(point.x, point.y, point.z) ? 1 : 0;
    }
    const index = original.getIndex();
    const total = index ? index.count : position.count;
    const kept: number[] = [];
    for (let t = 0; t + 2 < total; t += 3) {
      const a = index ? index.getX(t) : t;
      const b = index ? index.getX(t + 1) : t + 1;
      const c = index ? index.getX(t + 2) : t + 2;
      if (!out[a] && !out[b] && !out[c]) kept.push(a, b, c);
    }
    
    const trimmed = original.clone();
    trimmed.setIndex(kept);
    skin.geometry = trimmed;
    invalidate();
    return () => {
      skin.geometry = original;
      trimmed.dispose();
    };
  }, [scene, anatomy, invalidate]);

  // Status shows as a calm emissive glow over the organ's own tint. "No data" organs are muted and never glow.
  useEffect(() => {
    const muted = token("--bubbles-line-strong");
    // Only a choice the person makes pulls one organ forward; the page's opening pick leaves the body as a whole.
    if (opening.current === undefined) opening.current = selected;
    else if (selected !== opening.current) moved.current = true;
    const focus = moved.current && selected !== null && partsOf(selected).some((part) => !SHELLS.has(part) && materials.has(part));
    // A part with no organ in the map (uterus and ovaries for someone who doesn't use Cycle) is not drawn at all.
    scene.traverse((object: Object3D) => {
      if ((object as Mesh).isMesh) object.visible = owners.has(object.name);
    });
    for (const [id, material] of materials) {
      const organ = owners.get(id);
      const status = organ?.status ?? "no_data";
      const glow = status === "no_data" ? new Color(0, 0, 0) : token(STATUS_META[status].color);
      const active = organ !== undefined && organ.id === selected;
      const near = organ !== undefined && organ.id === hovered;
      if (SHELLS.has(id)) {
        const base = material.userData.base as Color;
        material.color.copy(base);
        material.opacity = SHELL_OPACITY[id] + (active ? 0.22 : near ? 0.12 : 0);
      } else {
        // With an organ chosen, the others step back (translucent) so the chosen one can be seen through them.
        const recede = focus && !active;
        material.transparent = recede;
        material.opacity = recede ? 0.32 : 1;
        material.depthWrite = !recede;
        material.needsUpdate = true;
        if (PAINTED.has(id)) {
          material.color.set(0xffffff);
        } else {
          const tint = token(ORGAN_TINT[id] ?? "--tint-pink");
          const fill = token((ORGAN_TINT[id] ?? "--tint-pink").replace("--tint-", "--bubbles-"));
          material.color.copy(tint).lerp(fill, status === "no_data" ? 0.15 : 0.55);
          if (status === "no_data") material.color.lerp(muted, 0.35);
        }
      }
      material.emissive.copy(glow);
      // Painted parts glow less so the iris and the white of the eye stay readable.
      const strength = PAINTED.has(id) ? 0.45 : 1;
      material.emissiveIntensity = (status === "no_data" ? 0 : active ? 0.7 : near ? 0.45 : 0.22) * strength;
    }
    pumpId.current = focus ? selected : null;
    invalidate();
  }, [scene, materials, owners, selected, hovered, invalidate]);

  // The bump: a slightly under-damped spring to a larger size, then (on a computer) a gentle pulse. Reduced motion just takes the larger size.
  useFrame((state, delta) => {
    let moving = false;
    for (const organ of organs) {
      const chosen = organ.id === pumpId.current;
      const target = chosen ? SELECTED_SCALE : 1;
      const spring = springs.current.get(organ.id) ?? { x: 1, v: 0 };
      const next = reduced ? { x: target, v: 0 } : stepSpring(spring, target, delta);
      springs.current.set(organ.id, next);
      const beating = chosen && !reduced && !phone.current;
      const scale = next.x * (1 + (beating ? pulse(organ.id, state.clock.elapsedTime) : 0));
      for (const part of partsOf(organ.id)) pivots.current.get(part)?.scale.setScalar(scale);
      if (beating || !isSettled(next, target)) moving = true;
    }
    if (moving) state.invalidate();
  });

  useEffect(() => () => void (canvas.style.cursor = ""), [canvas]);

  return (
    <Bvh
      onPointerMove={(event) => {
        event.stopPropagation();
        const id = pick(event, owners);
        canvas.style.cursor = id ? "pointer" : "";
        if (id !== hovered) onHover(id);
      }}
      onPointerOut={() => {
        canvas.style.cursor = "";
        onHover(null);
      }}
      onClick={(event) => {
        event.stopPropagation();
        if (event.delta > 6) return; // that was a drag to turn the body, not a tap
        const id = pick(event, owners);
        if (id) onSelect(id);
      }}
    >
      <primitive object={scene} />
    </Bvh>
  );
}

function Sky() {
  const [top, bottom] = useMemo(() => [token("--bubbles-white"), token("--tint-pink")], []);
  return <hemisphereLight args={[top, bottom, 0.55]} />;
}

/** Eases the camera to a goal; any drag or zoom by the person cancels it immediately. */
function CameraRig({ selected, view, ready, reduced }: { selected: string | null; view: { side: View; nonce: number }; ready: boolean; reduced: boolean }) {
  const camera = useThree((s) => s.camera);
  const scene = useThree((s) => s.scene);
  const invalidate = useThree((s) => s.invalidate);
  const controls = useThree((s) => s.controls) as unknown as Controls | null;
  const aspect = useThree((s) => s.size.width / Math.max(1, s.size.height));
  const goal = useRef<{ position: Vector3; target: Vector3 } | null>(null);
  const lastSelected = useRef<string | null | undefined>(undefined);
  const placed = useRef(false);

  useEffect(() => {
    if (!controls || placed.current) return;
    placed.current = true;
    camera.position.copy(homePosition("front", aspect));
    controls.target.copy(HOME_TARGET);
    controls.update();
    invalidate();
  }, [controls, camera, aspect, invalidate]);

  useEffect(() => {
    if (!controls) return;
    const cancel = () => void (goal.current = null);
    controls.addEventListener("start", cancel);
    return () => controls.removeEventListener("start", cancel);
  }, [controls]);

  // Front, side and back always show the whole torso from that side.
  useEffect(() => {
    if (view.nonce === 0) return;
    goal.current = { target: HOME_TARGET.clone(), position: homePosition(view.side, aspect) };
    invalidate();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- a resize alone must not move the camera
  }, [view, invalidate]);

  // A new selection keeps the current viewing angle and moves in on the organ. The first selection after load is the
  // page's default, so the opening shot stays on the whole body.
  useEffect(() => {
    if (!ready || !controls) return;
    if (lastSelected.current === undefined) {
      lastSelected.current = selected;
      return;
    }
    if (lastSelected.current === selected) return;
    lastSelected.current = selected;
    const parts = selected ? partsOf(selected).filter((part) => !SHELLS.has(part)) : [];
    const objects = parts.map((part) => scene.getObjectByName(part)).filter((o): o is Object3D => o !== undefined);
    const direction = camera.position.clone().sub(controls.target).normalize();
    let target = HOME_TARGET.clone();
    let distance = homeDistance(aspect);
    if (objects.length) {
      const box = new Box3();
      for (const object of objects) box.expandByObject(object);
      target = box.getCenter(new Vector3());
      distance = Math.min(1.3, Math.max(0.5, box.getSize(new Vector3()).length() * 3.4)); // small parts (eyes, thyroid) get a close shot
    }
    goal.current = { target, position: direction.multiplyScalar(distance).add(target) };
    invalidate();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- a resize alone must not move the camera
  }, [selected, ready, controls, camera, scene, invalidate]);

  useFrame((_, delta) => {
    const g = goal.current;
    if (!g || !controls) return;
    const k = reduced ? 1 : 1 - Math.exp(-delta * 4.5);
    camera.position.lerp(g.position, k);
    controls.target.lerp(g.target, k);
    controls.update();
    if (camera.position.distanceToSquared(g.position) < 1e-6 && controls.target.distanceToSquared(g.target) < 1e-6) goal.current = null;
    else invalidate();
  });

  return null;
}

const CONTROL =
  "inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded-full px-4 text-body-sm font-extrabold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-bubbles-grape";

export default function BodyViewer(props: BodyViewProps) {
  const reduced = useReducedMotion();
  const [ready, setReady] = useState(false);
  const [spin, setSpin] = useState(false);
  const [view, setView] = useState<{ side: View; nonce: number }>({ side: "front", nonce: 0 });
  const [lost, setLost] = useState(false);
  const onReady = useMemo(() => () => setReady(true), []);
  const glCanvas = useRef<HTMLCanvasElement | null>(null);
  const onContextLost = useCallback((event: Event) => {
    event.preventDefault();
    setLost(true);
  }, []);
  useEffect(() => () => glCanvas.current?.removeEventListener("webglcontextlost", onContextLost), [onContextLost]);
  const turning = spin && !reduced;

  if (lost) throw new Error("WebGL context lost"); // the page's boundary swaps in the flat body

  return (
    <div className="relative h-full w-full">
      <div className="absolute inset-0" role="img" aria-label="3D body model. Use the list of body parts to choose one.">
        <Canvas
          frameloop={turning ? "always" : "demand"}
          dpr={[1, 1.75]}
          camera={{ position: [0, HOME_TARGET.y + 0.11, HOME_DISTANCE], fov: 32, near: 0.05, far: 20 }}
          gl={{ antialias: true, alpha: true, powerPreference: "high-performance", toneMapping: NeutralToneMapping }}
          onCreated={({ gl }) => {
            glCanvas.current = gl.domElement;
            gl.domElement.addEventListener("webglcontextlost", onContextLost);
          }}
        >
          {/* Studio light built in the scene itself: no HDR file is fetched. */}
          <Environment resolution={128} frames={1}>
            <Lightformer form="rect" intensity={2.2} position={[0, 2.5, 3]} scale={[4, 1.6, 1]} />
            <Lightformer form="rect" intensity={1.1} position={[-3, 1.4, 0.5]} rotation-y={Math.PI / 2} scale={[3, 2, 1]} />
            <Lightformer form="rect" intensity={1.4} position={[3, 1.6, -1.5]} rotation-y={-Math.PI / 2} scale={[3, 2, 1]} />
            <Lightformer form="circle" intensity={0.8} position={[0, 3.5, -2]} scale={2} />
          </Environment>
          <Sky />
          <directionalLight position={[1.2, 2.8, 2.4]} intensity={0.9} />

          <Suspense fallback={null}>
            <Body {...props} onReady={onReady} reduced={reduced} />
          </Suspense>

          <OrbitControls
            makeDefault
            target={[HOME_TARGET.x, HOME_TARGET.y, HOME_TARGET.z]}
            enablePan={false}
            enableDamping={!reduced}
            dampingFactor={0.08}
            rotateSpeed={0.6}
            zoomSpeed={0.7}
            minDistance={0.45}
            maxDistance={3.2}
            minPolarAngle={0.3}
            maxPolarAngle={Math.PI - 0.3}
            autoRotate={turning}
            autoRotateSpeed={0.45}
          />
          <CameraRig selected={props.selected} view={view} ready={ready} reduced={reduced} />
        </Canvas>
      </div>

      {!ready && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center" role="status">
          <span className="rounded-full bg-surface/90 px-4 py-2 text-body-sm font-bold text-muted shadow-[var(--shadow-sm)]">
            Loading the body model…
          </span>
        </div>
      )}

      <div className="absolute left-3 top-3 flex flex-wrap gap-2">
        <div role="group" aria-label="Camera view" className="inline-flex rounded-full border border-line bg-surface/90 p-1 shadow-[var(--shadow-xs)] backdrop-blur">
          {(Object.keys(VIEWS) as View[]).map((side) => {
            const on = view.side === side;
            return (
              <button
                key={side}
                type="button"
                aria-pressed={on}
                disabled={!ready}
                onClick={() => setView((v) => ({ side, nonce: v.nonce + 1 }))}
                className={`${CONTROL} ${on ? "bg-ink text-white" : "text-ink-soft hover:bg-blush"} disabled:opacity-50`}
              >
                {VIEW_LABEL[side]}
              </button>
            );
          })}
        </div>
        {!reduced && (
          <span className="hidden sm:block">
          <button
            type="button"
            aria-pressed={spin}
            disabled={!ready}
            onClick={() => setSpin((s) => !s)}
            className={`${CONTROL} border border-line bg-surface/90 text-ink-soft shadow-[var(--shadow-xs)] backdrop-blur hover:bg-blush aria-pressed:bg-ink aria-pressed:text-white disabled:opacity-50`}
          >
            Turn slowly
          </button>
          </span>
        )}
      </div>
    </div>
  );
}
