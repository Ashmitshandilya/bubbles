/**
 * three.js layers used by the landing scene. Everything is on LAYER_SCENE except the soap bubbles, whose
 * shader writes display (sRGB) colours straight to the canvas; in the full tier the post stack draws them
 * on top of the graded scene instead of running them through bloom, tone mapping and grading
 * (post/PostStack.ts). The camera sees both layers, so the other tiers render exactly as before.
 */
export const LAYER_SCENE = 0;
export const LAYER_OVERLAY = 1;
