/**
 * Session, time-slot, and vote API client.
 *
 * All requests include credentials (the qb_session cookie) and expect JSON.
 * Non-OK responses throw an Error with the backend's `detail` message.
 */

/**
 * Shared fetch wrapper for session/timeslot/vote endpoints.
 *
 * @param {string} path - Absolute URL path
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

// ── Sessions ──────────────────────────────────────────────────────────────────

export const fetchSessions = (campaignId) =>
  request(`/api/campaigns/${campaignId}/sessions`);

export const fetchSession = (sessionId) =>
  request(`/api/sessions/${sessionId}`);

export const createSession = (campaignId, data) =>
  request(`/api/campaigns/${campaignId}/sessions`, {
    method: "POST",
    body: JSON.stringify(data),
  });

export const updateSession = (sessionId, data) =>
  request(`/api/sessions/${sessionId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });

export const cancelSession = (sessionId) =>
  request(`/api/sessions/${sessionId}`, { method: "DELETE" });

export const confirmSession = (sessionId, timeSlotId = null) =>
  request(`/api/sessions/${sessionId}/confirm`, {
    method: "POST",
    body: JSON.stringify({ time_slot_id: timeSlotId }),
  });

// ── Time slots ────────────────────────────────────────────────────────────────

export const addTimeslot = (sessionId, proposedTime) =>
  request(`/api/sessions/${sessionId}/timeslots`, {
    method: "POST",
    body: JSON.stringify({ proposed_time: proposedTime }),
  });

export const removeTimeslot = (sessionId, slotId) =>
  request(`/api/sessions/${sessionId}/timeslots/${slotId}`, { method: "DELETE" });

// ── Votes ──────────────────────────────────────────────────────────────────────

export const fetchVotes = (sessionId) =>
  request(`/api/sessions/${sessionId}/votes`);

export const submitVote = (sessionId, slotId, availability) =>
  request(`/api/sessions/${sessionId}/timeslots/${slotId}/vote`, {
    method: "PUT",
    body: JSON.stringify({ availability }),
  });

export const deleteVote = (sessionId, slotId) =>
  request(`/api/sessions/${sessionId}/timeslots/${slotId}/vote`, { method: "DELETE" });

// ── Session notes ──────────────────────────────────────────────────────────────

export const fetchMyNotes = (sessionId) =>
  request(`/api/sessions/${sessionId}/my-notes`);

export const upsertMyNote = (sessionId, content, visibility = "private") =>
  request(`/api/sessions/${sessionId}/my-note`, {
    method: "PUT",
    body: JSON.stringify({ content, visibility }),
  });

// ── Attendance ──────────────────────────────────────────────────────────────────

export const fetchAttendance = (sessionId) =>
  request(`/api/sessions/${sessionId}/attendance`);

export const setAttendance = (sessionId, userId, attended) =>
  request(`/api/sessions/${sessionId}/attendance/${userId}`, {
    method: "PUT",
    body: JSON.stringify({ attended }),
  });

// ── Admin ───────────────────────────────────────────────────────────────────────

export const fetchAdminUserDetail = (userId) =>
  request(`/api/admin/users/${userId}/details`);

export const fetchNotificationSettings = () =>
  request("/api/admin/settings/notifications");

export const saveNotificationSettings = (data) =>
  request("/api/admin/settings/notifications", {
    method: "PUT",
    body: JSON.stringify(data),
  });

export const sendTestEmail = () =>
  request("/api/admin/settings/notifications/test-email", { method: "POST" });
