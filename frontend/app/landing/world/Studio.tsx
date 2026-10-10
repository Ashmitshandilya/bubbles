"use client";

import { useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { story } from "../story/store";
import { DOME_FRAG, DOME_VERT, ENV_GAIN, ENV_INTENSITY, ENV_SIZE, LIGHT_POS, envDue, envKey, lightRig } from "./studioRig";

/**
 * The studio is the sky on screen. Its environment (what beads, pearls and bubbles reflect) is a small
 * gradient dome built from the director's current sky colours and turned into reflections with PMREM, rebuilt
 * at most four times a second and only while the colours change (a chapter hand-over). The lights take their
 * colours from the same sky: one key from the upper left, a rim on the other side in the horizon colour.
 * Replaces the stock RoomEnvironment (plan 2.4).
 */
export function Studio() {
  const gl = useThree((state) => state.gl);
  const scene = useThree((state) => state.scene);

  const lights = {
    hemi: useRef<THREE.HemisphereLight>(null),
    key: useRef<THREE.DirectionalLight>(null),
    fill: useRef<THREE.DirectionalLight>(null),
    rim: useRef<THREE.DirectionalLight>(null),
    rim2: useRef<THREE.DirectionalLight>(null),
  };

  // The dome scene and the built reflections. Everything GPU-side is created in the effect below and released in its cleanup.
  const dome = useMemo(
    () => ({
      uniforms: {
        uTop: { value: new THREE.Color() },
        uMid: { value: new THREE.Color() },
        uHor: { value: new THREE.Color() },
        uKey: { value: new THREE.Color() },
        uGain: { value: ENV_GAIN },
      },
    }),
    [],
  );
  const env = useRef({ target: null as THREE.WebGLRenderTarget | null, key: "", at: -Infinity, lightsSeen: -1 });
  const build = useRef<null | (() => void)>(null);

  useEffect(() => {
    const pmrem = new THREE.PMREMGenerator(gl);
    const geometry = new THREE.SphereGeometry(10, 24, 16);
    const material = new THREE.ShaderMaterial({
      uniforms: dome.uniforms,
      vertexShader: DOME_VERT,
      fragmentShader: DOME_FRAG,
      side: THREE.BackSide,
      depthWrite: false,
    });
    const domeScene = new THREE.Scene();
    domeScene.add(new THREE.Mesh(geometry, material));
    const state = env.current;

    build.current = () => {
      const sky = story.sky;
      dome.uniforms.uTop.value.set(sky.top);
      dome.uniforms.uMid.value.set(sky.mid);
      dome.uniforms.uHor.value.set(sky.horizon);
      dome.uniforms.uKey.value.set(sky.key);
      const next = pmrem.fromScene(domeScene, 0, 0.1, 50, { size: ENV_SIZE });
      const old = state.target;
      state.target = next;
      scene.environment = next.texture;
      scene.environmentIntensity = ENV_INTENSITY;
      old?.dispose();
      state.key = envKey(sky);
      state.at = performance.now();
    };
    build.current();

    return () => {
      build.current = null;
      scene.environment = null;
      state.target?.dispose();
      state.target = null;
      state.key = "";
      state.at = -Infinity;
      geometry.dispose();
      material.dispose();
      pmrem.dispose();
    };
  }, [gl, scene, dome]);

  useFrame(() => {
    const sky = story.sky;
    const state = env.current;
    if (build.current && envDue(state.at, performance.now(), state.key, envKey(sky))) build.current();

    if (state.lightsSeen === sky.v) return;
    state.lightsSeen = sky.v;
    const rig = lightRig(sky);
    const { hemi, key, fill, rim, rim2 } = lights;
    if (hemi.current) {
      hemi.current.color.set(rig.hemiSky);
      hemi.current.groundColor.set(rig.hemiGround);
      hemi.current.intensity = rig.hemi;
    }
    if (key.current) key.current.color.set(rig.key);
    if (fill.current) fill.current.color.set(rig.fill);
    if (rim.current) {
      rim.current.color.set(rig.rim);
      rim.current.intensity = rig.rimI;
    }
    if (rim2.current) {
      rim2.current.color.set(rig.rim2);
      rim2.current.intensity = rig.rim2I;
    }
  });

  return (
    <>
      <hemisphereLight ref={lights.hemi} args={["#FFF4FA", "#4A2348", 0.85]} />
      {/* the page's key light, from the upper left like the painting's */}
      <directionalLight ref={lights.key} position={[...LIGHT_POS.key]} intensity={2.1} color="#FFF6F2" />
      {/* lavender fill from the right */}
      <directionalLight ref={lights.fill} position={[...LIGHT_POS.fill]} intensity={0.55} color="#D8CCFF" />
      {/* rim from behind on the far side, in the horizon colour: keeps the white silhouette readable on dark scenes */}
      <directionalLight ref={lights.rim} position={[...LIGHT_POS.rim]} intensity={2.4} color="#FF86BD" />
      <directionalLight ref={lights.rim2} position={[...LIGHT_POS.rim2]} intensity={1.3} color="#C9B4FF" />
    </>
  );
}
