/**
 * Fetch the currently authenticated user from /api/me.
 * Throws if the response is not OK (e.g. 401 when not logged in).
 */
export async function fetchMe() {
  const response = await fetch("/api/me", { credentials: "include" });
  if (!response.ok) throw new Error("Not authenticated");
  return response.json();
}
