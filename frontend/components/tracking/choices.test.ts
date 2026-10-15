import { describe, expect, it } from "vitest";
import { choiceLabels, isChosen, parseChoices, toggleChoice } from "./choices";

const options = [{ value: "dry", label: "Dry" }, { value: "red", label: "Red" }, { value: "blurry", label: "Blurry" }];

describe("single choice", () => {
  it("replaces the pick and clears it when tapped again", () => {
    expect(toggleChoice("", "dry", false)).toBe("dry");
    expect(toggleChoice("dry", "red", false)).toBe("red");
    expect(toggleChoice("dry", "dry", false)).toBe("");
  });

  it("can forbid clearing", () => {
    expect(toggleChoice("dry", "dry", false, false)).toBe("dry");
  });
});

describe("multiple choice", () => {
  it("adds and removes picks, keeping the order they were tapped", () => {
    let value = "";
    value = toggleChoice(value, "red", true);
    value = toggleChoice(value, "dry", true);
    expect(value).toBe("red,dry");
    value = toggleChoice(value, "red", true);
    expect(value).toBe("dry");
    expect(toggleChoice(value, "dry", true)).toBe("");
  });

  it("knows what is picked, whatever spacing the server used", () => {
    expect(isChosen("dry, red", "red", true)).toBe(true);
    expect(isChosen("dry,red", "blurry", true)).toBe(false);
    expect(isChosen("dry", "dry", false)).toBe(true);
  });

  it("parses empty and messy values without empty picks", () => {
    expect(parseChoices("")).toEqual([]);
    expect(parseChoices(" dry , ,red,")).toEqual(["dry", "red"]);
  });

  it("shows readable labels, and an unknown value as typed", () => {
    expect(choiceLabels("dry, red", options)).toBe("Dry, Red");
    expect(choiceLabels("dry,mystery", options)).toBe("Dry, mystery");
    expect(choiceLabels("", options)).toBe("");
  });
});
