/**
 * True only in the Android app build (scripts/build-android.mjs sets NEXT_PUBLIC_BUBBLES_NATIVE=1).
 * Inlined at build time, so the website build never contains a native branch.
 */
export const isNativeApp = process.env.NEXT_PUBLIC_BUBBLES_NATIVE === "1";
