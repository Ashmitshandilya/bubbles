"use client";

import { useEffect } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { Orb } from "../bubbles/Orb";
import { SoapBubbles } from "../bubbles/SoapBubbles";
import { story } from "../story/store";

/**
 * The 3D scene: the orb (the giant soap bubble that carries the story) and the field of small bubbles. Both are
 * parented to the camera and placed in screen pixels over boxes in the page, so the camera itself stays still;
 * the scroll director and the copy do the choreography. The first frame marks the page `data-world="ready"`.
 */
export function World() {
  const camera = useThree((s) => s.camera);

  useEffect(() => {
    camera.position.set(0, 0, 10);
    camera.lookAt(0, 0, 0);
    camera.updateMatrixWorld();
    return () => {
      story.worldReady = false;
      const root = document.querySelector<HTMLElement>(".cw");
      if (root) root.dataset.world = "off";
    };
  }, [camera]);

  useFrame(() => {
    if (story.worldReady) return;
    story.worldReady = true;
    const root = document.querySelector<HTMLElement>(".cw");
    if (root) root.dataset.world = "ready";
  });

  return (
    <>
      <Orb />
      <SoapBubbles />
    </>
  );
}
