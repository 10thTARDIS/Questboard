/**
 * User-related API calls (platform links, bot settings).
 *
 * All requests include credentials (the qb_session cookie) and expect JSON.
 * Non-OK responses throw an Error with the backend's `detail` message.
 */

async function request(path, options = {}) {
  const response = await fetch(path, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed: ${response.status}`);
  }
  if (response.status === 204) return null;
  return response.json();
}

// ── Platform links ─────────────────────────────────────────────────────────────

export const fetchPlatformLinks = () =>
  request("/api/me/platform-links");

export const addPlatformLink = (platform, platformUserId) =>
  request("/api/me/platform-links", {
    method: "POST",
    body: JSON.stringify({ platform, platform_user_id: platformUserId }),
  });

export const removePlatformLink = (platform) =>
  request(`/api/me/platform-links/${platform}`, { method: "DELETE" });

// ── Admin: bot settings ────────────────────────────────────────────────────────

export const fetchBotSettings = () =>
  request("/api/admin/settings/bot");

export const saveBotSettings = (data) =>
  request("/api/admin/settings/bot", {
    method: "PUT",
    body: JSON.stringify(data),
  });

export const regenerateBotApiKey = () =>
  request("/api/admin/settings/bot/regenerate-key", { method: "POST" });

export const pingBot = () =>
  request("/api/admin/settings/bot/ping");
