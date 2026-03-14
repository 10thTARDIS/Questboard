Things that still need doing:

# Version 1.0

## Completed Items

[x] When pasting an invite code, you should be able to hit enter and have it accept it.  Right now it's an extra click.
[x] Add ability to edit sessions (change time, reschedule, rename, or delete)
[x] Define timezone for campaign scheduling
[x] Set webhook for the campaign when creating it  (already existed; timezone + reminder offsets added alongside)
[x] Set reminder schedule on a per-campaign basis  (reminder_offsets_minutes JSONB on Campaign; editable in campaign settings)
[~] Allow for full notification setup within the webapp  (webhook per campaign done; email + global settings done in Admin → Notification Settings)
[x] There should be admin users who can control who is GMing a particular campaign -- first user auto-becomes admin; admins can elevate others via Admin panel
[x] Admins should be able to configure notification endpoints (webhooks and email accounts for phase one) within application settings  (SMTP + global Discord webhook fallback configurable in Admin → Notification Settings)
[x] Admins should be able to see basic user info (last logged in, campaigns joined, attendance at previous sessions, etc)  (Admin panel: expandable user rows with campaign memberships + session attendance counts)
[x] Users should be able to set a display name for themselves within the app  (Profile page: display name override)
[x] Users should be able to set their own timezone/locale  (Profile page: timezone selector)
[x] Users should be able to set a character's name associated with their own within the campaign so it's easy to remember who is playing who  (inline editor on member row in CampaignDetail)
[x] Users should have the ability to create session notes, and those session notes should be automatically joined together into per-user campaign notes. These notes should be private by default.  (per-session private notes + Campaign Journal page at /campaigns/:id/notes)
[x] Add adjustable light/dark themes  (ThemeProvider + toggle button; dark is default)
[x] Add countdown to next session for each campaign (days until session until 24 hours before, then hours until session until one hour before, then minutes until session)
[x] Attendance tracking per session  (GM marks who attended on completed sessions in SessionDetail; PUT /api/sessions/{id}/attendance/{user_id} endpoint ready for v2 bot)
[x] Aggregated per-campaign notes view  (Campaign Journal page combining user's own notes + public GM notes, ordered by session date)
[x] GM public/private note visibility  (GMs can toggle notes public so they appear in all players' campaign journals)
[x] Admin: view which campaigns a user belongs to + session attendance history  (expandable user rows in Admin panel)
[x] Email notification endpoints  (admin-configurable SMTP in Admin → Notification Settings; "Send test email" button)
[x] Global notification endpoint configuration in app settings UI  (Discord webhook fallback + SMTP form in Admin → Notification Settings)
[x] Admin first-user bootstrap fix  (Alembic data migration promotes earliest registered user if no admins exist; `make set-admin EMAIL=...` CLI escape hatch)
[x] Reminder offsets UI  (up to 3 reminders, each with a value + unit selector of minutes/hours/days; stored as integer minutes in DB)

## Still Outstanding

[] Add a time selector to the session scheduler with a proper time picker — minutes selectable in 15-minute increments (dropdown) and AM/PM selector — rather than the browser-native datetime-local input
[] Add calendar event downloads for confirmed sessions: .ics file download, Google Calendar link, Apple Calendar link

## New Items for v1

[] Session status auto-complete: Celery Beat task that automatically transitions a confirmed session to `completed` status once its `confirmed_time` passes (removes the need for the GM to manually mark sessions done)
[] Vote notifications (per-campaign setting, GM-configurable):
   - Mode A: notify when every eligible player has voted ("all votes in")
   - Mode B: notify on each individual vote as it arrives
   - Auto-close voting: after a GM-configured duration, automatically close voting and confirm the highest-voted time slot
[] Leave campaign: allow players to leave a campaign themselves rather than requiring the GM to remove them


# Version 2.0

### Reaction-Based Voting via Bot
- Users link their Discord (or Matrix) account ID in profile settings
  (stored as `platform_links` table: user_id, platform ENUM, platform_user_id — table already created in v1 schema)
- Profile page UI to link/unlink Discord or Matrix account
- When a vote notification is posted, bot adds one reaction emoji per time slot
- Bot watches for reactions from users with linked accounts and writes votes
  back to the existing Votes API
- Users without linked accounts see a prompt when they react

### Session Recording & Transcription
- Discord bot joins voice channel on session start (opt-in, consent required)
- Audio sent to self-hosted OpenAI Whisper for transcription
- Transcript passed to LLM (Ollama or API) for session summary
- Transcript and summary stored on Session record (columns already exist in v1 schema), displayed in session detail page
- Admin: Whisper/LLM settings — model endpoint URL and API key stored in `app_settings`

### Campaign Milestone Tracking
- Milestones for the campaign (level up, major location changes) on the campaign page, controllable by the GM
- Repeat-appearance NPCs (from v2 NPC Tracker) surface in the milestones feed automatically

### Bot Administration
- Admin: bot token management — store Discord bot token in `app_settings`
- Admin: Whisper/LLM endpoint + API key configuration


# Version 3.0

### Campaign Wiki / Lore Pages
- GM-editable structured lore entries (locations, factions, NPCs) attached to a campaign, optionally linked to sessions
- Bot transcripts and summaries (v2) can propose new lore entries or expansions; GM reviews and approves before they become canonical
- Lore entries versioned so GMs can revert bot-proposed changes

### NPC Tracker
- GM creates NPC cards with descriptions, tags, and session appearances
- Bot (v2) can auto-propose new NPCs or update existing ones from session transcripts; GM approves all changes
- Repeat-appearance NPCs surface automatically in the v2 Campaign Milestones feed

### Automated Post-Session Recap Email
- After a session is completed and transcribed (v2), send an AI-generated summary email to attendees
- Opt-in per user (profile setting) AND per campaign (campaign setting); defaults to off for both

### Character Sheet Storage
- Link to or embed character sheet data per campaign member
- Investigate FoundryVTT API / compendium export for direct integration so character sheets can be pulled from an active Foundry world
- Fallback: freeform URL or key/value fields for users on other platforms

### Campaign Analytics Dashboard
- Player attendance rates, session frequency, average session gap, vote participation rates per campaign
- GM-facing view; optionally shareable with players

### Matrix/Element Bot Parity
- Same bot features (reaction voting, session recording) via Matrix protocol in addition to Discord
