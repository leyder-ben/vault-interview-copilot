# Phase 4: Web Interface — Design

**Status:** approved, ready for implementation planning
**Date:** 2026-07-19
**Exit condition (from `docs/architecture/10-delivery-plan.md` / `06-ui-requirements.md`):** the typed V1 is useful in realistic interview-prep sessions — Ben can actually use it live during a mock interview and get a usable answer fast enough to matter.

## Overview

Phases 0-3 built and proved the backend: indexing, hybrid retrieval, and grounded generation all work against `sample-vault`, exposed via `POST /api/query` and `GET /api/index/status`. `apps/web/` is still an empty Phase 0 scaffold (`src/`, `tests/`, both just `.gitkeep`). Phase 4 builds the one screen that makes the backend usable mid-interview: type a shorthand query, get a speakable answer with sources, fast.

Visual direction (Ben's, locked): dark, modern-SaaS register (Linear/Vercel/Raycast-adjacent), tuned for readability over minimalism — larger type and higher text/background contrast than a typical dense dashboard. Geist font, not Inter. Green for "cited, working," blue for UI chrome, warning colors with real contrast rather than muted variants.

The design's central technical concern is the same one that drove Phase 3's citation-relevance work: **the UI must not visually conflate a genuine no-evidence abstention with a grounded-but-under-cited answer**, and — per an accessibility pass on this spec — the three colored confidence states must be distinguishable by shape/icon alone, not hue alone, since misreading confidence state is exactly the failure mode this whole design exists to prevent.

## Explicitly deferred (do not build in this phase)

- **Query history.** Listed as "useful soon after, not blocking V1" in `06-ui-requirements.md`. Deferred entirely to its own later spec rather than included now.
- **Response-mode selector, source pin/exclude, feedback controls, retrieval-debug panel.** All listed as non-blocking in `06-ui-requirements.md`; none are built in this phase.
- **`POST /api/settings/provider` UI.** No provider-switching UI in V1 — matches Phase 3's deferral of the endpoint itself.
- **Containerizing the frontend.** `docker-compose.yml` stays `postgres` + `api` only. The Vite dev server runs directly (`npm run dev`), proxying `/api/*` to the API — adding a `web` service isn't justified yet.
- **Backend generic-exception-handler hardening.** Flagged during design (see "Error handling" below) as good defense-in-depth, but it's a backend change outside this frontend spec's scope — a disclosed follow-up, not something decided here.

## Visual design tokens

**Palette (dark):**

| Role | Value | Use |
|---|---|---|
| Background | `#0B0B0D` | Page background |
| Surface | `#18181B` | Cards (answer card, source items) |
| Border | `#2A2A2E` | Card/input borders, dividers |
| Text primary | `#F5F5F7` | Body/answer text |
| Text secondary | `#A1A1AA` | Labels, metadata, timestamps |
| Blue (chrome) | `#3B82F6`, focus ring `#60A5FA` | Buttons, input focus, links |
| Green (cited/working) | `#22C55E` | "Cited" badge, healthy index status |
| Amber (abstention) | `#F59E0B` | Genuine-abstention warning |
| Red (hard error) | `#EF4444` | API/provider failure |
| Neutral badge (under-cited) | bg `#3F3F46` / text `#D4D4D8` | Quiet secondary badge, no color-coded urgency |

**Icon pairing — signal survives independent of hue** (the single most common colorblind confusion pair is red/green; these four states must not rely on hue alone to be told apart):

| Status | Color | Icon | Rationale |
|---|---|---|---|
| Cited, working answer | Green | `CheckCircle2` (lucide-react) | Filled circle + check — "done/good" |
| Genuine abstention | Amber | `AlertTriangle` | Conventional warning silhouette |
| Hard error | Red | `XCircle` | Distinct silhouette from amber's triangle — reads "stopped/failed," not "caution" |
| Grounded, under-cited | Neutral | *(none)* | Deliberately icon-free — stays quiet, doesn't compete for attention |

**Typography:** `font-family: 'Geist', 'IBM Plex Sans', system-ui, sans-serif`, self-hosted (no external font CDN — consistent with the project's local-first posture). Named Tailwind `fontSize` tokens, not the bare default scale (17px doesn't otherwise land on a Tailwind step and would silently round to 16px):

```js
fontSize: {
  meta: ['14px', { lineHeight: '1.4' }],       // labels, timestamps, metadata
  body: ['17px', { lineHeight: '1.6' }],       // supporting points, sources, general body text
  answer: ['26px', { lineHeight: '1.5', fontWeight: '600' }], // speakable answer headline
}
```
Components use `text-body`/`text-answer`/`text-meta` explicitly.

## Layout

Single centered column, max-width ~760px, chosen over a two-zone dashboard split or a command-palette overlay — closest to Raycast's single-focus feel and the simplest to get right for a V1.

```
┌─────────────────────────────────────────┐
│ TopBar: app name          [● Indexed·2h]│  quiet index status, Popover on hover/click
├─────────────────────────────────────────┤
│         [ Query input, Enter⏎ ]         │  centered column, max-width ~760px
│  ┌───────────────────────────────────┐  │
│  │ [✓ Cited]  Speakable answer...    │  │  AnswerPanel: LoadingState /
│  │                          [Copy]   │  │  ErrorCard / AnswerCard
│  │  ▸ Supporting points & examples   │  │
│  │  ▸ Sources (3)                    │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

Focus shortcut: `/` focuses the query input from anywhere on the page (matches GitHub/Slack convention, doesn't collide with the browser's own Ctrl/Cmd+K). Input also auto-focuses on page load.

## Architecture approach

Stack is locked (React + Vite + TS + Tailwind + TanStack Query — `CLAUDE.md`). The one real fork is how to build the interactive widgets:

- Considered fully custom (zero primitive deps) — maximum control, but popovers and collapsibles are exactly the category that's fiddly to hand-roll correctly (focus trapping, `aria-expanded`, escape/click-outside).
- Considered full shadcn/ui — fastest assembly, but ships its own visual defaults that would need deliberate overriding everywhere to avoid landing on the generic look this design explicitly avoids.
- **Chosen: Radix primitives (unstyled), used only for `Collapsible` and `Popover`, fully custom Tailwind everywhere else.** Radix ships zero visual opinion, so it doesn't fight the design direction, while still getting correct keyboard/focus behavior for the two widgets where that's easy to get subtly wrong. This app is keyboard-first enough (focus shortcut, Enter-to-submit) that this matters.

Icons via `lucide-react` — small, tree-shakeable, no visual opinion beyond the icon itself.

## Component tree

```
App
└─ AppShell                 (centered column, max-width, top bar slot)
   ├─ TopBar
   │  └─ IndexStatusBadge   (Radix Popover: dot+label trigger -> detail panel)
   ├─ QueryInput            (controlled input, Enter submits, "/" focuses globally)
   └─ AnswerPanel           (switches on mutation status)
      ├─ LoadingState       (skeleton, same slot/dimensions as AnswerCard)
      ├─ ErrorCard          (XCircle, red -- hard failures only)
      └─ AnswerCard
         ├─ ConfidenceBadge (green/amber/neutral -- see discriminator below)
         ├─ answer text (text-answer token) + CopyButton (copies say_this only)
         ├─ SupportingPointsDisclosure (Radix Collapsible -- supporting_points + personal_examples)
         └─ SourcesDisclosure          (Radix Collapsible -> list of SourceItem: path, heading, excerpt, score)
```

File layout under `apps/web/src/`:

```
main.tsx
App.tsx
api/
  client.ts       -- fetch wrapper + TanStack Query hooks (useQueryAnswer, useIndexStatus)
  types.ts        -- API response TypeScript types mirroring 05-api-surface.md
components/
  AppShell.tsx
  TopBar.tsx
  IndexStatusBadge.tsx
  QueryInput.tsx
  AnswerPanel.tsx
  AnswerCard.tsx
  ConfidenceBadge.tsx
  CopyButton.tsx
  SupportingPointsDisclosure.tsx
  SourcesDisclosure.tsx
  SourceItem.tsx
  LoadingState.tsx
  ErrorCard.tsx
```

## Confidence-state discriminator

Derived client-side from the existing `POST /api/query` response shape — no new backend field needed. Spelled out precisely so it can't be interpreted two different ways:

- `confidence === "low"` -> **Amber, abstention.** Backend only sets `"low"` via the retrieval-quality-gated pre-check (Phase 3), always paired with a `limitations` entry — render that message directly next to the badge.
- `confidence` is `"high"`/`"medium"` **and** `sources.length === 0` -> **Neutral, under-cited.** Quiet badge, no icon, no limitation text — this isn't a limitation the model reported, it's the disclosed citation-population gap from Phase 3 (`10-delivery-plan.md`'s open follow-up).
- `confidence` is `"high"`/`"medium"` **and** `sources.length > 0` -> **Green, cited.**
- A network/HTTP failure on the request itself (not a valid `QueryResponse`) -> **Red `ErrorCard`**, replaces the whole `AnswerPanel` slot, not just the badge.

## Index-status discriminator

Derived from the real `GET /api/index/status` response shape (`apps/api/app/api/index_status.py`: `note_count`, `embedding_model`, `last_run: { status, started_at, completed_at, files_*, errors } | null`; `status` is written as exactly `"success"` or `"failed"` by `app/ingestion/indexer.py` — no other values exist today). Spelled out explicitly since the testing section asserts a specific dot color per case:

- `last_run === null` (never indexed) -> **neutral/gray dot**, label "Not indexed."
- `last_run.status === "failed"` (or `errors` is non-empty) -> **red dot**, label "Index error" — Popover detail shows the error content from `errors`.
- `last_run.status === "success"` and no errors -> **green dot**, label "Indexed · {relative time since `completed_at`}."

No separate "stale" state for V1 — not in the required list, and inventing a staleness threshold isn't justified by anything measured yet (YAGNI).

## Data flow

**Client/server split:** Vite dev server, not containerized. `vite.config.ts`'s `server.proxy` forwards `/api/*` to `http://localhost:8000` in dev, so the app calls same-origin paths with no CORS configuration needed.

**Server state — TanStack Query, no other state library** (YAGNI: nothing here needs Redux/Zustand/Context):
- `useMutation` wraps `POST /api/query`, fired on submit (Enter or button click). Its status (`idle`/`pending`/`error`/`success`) drives `AnswerPanel`'s branch directly.
- `useQuery(['index-status'], ...)` wraps `GET /api/index/status` — fetched on mount, `refetchInterval: 120_000` (2 min) so the badge can go stale without user action, plus a manual `refetch()` when the `IndexStatusBadge` popover opens.

**Local component state:** the controlled query-input text, and the Popover's open/closed state (managed internally by Radix). That's the entire non-server-state surface.

## Error handling

Two request-failure variants, deliberately kept simple:

- **Fetch-level failure** (unreachable, timeout) -> `ErrorCard`: "Can't reach the API."
- **HTTP error response**: 4xx with a parseable JSON `detail` (e.g. Pydantic validation errors — structurally safe, field-level only) may show that `detail` text. **Any 5xx, or a non-JSON/unparseable body, always renders the fixed generic message** ("Something went wrong generating an answer") — the raw response body is never rendered verbatim, regardless of what the backend sends.

This second rule exists because of a direct check against the backend during design: `apps/api/app/main.py` has no custom exception handler, and `POST /api/query` never raises `HTTPException` with a `detail` message — an unhandled exception today falls through to Starlette's default 500 handler (plain text "Internal Server Error", not a stack trace, since `debug` is unset/`False` everywhere in the codebase). That's not a leak today, but it's incidental, not guaranteed — it would break the moment a future change adds `HTTPException(status_code=500, detail=str(e))` for a debugging convenience. Rather than make this frontend spec depend on that staying true, the frontend contract itself refuses to render 5xx bodies verbatim. A generic backend exception handler (fixed safe body for any unhandled 500) would still be good defense-in-depth — noted above as a disclosed, non-blocking follow-up.

Both variants render in the same `AnswerPanel` slot the answer would have occupied (not a toast/banner) — chosen so nothing shifts position mid-interview and an error can't be missed by being easy-to-dismiss chrome.

## Testing

Following `docs/architecture/09-testing.md`'s existing split, not inventing a new one:

- **Unit (Vitest + React Testing Library).** `ConfidenceBadge`/`ErrorCard`: each of the four states asserts the actual rendered icon component and color token, not just message text — locking the icon-pairing table in as an executable assertion so a miswiring between branches (e.g. amber's `AlertTriangle` landing on the wrong condition) fails a test instead of silently shipping:
  ```
  cited        -> renders <CheckCircle2>, class includes text-green-500 (#22C55E)
  abstention   -> renders <AlertTriangle>, class includes text-amber-500 (#F59E0B)
  under-cited  -> renders no icon, class includes neutral badge tokens (#3F3F46/#D4D4D8)
  hard error   -> renders <XCircle>, class includes text-red-500 (#EF4444)
  ```
  Also: `CopyButton` copies `say_this` only (not the full answer bundle); `IndexStatusBadge` asserts the same way per the index-status discriminator above — `last_run: null` -> gray, `status: "failed"`/non-empty `errors` -> red, `status: "success"` with no errors -> green.
- **Integration (Vitest + RTL, mocked API).** `QueryInput` submit fires `useMutation` with the correct payload; loading -> success/error transitions render the right `AnswerPanel` child; `SourcesDisclosure`/`SupportingPointsDisclosure` expand on click.
- **End-to-end (Playwright, via the `webapp-testing` skill).** Matches `09-testing.md`'s existing E2E list directly: shorthand query -> correct source appears; answer renders in expected sections; clicking a citation shows the expected excerpt; missing evidence produces the stated amber limitation, not a fabricated claim. Runs against the real API + `sample-vault`, not mocked — this is the layer that proves the UI reflects real backend behavior, not just its own mocks.
- **Model-dependent runs stay manual/separate**, same as the backend — no E2E test that would trigger a real `gpt-oss:20b` call runs in standard CI.

## Copy-button and source-display scope (resolved during design)

- Copy button copies the speakable answer (`say_this`) only, not the full answer bundle — matches the tool's purpose as a quick line to say or paste.
- Sources expand inline within the column (Radix `Collapsible`), not in a modal/drawer — consistent with the single-column layout and avoids introducing a second UI surface for a V1 this small.
