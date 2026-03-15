Things that still need doing:

# Version v0.1.0

## Completed Items

- [x] When pasting an invite code, you should be able to hit enter and have it accept it.  Right now it's an extra click.  
- [x] Add ability to edit sessions (change time, reschedule, rename, or delete)  
- [x] Define timezone for campaign scheduling  
- [x] Set webhook for the campaign when creating it  (already existed; timezone + reminder offsets added alongside)  
- [x] Set reminder schedule on a per-campaign basis  (reminder_offsets_minutes JSONB on Campaign; editable in campaign settings)  
- [~] Allow for full notification setup within the webapp  (webhook per campaign done; email + global settings done in Admin → Notification Settings)  
- [x] There should be admin users who can control who is GMing a particular campaign -- first user auto-becomes admin; admins can elevate others via Admin panel  
- [x] Admins should be able to configure notification endpoints (webhooks and email accounts for phase one) within application settings  (SMTP + global Discord webhook fallback configurable in Admin → Notification Settings)  
- [x] Admins should be able to see basic user info (last logged in, campaigns joined, attendance at previous sessions, etc)  (Admin panel: expandable user rows with campaign memberships + session attendance counts)  
- [x] Users should be able to set a display name for themselves within the app  (Profile page: display name override)  
- [x] Users should be able to set their own timezone/locale  (Profile page: timezone selector)  
- [x] Users should be able to set a character's name associated with their own within the campaign so it's easy to remember who is playing who  (inline editor on member row in CampaignDetail)  
- [x] Users should have the ability to create session notes, and those session notes should be automatically joined together into per-user campaign notes. These notes should be private by default.  (per-session private notes + Campaign Journal page at /campaigns/:id/notes)  
- [x] Add adjustable light/dark themes  (ThemeProvider + toggle button; dark is default)  
- [x] Add countdown to next session for each campaign (days until session until 24 hours before, then hours until session until one hour before, then minutes until session)  
- [x] Attendance tracking per session  (GM marks who attended on completed sessions in SessionDetail; PUT /api/sessions/{id}/attendance/{user_id} endpoint ready for v2 bot)  
- [x] Aggregated per-campaign notes view  (Campaign Journal page combining user's own notes + public GM notes, ordered by session date)  
- [x] GM public/private note visibility  (GMs can toggle notes public so they appear in all players' campaign journals)  
- [x] Admin: view which campaigns a user belongs to + session attendance history  (expandable user rows in Admin panel)  
- [x] Email notification endpoints  (admin-configurable SMTP in Admin → Notification Settings; "Send test email" button)  
- [x] Global notification endpoint configuration in app settings UI  (Discord webhook fallback + SMTP form in Admin → Notification Settings)  
- [x] Admin first-user bootstrap fix  (Alembic data migration promotes earliest registered user if no admins exist; `make set-admin EMAIL=...` CLI escape hatch)  
- [x] Reminder offsets UI  (up to 3 reminders, each with a value + unit selector of minutes/hours/days; stored as integer minutes in DB)  
- [x] Add Apple Calendar link to confirmed session calendar section (Apple Calendar uses the same .ics file; add a direct webcal:// link alongside the existing .ics download)
- [x] Add a time selector to the session scheduler with a proper time picker — minutes selectable in 15-minute increments (dropdown) and AM/PM selector  (DateTimePicker component replacing datetime-local in session create form and reschedule form)  
- [x] Add calendar event downloads for confirmed sessions  (.ics file download at GET /api/sessions/{id}/calendar.ics; Google Calendar link; both shown on SessionDetail for confirmed sessions)  
- [x] Session status auto-complete  (Celery Beat task every 5 minutes; transitions confirmed sessions to completed once confirmed_time passes)  
- [x] Vote notifications (per-campaign setting, GM-configurable):  
   - Mode A: notify when every eligible player has voted ("all votes in")  
   - Mode B: notify on each individual vote as it arrives  
   - Auto-close voting: after a GM-configured duration (vote_auto_close_hours), automatically close voting and confirm the highest-voted time slot  
- [x] Leave campaign: players can leave via "Leave Campaign" button on the campaign page; last GM is blocked with an error message


# Version v0.2.0

### Reaction-Based Voting via Bot
- [x] Users link their Discord (or Matrix) account ID in profile settings
  (`platform_links` table + Profile page "Connected Accounts" section; GET/POST/DELETE /api/me/platform-links)
- [x] Profile page UI to link/unlink Discord or Matrix account
- [ ] When a vote notification is posted, bot adds one reaction emoji per time slot  *(bot)*
- [ ] Bot watches for reactions from users with linked accounts and writes votes
  back to the existing Votes API  *(bot — PUT /api/bot/sessions/{id}/timeslots/{slot}/vote ready)*
- [ ] Users without linked accounts see a prompt when they react  *(bot)*

### Session Recording & Transcription
- [ ] Discord bot joins voice channel on session start (opt-in, consent required)  *(bot)*
- [ ] Audio sent to self-hosted OpenAI Whisper for transcription  *(bot)*
- [ ] Transcript passed to LLM (Ollama or API) for session summary  *(bot)*
- [x] Transcript and summary stored on Session record and displayed in SessionDetail
  (RecordingSection component; summary + collapsible transcript + recording link)
- [x] Admin: Whisper/LLM settings — model endpoint URL and API key stored in `app_settings`
  (Bot Settings tab in Admin panel)

### Campaign Milestone Tracking
- [x] Milestones for the campaign (level up, major location changes) on the campaign page, controllable by the GM
  (`milestones` table + Alembic migration; full GM create/edit/delete UI in CampaignDetail)
- [ ] Repeat-appearance NPCs surface in the milestones feed automatically  *(v3 dependency — NPC Tracker)*

### Bot Administration
- [x] Admin: bot token management — store Discord bot token in `app_settings`  (Bot Settings tab)
- [x] Admin: Whisper/LLM endpoint + API key configuration  (Bot Settings tab)
- [x] Bot API key — generate/regenerate shared secret; `require_bot_auth` dependency validates `X-Bot-Key` header
- [x] Bot API router — `/api/bot/` with 5 endpoints (upcoming sessions, linked users, vote, attendance, transcript)


# Version v0.3.0

### Campaign Wiki / Lore Pages
- [x] GM-editable structured lore entries (locations, factions, NPCs, items, events, other) attached to a campaign, optionally linked to sessions
  (`lore_entries` table + migration 930af97f5798; full GM CRUD in `/campaigns/:id/lore`; Wiki link in CampaignDetail)
- [ ] Bot transcripts and summaries (v2) can propose new lore entries or expansions; GM reviews and approves before they become canonical
  *(deferred — see docs/ENHANCEMENTS.md)*
- [ ] Lore entries versioned so GMs can revert bot-proposed changes
  *(deferred — see docs/ENHANCEMENTS.md)*

### NPC Tracker
- GM creates NPC cards with descriptions, tags, and session appearances
- Bot (v2) can auto-propose new NPCs or update existing ones from session transcripts; GM approves all changes
- Repeat-appearance NPCs surface automatically in the v2 Campaign Milestones feed

### Automated Post-Session Recap Email
- [x] After a session is completed and transcribed (v2), send an AI-generated summary email to attendees
  (`send_recap_email` Celery task; fired from `POST /api/bot/sessions/{id}/transcript`)
- [x] Opt-in per user (profile setting) AND per campaign (campaign setting); defaults to off for both
  (`recap_email_opt_in` on User; `recap_email_enabled` on Campaign; both settable in UI)

### Character Sheet Storage
- [x] Link to or embed character sheet data per campaign member
  (`character_sheet_url` + `character_sheet_notes` on `campaign_members`; editable inline in CampaignDetail)
- [ ] Investigate FoundryVTT API / compendium export for direct integration
  *(deferred — see docs/ENHANCEMENTS.md)*
- [x] Fallback: freeform URL + notes fields for users on other platforms

### Campaign Analytics Dashboard
- [x] Player attendance rates, session frequency, average session gap, vote participation rates per campaign
  (`GET /api/campaigns/{id}/analytics`; `/campaigns/:id/analytics` page; Analytics link in CampaignDetail)
- [x] GM-facing view; optionally shareable with players (accessible to all members)

### Matrix/Element Bot Parity
- Same bot features (reaction voting, session recording) via Matrix protocol in addition to Discord
