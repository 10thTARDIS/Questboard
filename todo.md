Things that still need doing:

[x] When pasting an invite code, you should be able to hit enter and have it accept it.  Right now it's an extra click.
[x] Add ability to edit sessions (change time, reschedule, rename, or delete)
[x] Define timezone for campaign scheduling
[x] Set webhook for the campaign when creating it  (already existed; timezone + reminder offsets added alongside)
[x] Set reminder schedule on a per-campaign basis  (reminder_offsets_minutes JSONB on Campaign; editable in campaign settings)
[~] Allow for full notification setup within the webapp  (webhook per campaign done; email endpoints not yet implemented)
[x] There should be admin users who can control who is GMing a particular campaign -- first user auto-becomes admin; admins can elevate others via Admin panel
[~] Admins should be able to configure notification endpoints (webhooks and email accounts for phase one) within application settings  (webhook per campaign done; global/email endpoint config not yet built)
[x] Admins should be able to see basic user info (last logged in, campaigns joined, attendance at previous sessions, etc)  (Admin panel shows all users with last login and join date; per-campaign/session attendance stats not yet added)
[x] Users should be able to set a display name for themselves within the app  (Profile page: display name override)
[x] Users should be able to set their own timezone/locale  (Profile page: timezone selector)
[x] Users should be able to set a character's name associated with their own within the campaign so it's easy to remember who is playing who  (inline editor on member row in CampaignDetail)
[x] Users should have the ability to create session notes, and those session notes should be automatically joined together into per-user campaign notes. These notes should be private by default.  (per-session private notes done; aggregated campaign-level view not yet built)
[x] Add adjustable light/dark themes  (ThemeProvider + toggle button; dark is default)
[x] Add countdown to next session for each campaign (days until session until 24 hours before, then hours until session until one hours before, then minutes until session)

Still outstanding / partial:
[] Email notification endpoints (admin-configurable SMTP/email accounts)
[] Global notification endpoint configuration in app settings UI
[] Attendance tracking per session (who showed up)
[] Aggregated per-campaign notes view (combining all per-session notes for a user)
[] Admin: view which campaigns a user belongs to, session attendance history