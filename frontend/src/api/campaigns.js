/**
 * Campaign API client.
 *
 * All requests include credentials (the qb_session cookie) and expect JSON.
 * Non-OK responses throw an Error whose message comes from the backend's
 * `detail` field, making it safe to display directly in the UI.
 */

const BASE = "/api/campaigns";

/**
 * Shared fetch wrapper for campaign endpoints.
 *
 * @param {string} path - Absolute URL path (e.g. "/api/campaigns/123")
 * @param {RequestInit} options - Merged into the fetch options
 * @returns {Promise<any>} Parsed JSON body, or null for 204 No Content
 * @throws {Error} With the backend's detail message on non-OK responses
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

export const fetchCampaigns = () => request(BASE);

export const fetchCampaign = (id) => request(`${BASE}/${id}`);

export const createCampaign = (data) =>
  request(BASE, { method: "POST", body: JSON.stringify(data) });

export const updateCampaign = (id, data) =>
  request(`${BASE}/${id}`, { method: "PATCH", body: JSON.stringify(data) });

export const deleteCampaign = (id) =>
  request(`${BASE}/${id}`, { method: "DELETE" });

export const joinCampaign = (inviteCode) =>
  request(`${BASE}/join`, {
    method: "POST",
    body: JSON.stringify({ invite_code: inviteCode }),
  });

export const regenerateInviteCode = (id) =>
  request(`${BASE}/${id}/invite/regenerate`, { method: "POST" });

export const fetchMembers = (id) => request(`${BASE}/${id}/members`);

export const updateMember = (campaignId, userId, data) =>
  request(`${BASE}/${campaignId}/members/${userId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });

export const removeMember = (campaignId, userId) =>
  request(`${BASE}/${campaignId}/members/${userId}`, { method: "DELETE" });

export const leaveCampaign = (campaignId) =>
  request(`${BASE}/${campaignId}/members/me`, { method: "DELETE" });

export const fetchNextSession = (campaignId) =>
  request(`${BASE}/${campaignId}/next-session`);

export const fetchCampaignNotes = (campaignId) =>
  request(`${BASE}/${campaignId}/my-notes`);

// ── Milestones ─────────────────────────────────────────────────────────────────

export const fetchMilestones = (campaignId) =>
  request(`${BASE}/${campaignId}/milestones`);

export const createMilestone = (campaignId, data) =>
  request(`${BASE}/${campaignId}/milestones`, {
    method: "POST",
    body: JSON.stringify(data),
  });

export const updateMilestone = (campaignId, milestoneId, data) =>
  request(`${BASE}/${campaignId}/milestones/${milestoneId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });

export const deleteMilestone = (campaignId, milestoneId) =>
  request(`${BASE}/${campaignId}/milestones/${milestoneId}`, { method: "DELETE" });

export const fetchCampaignAnalytics = (campaignId) =>
  request(`${BASE}/${campaignId}/analytics`);
