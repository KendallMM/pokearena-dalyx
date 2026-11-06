import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SessionProvider, useSession } from "./SessionContext";

const wrapper = ({ children }: { children: ReactNode }) => (
  <SessionProvider>{children}</SessionProvider>
);

describe("session", () => {
  beforeEach(() => sessionStorage.clear());
  afterEach(() => vi.useRealTimers());

  it("expires the internal credential and clears the session automatically", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useSession(), { wrapper });
    act(() =>
      result.current.setToken("internal", new Date(Date.now() + 1000).toISOString()),
    );
    expect(result.current.getToken()).toBe("internal");
    act(() => vi.advanceTimersByTime(1001));
    expect(result.current.hasToken).toBe(false);
    expect(result.current.getToken()).toBeNull();
  });

  it("rejects an already expired credential", () => {
    const { result } = renderHook(() => useSession(), { wrapper });
    act(() =>
      result.current.setToken("expired", new Date(Date.now() - 1000).toISOString()),
    );
    expect(result.current.hasToken).toBe(false);
  });

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

  it("does not persist bearer credentials across a reload", () => {
    const first = renderHook(() => useSession(), { wrapper });
    act(() => first.result.current.setToken("abc"));
    first.unmount();

    const second = renderHook(() => useSession(), { wrapper });
    expect(second.result.current.getToken()).toBeNull();
    expect(sessionStorage.getItem("pokearena.session.token")).toBeNull();
  });

  it("treats a blank token as no session", () => {
    const { result } = renderHook(() => useSession(), { wrapper });
    act(() => result.current.setToken("   "));
    expect(result.current.hasToken).toBe(false);
  });
});
