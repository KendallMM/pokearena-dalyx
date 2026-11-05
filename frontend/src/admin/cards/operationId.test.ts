import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { newOperationId, useOperationKey } from "./operationId";

describe("newOperationId", () => {
  it("creates different identifiers", () => {
    expect(newOperationId()).not.toBe(newOperationId());
  });
});

describe("useOperationKey", () => {
  it("keeps the same key until it is reset", () => {
    const { result } = renderHook(() => useOperationKey());
    const first = result.current.current();
    expect(result.current.current()).toBe(first);

    result.current.reset();
    expect(result.current.current()).not.toBe(first);
  });
});
