import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GoogleLoginCancelled, requestGoogleIdentity } from "./googleSignIn";

const challenge = { client_id: "client", nonce: "server-nonce", expires_in: 300 };

function popupWindow() {
  return { closed: false, close: vi.fn(), location: { href: "about:blank" } };
}

function reply(popup, data, origin = window.location.origin, source = popup) {
  window.dispatchEvent(new MessageEvent("message", { origin, source, data }));
}

describe("Google browser identity", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("requests an ID token with state and the server nonce, then accepts only the expected popup", async () => {
    const popup = popupWindow();
    const result = requestGoogleIdentity(challenge, popup);
    const url = new URL(popup.location.href);
    expect(url.origin).toBe("https://accounts.google.com");
    expect(url.searchParams.get("response_type")).toBe("id_token");
    expect(url.searchParams.get("nonce")).toBe("server-nonce");
    const data = {
      type: "pokearena.google.identity",
      state: url.searchParams.get("state"),
      credential: "signed-token",
    };
    reply(popup, data, "https://attacker.example");
    reply(popup, data, window.location.origin, window);
    reply(popup, { ...data, state: "different-state" });
    expect(popup.close).not.toHaveBeenCalled();
    reply(popup, data);
    await expect(result).resolves.toBe("signed-token");
    expect(popup.close).toHaveBeenCalledOnce();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("treats closing Google's popup as cancellation", async () => {
    const popup = popupWindow();
    const result = requestGoogleIdentity(challenge, popup);
    const rejection = expect(result).rejects.toBeInstanceOf(GoogleLoginCancelled);
    popup.closed = true;
    await vi.advanceTimersByTimeAsync(300);
    await rejection;
  });

  it("treats Google's access_denied response as cancellation", async () => {
    const popup = popupWindow();
    const result = requestGoogleIdentity(challenge, popup);
    reply(popup, {
      type: "pokearena.google.identity",
      state: new URL(popup.location.href).searchParams.get("state"),
      error: "access_denied",
    });
    await expect(result).rejects.toBeInstanceOf(GoogleLoginCancelled);
  });
});
