# Dashboard Live Log Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Update the dashboard so desktop users can see compact benchmark results and an ascending live event log table in the same viewport.

**Architecture:** Keep the existing Next.js App Router page and client dashboard component, but extract event presentation logic into small pure helpers so ordering and summary formatting can be tested independently. Then reshape the dashboard markup and CSS so the event log becomes a dense table in the right-hand operations column while the lineage panel stays prominent.

**Tech Stack:** Next.js App Router, React client components, TypeScript, CSS, Vitest

---

### Task 1: Add event presentation helpers with test-first coverage

**Files:**
- Create: `apps/web/src/lib/dashboard-presenters.ts`
- Create: `apps/web/src/lib/dashboard-presenters.test.ts`

**Step 1: Write the failing test**

Add tests that define the desired behavior for:
- Sorting events by ascending `sequence`
- Returning the latest event by order without reversing the list
- Condensing payload objects into a readable one-line summary

**Step 2: Run test to verify it fails**

Run: `pnpm exec vitest run apps/web/src/lib/dashboard-presenters.test.ts`
Expected: FAIL because the helper module does not exist yet.

**Step 3: Write minimal implementation**

Implement small pure functions for summary formatting and sorted event projection.

**Step 4: Run test to verify it passes**

Run: `pnpm exec vitest run apps/web/src/lib/dashboard-presenters.test.ts`
Expected: PASS.

### Task 2: Update dashboard markup to use the new operations layout

**Files:**
- Modify: `apps/web/src/components/dashboard-app.tsx`

**Step 1: Add the failing test coverage already created in Task 1**

Use the helper tests as the red phase for changed log behavior.

**Step 2: Implement the minimal component changes**

- Import and use the event presentation helpers
- Replace the event card list with a table
- Keep event order ascending
- Add scroll-follow behavior that only auto-scrolls when the user is near the bottom
- Compact mode cards and reorganize the analysis section into a left lineage panel and right operations column

**Step 3: Run targeted verification**

Run: `pnpm exec vitest run apps/web/src/lib/dashboard-presenters.test.ts`
Expected: PASS with the new component imports unaffected.

### Task 3: Refresh dashboard styling for the denser layout

**Files:**
- Modify: `apps/web/src/app/globals.css`

**Step 1: Implement the minimal style changes**

- Reduce the height of the hero/control/results sections on desktop
- Add table styles for the live event log
- Add right-column operations layout styles and compact mode-card styles
- Preserve responsive stacked behavior under the existing breakpoint

**Step 2: Verify lint/build**

Run: `pnpm lint`
Expected: PASS.

Run: `pnpm build`
Expected: PASS.

### Task 4: Manual behavior verification

**Files:**
- Modify: None

**Step 1: Run the app locally if needed**

Run: `pnpm dev`

**Step 2: Verify dashboard behavior**

- Start a run and confirm event rows append oldest-to-newest
- Confirm the log table stays visible with other result panels on desktop
- Confirm the log scroll follows new rows when near the bottom
- Confirm review controls still render for `human_review_required`
