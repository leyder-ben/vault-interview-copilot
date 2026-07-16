# UI Requirements — V1

Keep the interface intentionally small. Primary path: focus input, type shorthand, press Enter, read the answer.

## Required

- Large query input.
- Keyboard shortcut to focus the query input.
- Enter to submit.
- Visible loading state.
- Speakable answer at the top.
- Expandable supporting points and personal examples.
- Source list with note path, heading, and excerpt.
- Clear confidence and limitation messages.
- Copy-answer button.
- Index status indicator.

## Useful soon after (not blocking V1)

- Query history stored locally.
- Response-mode selector.
- Pin or exclude a source from the current answer.
- Feedback controls (correct source / wrong source / useful answer / unsupported claim).
- Retrieval-debug panel, dev-mode only.

## Avoid initially — do not build these without being asked

Dashboard-heavy layouts, complex note browsing, rich-text editing, always-on-top overlays, animated assistant behavior, multiple panes competing for attention. See `docs/adr/0002-web-before-electron.md` — the desktop-overlay instinct is explicitly deferred to V2.

## Design guidance

Use the `frontend-design` skill when building this. Keyboard-first, low cognitive load, no dashboard aesthetic. This is a tool meant to be glanced at mid-conversation, not a control panel.

## Phase 4 exit condition

The typed V1 is useful in realistic interview-prep sessions — meaning Ben can actually use it live during a mock interview and get a usable answer fast enough to matter.
