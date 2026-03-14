/**
 * Fetch the currently authenticated user from /api/me.
 * Throws if the response is not OK (e.g. 401 when not logged in).
 */
export async function fetchMe() {
  const response = await fetch("/api/me", { credentials: "include" });
  if (!response.ok) throw new Error("Not authenticated");
  return response.json();
}

/**
 * Update the current user's profile (display name override, timezone).
 */
export async function updateMe(data) {
  const response = await fetch("/api/me", {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? "Failed to update profile");
  }
  return response.json();
}

/**
 * Admin: list all users.
 */
export async function fetchAdminUsers() {
  const response = await fetch("/api/admin/users", { credentials: "include" });
  if (!response.ok) throw new Error("Not authorized");
  return response.json();
}

/**
 * Admin: grant or revoke admin status.
 */
export async function setAdminStatus(userId, isAdmin) {
  const response = await fetch(`/api/admin/users/${userId}/admin?is_admin=${isAdmin}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? "Failed to update admin status");
  }
  return response.json();
}
