import { describe, expect, it } from "vitest";
import { organFromSearch } from "./organParam";

describe("organFromSearch", () => {
  it("reads a plain organ id", () => {
    expect(organFromSearch("?organ=brain")).toBe("brain");
    expect(organFromSearch("?x=1&organ=uterus_ovaries")).toBe("uterus_ovaries");
  });
  it("ignores anything else", () => {
    expect(organFromSearch("")).toBeNull();
    expect(organFromSearch("?organ=")).toBeNull();
    expect(organFromSearch("?organ=../x")).toBeNull();
    expect(organFromSearch("?organ=<script>")).toBeNull();
    expect(organFromSearch("?organ=Brain")).toBeNull();
  });
});
