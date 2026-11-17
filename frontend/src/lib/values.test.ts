import { describe, expect, it } from "vitest";
import { parsePriority, splitCommaList } from "./values.ts";

describe("parsePriority", () => {
  it("turns a numeric string into a number", () => {
    expect(parsePriority(" 4 ")).toBe(4);
  });

  it("keeps a priority alias as a string", () => {
    expect(parsePriority("urgent")).toBe("urgent");
  });

  it("treats a blank value as absent", () => {
    expect(parsePriority("   ")).toBeUndefined();
  });
});

describe("splitCommaList", () => {
  it("trims and drops empty entries", () => {
    expect(splitCommaList(" warning, backup ,, ")).toEqual(["warning", "backup"]);
  });

  it("returns no entries for a blank value", () => {
    expect(splitCommaList("  ")).toEqual([]);
  });
});
