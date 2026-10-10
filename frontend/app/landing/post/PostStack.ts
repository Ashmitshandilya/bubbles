import * as THREE from "three";
import { ShaderPass } from "three/examples/jsm/postprocessing/ShaderPass.js";
import { UnrealBloomPass } from "three/examples/jsm/postprocessing/UnrealBloomPass.js";
import { CopyShader } from "three/examples/jsm/shaders/CopyShader.js";
import { LAYER_OVERLAY, LAYER_SCENE } from "../world/layers";
import { GRADE_FRAG, GRADE_VERT } from "./grade.glsl";
import { POST, bloomStrength, gradeUniforms, newGradeUniforms, postTargetSize } from "./grade";
import type { Grade } from "../atmosphere/palette";

/**
 * The full tier's finish: scene to a multisampled half-float target, a bloom, then a grade that also tone maps
 * and writes to the canvas, and finally the soap bubbles on top.
 *
 *   1. scene (layer 0) into `sceneRT`, 4x multisampled, linear light, alpha 0 where nothing is drawn
 *   2. resolve copy into `plainRT`. The bloom adds its glow into the target it is given, and a multisampled
 *      target cannot be blended into after it has been resolved (three discards its colour samples then), so
 *      the bloom works on this plain copy.
 *   3. UnrealBloomPass on `plainRT` (premultiplied glow, so it is valid over the transparent canvas)
 *   4. the grade pass reads `plainRT` and draws to the canvas (post/grade.glsl.ts)
 *   5. the overlay layer (soap bubbles, whose shader writes display colours) is drawn on top, as it always was
 *
 * It writes only to render targets and to the canvas; the DOM is untouched, so copy never blooms. Anything that
 * goes wrong (an exception) is the caller's cue to fall back to the plain render.
 */
export class PostStack {
  private readonly sceneRT: THREE.WebGLRenderTarget;
  private readonly plainRT: THREE.WebGLRenderTarget;
  private readonly bloom: UnrealBloomPass;
  private readonly copy: ShaderPass;
  private readonly grade: ShaderPass;
  private readonly gradeValues = newGradeUniforms();
  private readonly size = new THREE.Vector2(2, 2);
  private cssW = 0;
  private cssH = 0;
  private dpr = 0;

  constructor(
    private readonly renderer: THREE.WebGLRenderer,
    private readonly scene: THREE.Scene,
    private readonly camera: THREE.Camera,
    cssW: number,
    cssH: number,
    dpr: number,
  ) {
    const target = postTargetSize(cssW, cssH, dpr);
    this.sceneRT = new THREE.WebGLRenderTarget(target.width, target.height, { type: THREE.HalfFloatType, samples: target.samples });
    this.sceneRT.texture.name = "Post.scene";
    this.plainRT = new THREE.WebGLRenderTarget(target.width, target.height, { type: THREE.HalfFloatType, depthBuffer: false });
    this.plainRT.texture.name = "Post.plain";

    this.bloom = new UnrealBloomPass(this.size.set(target.width, target.height), 0, POST.bloomRadius, POST.bloomThreshold);

    this.copy = new ShaderPass(CopyShader);
    this.copy.material.blending = THREE.NoBlending;

    const material = new THREE.ShaderMaterial({
      uniforms: {
        tDiffuse: { value: null },
        uWarm: { value: new THREE.Vector3(1, 1, 1) },
        uSat: { value: 1 },
        uCon: { value: 1 },
        uLift: { value: 0 },
        uVig: { value: 0 },
      },
      vertexShader: GRADE_VERT,
      fragmentShader: GRADE_FRAG,
      blending: THREE.NoBlending,
      depthTest: false,
      depthWrite: false,
    });
    this.grade = new ShaderPass(material);
    this.grade.renderToScreen = true;

    this.cssW = cssW;
    this.cssH = cssH;
    this.dpr = dpr;
  }

  /** Follow a canvas resize (or a device pixel ratio change). */
  resize(cssW: number, cssH: number, dpr: number) {
    if (cssW === this.cssW && cssH === this.cssH && dpr === this.dpr) return;
    this.cssW = cssW;
    this.cssH = cssH;
    this.dpr = dpr;
    const { width, height } = postTargetSize(cssW, cssH, dpr);
    this.sceneRT.setSize(width, height);
    this.plainRT.setSize(width, height);
    this.bloom.setSize(width, height);
  }

  /** Draw one frame. `amount` (0..1) fades the whole effect in and out. */
  render(dt: number, bloom: number, grade: Grade, amount: number) {
    const { renderer, scene, camera } = this;
    const priorTarget = renderer.getRenderTarget();
    const priorAutoClear = renderer.autoClear;
    const priorLayers = camera.layers.mask;
    const strength = bloomStrength(bloom, amount);
    try {
      // 1. the scene, without the overlay layer
      camera.layers.set(LAYER_SCENE);
      renderer.autoClear = true;
      renderer.setRenderTarget(this.sceneRT);
      renderer.render(scene, camera);

      // 2. resolved copy (the multisampled target resolves when it is sampled)
      this.copy.render(renderer, this.plainRT, this.sceneRT, dt, false);

      // 3. bloom, added into the copy
      if (strength > 0.004) {
        this.bloom.strength = strength;
        this.bloom.render(renderer, this.plainRT, this.plainRT, dt, false);
      }

      // 4. grade, tone map and encode to the canvas
      const u = gradeUniforms(grade, amount, this.gradeValues);
      const uniforms = this.grade.uniforms;
      (uniforms.uWarm.value as THREE.Vector3).set(u.warm[0], u.warm[1], u.warm[2]);
      uniforms.uSat.value = u.sat;
      uniforms.uCon.value = u.con;
      uniforms.uLift.value = u.lift;
      uniforms.uVig.value = u.vig;
      renderer.autoClear = true;
      this.grade.render(renderer, this.plainRT, this.plainRT, dt, false);

      // 5. the soap bubbles, straight onto the canvas (the depth the grade quad left behind is cleared first)
      camera.layers.set(LAYER_OVERLAY);
      renderer.autoClear = false;
      renderer.clearDepth();
      renderer.render(scene, camera);
    } finally {
      camera.layers.mask = priorLayers;
      renderer.autoClear = priorAutoClear;
      renderer.setRenderTarget(priorTarget);
    }
  }

  dispose() {
    this.sceneRT.dispose();
    this.plainRT.dispose();
    this.bloom.dispose();
    this.copy.dispose();
    this.grade.dispose();
  }
}
