/**
 * Dashboard — the main landing page for authenticated users.
 *
 * Shows all campaigns the user belongs to, with role badges (GM / Player).
 * Provides inline forms to create a new campaign or join one via invite code.
 * Newly created/joined campaigns are prepended to the list optimistically
 * so the page doesn't need to re-fetch from the server.
 */

import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth.jsx";
import NavBar from "../components/NavBar.jsx";
import {
  createCampaign,
  fetchCampaigns,
  fetchNextSession,
  joinCampaign,
} from "../api/campaigns.js";

/**
 * Format a countdown from now to a future date.
 * Returns a string like "3d 4h", "6h 30m", "45m", "< 1m".
 */
function formatCountdown(isoDate) {
  const diff = new Date(isoDate) - Date.now();
  if (diff <= 0) return null;
  const totalMinutes = Math.floor(diff / 60000);
  const days = Math.floor(totalMinutes / 1440);
  const hours = Math.floor((totalMinutes % 1440) / 60);
  const minutes = totalMinutes % 60;
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m`;
  return "< 1m";
}

function SessionCountdown({ campaignId }) {
  const [next, setNext] = useState(undefined); // undefined = loading, null = none
  const [, setTick] = useState(0);
  const timerRef = useRef(null);

  useEffect(() => {
    fetchNextSession(campaignId)
      .then(setNext)
      .catch(() => setNext(null));
  }, [campaignId]);

  useEffect(() => {
    if (!next?.confirmed_time) return;
    timerRef.current = setInterval(() => setTick((t) => t + 1), 60000);
    return () => clearInterval(timerRef.current);
  }, [next]);

  if (next === undefined) return null;
  if (!next) return null;

  const countdown = formatCountdown(next.confirmed_time);
  if (!countdown) return null;

  return (
    <p className="text-xs text-indigo-400 mt-0.5">
      Next session in {countdown}
    </p>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Create-campaign form state
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({
    name: "",
    game_system: "",
    description: "",
  });
  const [createError, setCreateError] = useState(null);
  const [creating, setCreating] = useState(false);

  // Join-campaign form state
  const [showJoin, setShowJoin] = useState(false);
  const [inviteCode, setInviteCode] = useState("");
  const [joinError, setJoinError] = useState(null);
  const [joining, setJoining] = useState(false);

  useEffect(() => {
    fetchCampaigns()
      .then(setCampaigns)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    setCreating(true);
    setCreateError(null);
    try {
      const campaign = await createCampaign({
        name: createForm.name,
        game_system: createForm.game_system || null,
        description: createForm.description || null,
      });
      setCampaigns((prev) => [
        { ...campaign, my_role: "gm" },
        ...prev,
      ]);
      setShowCreate(false);
      setCreateForm({ name: "", game_system: "", description: "" });
    } catch (e) {
      setCreateError(e.message);
    } finally {
      setCreating(false);
    }
  };

  const handleJoin = async (e) => {
    e.preventDefault();
    setJoining(true);
    setJoinError(null);
    try {
      const campaign = await joinCampaign(inviteCode.trim());
      setCampaigns((prev) => [
        { ...campaign, my_role: "player" },
        ...prev,
      ]);
      setShowJoin(false);
      setInviteCode("");
    } catch (e) {
      setJoinError(e.message);
    } finally {
      setJoining(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <header className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <h1 className="text-xl font-bold">Quest Board</h1>
        <NavBar />
      </header>

      <main className="mx-auto max-w-3xl px-6 py-8">
        {/* Page title + actions */}
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Your Campaigns</h2>
          <div className="flex gap-2">
            <button
              onClick={() => { setShowJoin(true); setShowCreate(false); }}
              className="rounded-lg border border-gray-700 px-3 py-1.5 text-sm hover:border-gray-500 transition"
            >
              Join
            </button>
            <button
              onClick={() => { setShowCreate(true); setShowJoin(false); }}
              className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium hover:bg-indigo-500 transition"
            >
              New Campaign
            </button>
          </div>
        </div>

        {/* Create form */}
        {showCreate && (
          <form
            onSubmit={handleCreate}
            className="mb-6 rounded-xl border border-gray-800 bg-gray-900 p-5 space-y-3"
          >
            <h3 className="font-medium">New Campaign</h3>
            <input
              required
              placeholder="Campaign name"
              value={createForm.name}
              onChange={(e) => setCreateForm((f) => ({ ...f, name: e.target.value }))}
              className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <input
              placeholder="Game system (e.g. Pathfinder 2e)"
              value={createForm.game_system}
              onChange={(e) => setCreateForm((f) => ({ ...f, game_system: e.target.value }))}
              className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <textarea
              placeholder="Description (optional)"
              rows={2}
              value={createForm.description}
              onChange={(e) => setCreateForm((f) => ({ ...f, description: e.target.value }))}
              className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
            />
            {createError && <p className="text-sm text-red-400">{createError}</p>}
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => setShowCreate(false)}
                className="rounded-lg border border-gray-700 px-3 py-1.5 text-sm hover:border-gray-500 transition"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={creating}
                className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium hover:bg-indigo-500 disabled:opacity-50 transition"
              >
                {creating ? "Creating…" : "Create"}
              </button>
            </div>
          </form>
        )}

        {/* Join form */}
        {showJoin && (
          <form
            onSubmit={handleJoin}
            className="mb-6 rounded-xl border border-gray-800 bg-gray-900 p-5 space-y-3"
          >
            <h3 className="font-medium">Join a Campaign</h3>
            <input
              required
              placeholder="Invite code"
              value={inviteCode}
              onChange={(e) => setInviteCode(e.target.value)}
              className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            {joinError && <p className="text-sm text-red-400">{joinError}</p>}
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => setShowJoin(false)}
                className="rounded-lg border border-gray-700 px-3 py-1.5 text-sm hover:border-gray-500 transition"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={joining}
                className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium hover:bg-indigo-500 disabled:opacity-50 transition"
              >
                {joining ? "Joining…" : "Join"}
              </button>
            </div>
          </form>
        )}

        {/* Campaign list */}
        {loading && <p className="text-gray-500 text-sm">Loading campaigns…</p>}
        {error && <p className="text-red-400 text-sm">{error}</p>}
        {!loading && campaigns.length === 0 && (
          <p className="text-gray-500 text-sm">
            No campaigns yet. Create one or join with an invite code.
          </p>
        )}
        <ul className="space-y-3">
          {campaigns.map((c) => (
            <li key={c.id}>
              <Link
                to={`/campaigns/${c.id}`}
                className="flex items-center justify-between rounded-xl border border-gray-800 bg-gray-900 px-5 py-4 hover:border-gray-700 transition"
              >
                <div>
                  <p className="font-medium">{c.name}</p>
                  {c.game_system && (
                    <p className="text-sm text-gray-400">{c.game_system}</p>
                  )}
                  <SessionCountdown campaignId={c.id} />
                </div>
                <span
                  className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                    c.my_role === "gm"
                      ? "bg-amber-900/50 text-amber-300"
                      : "bg-gray-800 text-gray-400"
                  }`}
                >
                  {c.my_role === "gm" ? "GM" : "Player"}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </main>
    </div>
  );
}
