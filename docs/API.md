# Quest Board — API Reference

All API routes are served under the `/api` prefix (proxied by Nginx to the FastAPI backend on port 8000). Authentication routes live under `/auth`.

Authentication is via an `HttpOnly` session cookie (`qb_session`) set after a successful OIDC login. All `/api/*` endpoints require this cookie.

---

## Table of Contents

- [Authentication](#authentication)
- [Users](#users)
- [Campaigns](#campaigns)
- [Campaign Members](#campaign-members)
- [Sessions](#sessions)
- [Time Slots](#time-slots)
- [Votes](#votes)
- [Health](#health)
- [Error Responses](#error-responses)

---

## Authentication

### `GET /auth/login`

Initiates the OIDC PKCE authorization flow. Redirects the browser to the identity provider.

**Rate limit:** 10 requests/minute per IP.

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `invite_code` | string | No | Required for first-time registration if `INVITE_CODE` is set in config |

**Response:** `302 Redirect` to the provider's authorization endpoint.

---

### `GET /auth/callback`

Handles the redirect from the OIDC provider after successful authentication.

**Rate limit:** 10 requests/minute per IP.

**Query parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `code` | string | Authorization code from the provider |
| `state` | string | CSRF state token |

**Response:** `302 Redirect` to `/dashboard` with `qb_session` cookie set.

**Error responses:**
- `400` — Invalid or expired state parameter (CSRF protection)
- `403` — Invalid invite code (registration gate)
- `502` — Failed to communicate with OIDC provider

---

### `GET /auth/logout`

Deletes the server-side session and clears the cookie.

**Rate limit:** 10 requests/minute per IP.

**Response:** `302 Redirect` to `/login` with cookie deleted.

---

## Users

### `GET /api/me`

Returns the currently authenticated user's profile.

**Response `200`:**
```json
{
  "id": "uuid",
  "display_name": "string",
  "email": "string | null",
  "avatar_url": "string | null",
  "created_at": "datetime"
}
```

---

## Campaigns

### `GET /api/campaigns`

Lists all campaigns the authenticated user belongs to.

**Response `200`:** Array of campaign summaries including the calling user's role.
```json
[
  {
    "id": "uuid",
    "name": "string",
    "game_system": "string | null",
    "description": "string | null",
    "created_at": "datetime",
    "my_role": "gm | player"
  }
]
```

---

### `POST /api/campaigns`

Creates a new campaign. The creator is automatically assigned the GM role.

**Request body:**
```json
{
  "name": "string (required)",
  "game_system": "string | null",
  "description": "string | null",
  "discord_webhook_url": "string | null"
}
```

`discord_webhook_url` must start with `https://discord.com/api/webhooks/` or the request will be rejected with `422`.

**Response `201`:** Full `CampaignResponse` object (see below).

---

### `GET /api/campaigns/{campaign_id}`

Returns full details for a campaign. Requires campaign membership.

**Response `200`:**
```json
{
  "id": "uuid",
  "name": "string",
  "game_system": "string | null",
  "description": "string | null",
  "discord_webhook_url": "string | null",
  "invite_code": "string | null",
  "created_at": "datetime"
}
```

---

### `PATCH /api/campaigns/{campaign_id}`

Updates campaign fields. Requires GM role. Only supplied fields are changed (partial update).

**Request body:** Same fields as `POST /api/campaigns`, all optional.

**Response `200`:** Updated `CampaignResponse`.

---

### `DELETE /api/campaigns/{campaign_id}`

Deletes the campaign and all associated data. Requires GM role.

**Response `204 No Content`**

---

### `POST /api/campaigns/join`

Joins a campaign using its invite code. The joining user becomes a player.

**Request body:**
```json
{ "invite_code": "string" }
```

**Response `200`:** `CampaignResponse` for the joined campaign.

**Error responses:**
- `400` — Invalid invite code or user is already a member

---

### `POST /api/campaigns/{campaign_id}/invite/regenerate`

Generates a new invite code, invalidating the previous one. Requires GM role.

**Response `200`:** Updated `CampaignResponse`.

---

## Campaign Members

### `GET /api/campaigns/{campaign_id}/members`

Lists all members of a campaign. Requires campaign membership.

**Response `200`:**
```json
[
  {
    "user_id": "uuid",
    "display_name": "string",
    "email": "string | null",
    "avatar_url": "string | null",
    "role": "gm | player",
    "joined_at": "datetime"
  }
]
```

---

### `DELETE /api/campaigns/{campaign_id}/members/{user_id}`

Removes a member from the campaign. Requires GM role.

**Constraints:**
- A GM cannot remove themselves.
- The last GM cannot be removed (campaign must always have at least one GM).

**Response `204 No Content`**

**Error responses:**
- `400` — Attempted to remove self, or last GM

---

## Sessions

### `GET /api/campaigns/{campaign_id}/sessions`

Lists all sessions for a campaign. Requires campaign membership.

**Response `200`:** Array of `SessionListItem` objects:
```json
[
  {
    "id": "uuid",
    "campaign_id": "uuid",
    "title": "string | null",
    "scheduling_mode": "vote | direct | tentative",
    "status": "proposed | confirmed | completed | cancelled",
    "confirmed_time": "datetime | null",
    "created_at": "datetime"
  }
]
```

---

### `POST /api/campaigns/{campaign_id}/sessions`

Creates a new session. Requires GM role.

**Request body:**
```json
{
  "title": "string | null",
  "description": "string | null",
  "scheduling_mode": "vote | direct | tentative",
  "proposed_times": ["datetime"]
}
```

**`proposed_times` constraints:**
- `vote` mode: 2–5 datetime values
- `direct` or `tentative` mode: exactly 1 datetime value

For `direct` mode, the session is immediately `confirmed` and Discord notifications are scheduled.

**Response `201`:** Full `SessionResponse` object.

---

### `GET /api/sessions/{session_id}`

Returns full session details including time slots. Requires campaign membership.

**Response `200`:**
```json
{
  "id": "uuid",
  "campaign_id": "uuid",
  "title": "string | null",
  "description": "string | null",
  "scheduling_mode": "vote | direct | tentative",
  "status": "proposed | confirmed | completed | cancelled",
  "confirmed_time": "datetime | null",
  "session_notes": "string | null",
  "created_by": "uuid",
  "created_at": "datetime",
  "time_slots": [
    { "id": "uuid", "proposed_time": "datetime", "created_at": "datetime" }
  ]
}
```

---

### `PATCH /api/sessions/{session_id}`

Updates editable session fields. Requires GM role. Only `title`, `description`, and `session_notes` can be changed via PATCH.

**Request body:**
```json
{
  "title": "string | null",
  "description": "string | null",
  "session_notes": "string | null"
}
```

**Response `200`:** Updated `SessionResponse`.

---

### `DELETE /api/sessions/{session_id}`

Cancels a session (sets status to `cancelled`). Requires GM role. Pending reminder tasks are revoked.

**Response `204 No Content`**

**Error responses:**
- `400` — Session is already cancelled

---

### `POST /api/sessions/{session_id}/confirm`

Confirms a proposed session. Requires GM role. Schedules Discord reminder notifications.

**Request body:**
```json
{ "time_slot_id": "uuid | null" }
```

- **Vote mode:** `time_slot_id` is required (the winning slot).
- **Tentative mode:** omit `time_slot_id`; the single slot is used automatically.

**Response `200`:** Updated `SessionResponse` with `status=confirmed` and `confirmed_time` set.

**Error responses:**
- `400` — Session is not in `proposed` state, slot not found, or vote mode missing `time_slot_id`

---

## Time Slots

### `GET /api/sessions/{session_id}/timeslots`

Lists all time slots for a session. Requires campaign membership.

**Response `200`:** Array of `TimeSlotResponse` objects.

---

### `POST /api/sessions/{session_id}/timeslots`

Adds a time slot to a vote-mode session. Requires GM role. Maximum 5 slots per session.

**Request body:**
```json
{ "proposed_time": "datetime" }
```

**Response `201`:** `TimeSlotResponse` for the created slot.

**Error responses:**
- `400` — Session not in proposed state, not vote mode, or already at 5 slots

---

### `DELETE /api/sessions/{session_id}/timeslots/{slot_id}`

Removes a time slot. Requires GM role. Session must still be in `proposed` state.

**Response `204 No Content`**

---

## Votes

### `GET /api/sessions/{session_id}/votes`

Returns all votes cast across all time slots of the session. Requires campaign membership.

**Response `200`:**
```json
[
  {
    "id": "uuid",
    "time_slot_id": "uuid",
    "user_id": "uuid",
    "availability": "yes | maybe | no",
    "updated_at": "datetime"
  }
]
```

---

### `PUT /api/sessions/{session_id}/timeslots/{slot_id}/vote`

Creates or updates the authenticated user's vote for a time slot.

**Constraints:**
- Session must be `vote` mode and `proposed` status.
- One vote per user per slot; sending a second PUT replaces the previous vote.

**Request body:**
```json
{ "availability": "yes | maybe | no" }
```

**Response `200`:** `VoteResponse` for the created/updated vote.

---

### `DELETE /api/sessions/{session_id}/timeslots/{slot_id}/vote`

Removes the authenticated user's vote for a time slot. No-op if no vote exists.

**Response `204 No Content`**

---

## Health

### `GET /health`

Liveness probe. No authentication required.

**Response `200`:**
```json
{ "status": "ok" }
```

---

## Error Responses

All error responses follow the FastAPI default format:

```json
{ "detail": "Human-readable error message" }
```

Validation errors (422) include a `detail` array:

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "field_name"],
      "msg": "Error message",
      "input": "submitted_value"
    }
  ]
}
```

| HTTP Status | Meaning |
|-------------|---------|
| `400` | Bad request — business rule violation |
| `401` | Not authenticated — missing or expired session cookie |
| `403` | Forbidden — insufficient role (not a member / not GM) |
| `404` | Resource not found |
| `422` | Validation error — request body fails schema validation |
| `429` | Rate limit exceeded |
| `500` | Internal server error (details not exposed) |
| `502` | Bad gateway — upstream OIDC provider error |
