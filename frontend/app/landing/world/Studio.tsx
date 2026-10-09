"use client";

import { useEffect } from "react";
import { useThree } from "@react-three/fiber";
import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";

/** Procedural studio reflections (no HDR download) plus Bubbles' three-light setup. */
export function Studio({ envIntensity = 0.75, rim = 2.4 }: { envIntensity?: number; rim?: number }) {
  const gl = useThree((state) => state.gl);
  const scene = useThree((state) => state.scene);

  useEffect(() => {
    const pmrem = new THREE.PMREMGenerator(gl);
    const room = new RoomEnvironment();
    const env = pmrem.fromScene(room, 0.04).texture;
    scene.environment = env;
    scene.environmentIntensity = envIntensity;
    return () => {
      scene.environment = null;
      env.dispose();
      pmrem.dispose();
      room.traverse((object) => {
        const mesh = object as THREE.Mesh;
        mesh.geometry?.dispose?.();
        const material = mesh.material as THREE.Material | THREE.Material[] | undefined;
        if (Array.isArray(material)) material.forEach((mat) => mat.dispose());
        else material?.dispose?.();
      });
    };
  }, [gl, scene, envIntensity]);

  return (
    <>
      <hemisphereLight args={["#FFF4FA", "#4A2348", 0.85]} />
      {/* warm key from the upper right */}
      <directionalLight position={[3.5, 5, 4.5]} intensity={2.1} color="#FFF6F2" />
      {/* lavender fill from the left */}
      <directionalLight position={[-4, 1.5, 3]} intensity={0.55} color="#D8CCFF" />
      {/* pink rim from behind: keeps the white silhouette readable on dark scenes */}
      <directionalLight position={[-3, 3.5, -4.5]} intensity={rim} color="#FF86BD" />
      <directionalLight position={[3.5, 1, -4]} intensity={rim * 0.55} color="#C9B4FF" />
    </>
  );
}
