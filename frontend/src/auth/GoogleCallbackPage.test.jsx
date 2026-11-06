import { render } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, expect, it, vi } from "vitest";

import { GoogleCallbackPage } from "./GoogleCallbackPage";

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.replaceState(null, "", "/");
});

it("clears the token fragment and posts exactly once to its own origin in StrictMode", () => {
  window.history.replaceState(
    null,
    "",
    "/auth/google/callback#id_token=signed-token&state=expected",
  );
  const opener = { postMessage: vi.fn() };
  vi.stubGlobal("opener", opener);
  render(
    <StrictMode>
      <GoogleCallbackPage />
    </StrictMode>,
  );
  expect(window.location.hash).toBe("");
  expect(opener.postMessage).toHaveBeenCalledOnce();
  expect(opener.postMessage).toHaveBeenCalledWith(
    {
      type: "pokearena.google.identity",
      credential: "signed-token",
      state: "expected",
      error: null,
    },
    window.location.origin,
  );
});
