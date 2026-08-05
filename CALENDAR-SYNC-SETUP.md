# Public-show calendar sync

The website reads `events.json` and displays the entries as custom event cards.

Google Calendar remains the source of truth. The GitHub Action in
`.github/workflows/sync-public-shows.yml` checks the dedicated public calendar
once per hour, updates `events.json`, and requests a GitHub Pages rebuild.

## One-time check after upload

1. Open the repository's **Actions** tab.
2. Open **Sync public shows**.
3. Choose **Run workflow**.
4. Confirm that the run completes successfully.

If the run says it cannot push `events.json`, open:

**Settings → Actions → General → Workflow permissions**

Choose **Read and write permissions**, save, then run the workflow again.

## Event-title format

Use:

`Project - Event name @ Venue`

Example:

`Jen & Cooper - Rusty and Primitive Treasures @ Hayworth Vineyard`

## Optional event image

Add one line to the Google Calendar event description:

`IMAGE: https://example.com/photo.jpg`

A locally uploaded website image also works:

`IMAGE: trio-current.webp`

Without an IMAGE line, the website automatically uses a matching project photo.

## Version 2.18 behavior

- Uploading this update triggers an immediate calendar sync automatically.
- The calendar is checked every 15 minutes afterward.
- You can still run **Actions → Sync public shows → Run workflow** for an immediate manual check.
- Google may occasionally take a few minutes to publish a brand-new public event.
