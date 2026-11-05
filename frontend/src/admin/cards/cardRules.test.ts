import { describe, expect, it } from "vitest";

import { pngFile } from "../../test/fixtures";
import {
  EMPTY_CARD_FORM,
  formFieldFromApi,
  parseInteger,
  toCreateCardInput,
  validateCardValues,
  type CardFormValues,
} from "./cardRules";

const VALID: CardFormValues = {
  name: "Charmander",
  cost: "3",
  power: "5",
  cardType: "FUE",
  rarity: "COMMON",
  ability: "HAB-000",
  image: pngFile(),
};

describe("parseInteger", () => {
  it.each([
    ["5", 5],
    ["-3", -3],
    [" 7 ", 7],
    ["0", 0],
  ])("reads %s", (text, expected) => {
    expect(parseInteger(text)).toBe(expected);
  });

  it.each(["", "abc", "1.5", "1e3", "--2", "+3"])("rejects %j", (text) => {
    expect(parseInteger(text)).toBeNull();
  });
});

describe("validateCardValues", () => {
  it("accepts valid values", () => {
    expect(validateCardValues(VALID)).toEqual({});
  });

  it("accepts the bounds of cost and power", () => {
    for (const [cost, power] of [
      ["0", "-20"],
      ["10", "20"],
    ]) {
      expect(validateCardValues({ ...VALID, cost: cost!, power: power! })).toEqual({});
    }
  });

  it("asks for every required field", () => {
    const errors = validateCardValues(EMPTY_CARD_FORM);
    expect(Object.keys(errors).sort()).toEqual(
      ["ability", "cardType", "cost", "image", "name", "power", "rarity"].sort(),
    );
    expect(errors.ability).toMatch(/Sin Habilidad/);
  });

  it.each([
    [{ cost: "11" }, "cost", /entre 0 y 10/],
    [{ cost: "-1" }, "cost", /entre 0 y 10/],
    [{ cost: "2.5" }, "cost", /entero/],
    [{ power: "21" }, "power", /entre -20 y 20/],
    [{ power: "-21" }, "power", /entre -20 y 20/],
    [{ power: "x" }, "power", /entero/],
    [{ name: "   " }, "name", /obligatorio/],
    [{ name: "x".repeat(101) }, "name", /100 caracteres/],
  ])("rejects %j", (change, field, message) => {
    const errors = validateCardValues({ ...VALID, ...change });
    expect(errors[field as keyof typeof errors]).toMatch(message);
  });
});

describe("toCreateCardInput", () => {
  it("converts the text fields to what the API expects", () => {
    const input = toCreateCardInput({
      ...VALID,
      name: "  Charmander ",
      cost: " 3 ",
      power: "-5",
    });
    expect(input).toMatchObject({
      name: "Charmander",
      cost: 3,
      power: -5,
      cardType: "FUE",
    });
  });

  it("refuses to build a request without image", () => {
    expect(() => toCreateCardInput({ ...VALID, image: null })).toThrow();
  });
});

describe("formFieldFromApi", () => {
  it("maps API field names to form fields", () => {
    expect(formFieldFromApi("card_type")).toBe("cardType");
    expect(formFieldFromApi("image")).toBe("image");
    expect(formFieldFromApi("Idempotency-Key")).toBeNull();
    expect(formFieldFromApi(null)).toBeNull();
  });
});
