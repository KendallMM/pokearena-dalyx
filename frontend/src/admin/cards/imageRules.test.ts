import { describe, expect, it } from "vitest";

import { pngFile } from "../../test/fixtures";
import { checkImageFile, checkImageSize, inspectCardImage } from "./imageRules";

describe("checkImageFile", () => {
  it.each(["image/png", "image/jpeg", "image/webp"])("accepts %s", (type) => {
    expect(checkImageFile(pngFile("a", type))).toBeNull();
  });

  it.each(["image/gif", "application/pdf", ""])("rejects format %j", (type) => {
    expect(checkImageFile(pngFile("a", type))).toMatch(/PNG, JPG o WebP/);
  });

  it("rejects more than 5 MB and accepts exactly 5 MB", () => {
    expect(checkImageFile(pngFile("a", "image/png", 5 * 1024 * 1024))).toBeNull();
    expect(checkImageFile(pngFile("a", "image/png", 5 * 1024 * 1024 + 1))).toMatch(
      /5 MB/,
    );
  });
});

describe("checkImageSize", () => {
  it("accepts the exact 5:7 ratio at the minimum and above", () => {
    expect(checkImageSize({ width: 600, height: 840 })).toBeNull();
    expect(checkImageSize({ width: 1000, height: 1400 })).toBeNull();
  });

  it("rejects another ratio, naming the real size", () => {
    expect(checkImageSize({ width: 840, height: 600 })).toMatch(/5:7.*840 × 600/);
    expect(checkImageSize({ width: 601, height: 840 })).toMatch(/5:7/);
  });

  it("rejects a resolution below the minimum", () => {
    expect(checkImageSize({ width: 500, height: 700 })).toMatch(/600 × 840/);
  });
});

describe("inspectCardImage", () => {
  it("does not read the size of a file with a bad format", async () => {
    let read = false;
    const problem = await inspectCardImage(pngFile("a", "image/gif"), async () => {
      read = true;
      return { width: 600, height: 840 };
    });
    expect(problem).toMatch(/PNG, JPG o WebP/);
    expect(read).toBe(false);
  });

  it("returns null for a valid image", async () => {
    const problem = await inspectCardImage(pngFile(), async () => ({
      width: 600,
      height: 840,
    }));
    expect(problem).toBeNull();
  });

  it("reports a file that cannot be decoded", async () => {
    const problem = await inspectCardImage(pngFile(), async () => {
      throw new Error("corrupta");
    });
    expect(problem).toMatch(/No se pudo leer/);
  });
});
