import * as React from "react";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

// vitest compiles JSX with the classic runtime (tsconfig has jsx: "preserve"), so components expect `React` in scope.
(globalThis as { React?: typeof React }).React = React;

const PUBLISHED = {
  published: true,
  appName: "Bubbles",
  applicationId: "in.heybubbles.app",
  versionName: "1.2.0",
  versionCode: 3,
  releaseDate: "2026-10-11",
  minSdk: 24,
  minAndroid: "7.0",
  targetSdk: 36,
  file: "/android/bubbles.apk",
  sizeBytes: 5242880,
  sha256: "ab".repeat(32),
  signingCertSha256: Array(32).fill("CD").join(":"),
};

async function render(release: object, native = false) {
  vi.resetModules();
  vi.doMock("../../public/android/latest.json", () => ({ default: release }));
  vi.doMock("../../lib/native", () => ({ isNativeApp: native }));
  const { default: AndroidPage } = await import("./page");
  return renderToStaticMarkup(createElement(AndroidPage));
}

afterEach(() => {
  vi.doUnmock("../../public/android/latest.json");
  vi.doUnmock("../../lib/native");
});

describe("/android", () => {
  it("offers no download until a release is published", async () => {
    const html = await render({ ...PUBLISHED, published: false, versionName: "", releaseDate: "", sizeBytes: 0, sha256: "", signingCertSha256: "" });
    expect(html).toContain("isn&#x27;t published yet");
    expect(html).not.toContain("bubbles.apk");
    expect(html).not.toContain("download=");
  });

  it("describes the published file from the manifest", async () => {
    const html = await render(PUBLISHED);
    expect(html).toMatch(/<a href="\/android\/bubbles\.apk" download=""/);
    expect(html).toContain("1.2.0");
    expect(html).toContain("11 October 2026");
    expect(html).toContain("5.0 MB");
    expect(html).toContain("Android 7.0 or newer");
    expect(html).toContain(PUBLISHED.sha256);
    expect(html).toContain(PUBLISHED.signingCertSha256);
  });

  it("never offers the download inside the app", async () => {
    const html = await render(PUBLISHED, true);
    expect(html).toContain("already using the app");
    expect(html).not.toContain("download=");
  });
});
