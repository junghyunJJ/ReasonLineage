# Dashboard Live Log Redesign Design

**Date:** 2026-03-28

**Problem**

The dashboard places the live event log below other result panels, renders each event as a large JSON card, and orders entries newest-first. This makes the run console hard to scan and prevents users from seeing comparison results and the event stream together without additional page scrolling.

**Goals**

- Keep core benchmark results, lineage, and live log visible together on desktop.
- Replace the oversized event cards with a dense table that is easier to scan.
- Show live events oldest-first so the stream reads naturally top-to-bottom.
- Preserve the existing run lifecycle, SSE updates, and review controls.

**Non-goals**

- Reworking the backend event model.
- Replacing the existing desktop/mobile visual language.
- Adding advanced log filtering or search.

**Approved Approach**

1. Compress the top section of the page so the hero, controls, and result cards consume less vertical space.
2. Keep the lineage panel large on the left and dedicate the right column to a stacked operations view containing the fitness trend, critique feed, and live event log.
3. Replace the live event card list with a three-column table: sequence, event type, and a condensed summary string.
4. Keep the event panel internally scrollable, default to following new events near the bottom, and avoid disrupting the user if they scroll upward to inspect earlier rows.

**Behavior Details**

- Event rows are sorted by ascending sequence number.
- Summary strings condense payloads to human-readable highlights instead of raw multiline JSON.
- Full payload data remains accessible via native browser hover/title text.
- Mode cards stay compact but still show status, fitness, and final answer at a glance.
- Mobile keeps a stacked layout rather than forcing a dense desktop composition into a narrow viewport.

**Validation**

- On desktop, the first viewport should show benchmark results and the live log together.
- The log must render in ascending sequence order.
- The log panel should not create oversized rows from long JSON payloads.
- Existing run controls, SSE updates, and review actions must continue working.
