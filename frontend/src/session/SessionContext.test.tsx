import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it } from "vitest";

import { SessionProvider, useSession } from "./SessionContext";

const wrapper = ({ children }: { children: ReactNode }) => (
  <SessionProvider>{children}</SessionProvider>
);

describe("session", () => {
  beforeEach(() => sessionStorage.clear());

  it("starts without token", () => {
    const { result } = renderHook(() => useSession(), { wrapper });
    expect(result.current.hasToken).toBe(false);
    expect(result.current.getToken()).toBeNull();
  });

  it("keeps the token (trimmed) and clears it", () => {
    const { result } = renderHook(() => useSession(), { wrapper });
    act(() => result.current.setToken("  abc  "));
    expect(result.current.getToken()).toBe("abc");
    expect(result.current.hasToken).toBe(true);

    act(() => result.current.clearToken());
    expect(result.current.getToken()).toBeNull();
    expect(result.current.hasToken).toBe(false);
  });

  it("recovers the token after a reload of the page", () => {
    const first = renderHook(() => useSession(), { wrapper });
    act(() => first.result.current.setToken("abc"));
    first.unmount();

    const second = renderHook(() => useSession(), { wrapper });
    expect(second.result.current.getToken()).toBe("abc");
  });

  it("treats a blank token as no session", () => {
    const { result } = renderHook(() => useSession(), { wrapper });
    act(() => result.current.setToken("   "));
    expect(result.current.hasToken).toBe(false);
  });
});
