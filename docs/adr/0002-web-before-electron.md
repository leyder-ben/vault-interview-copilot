# ADR-002: Web Application Before Electron

**Status:** Accepted
**Date:** 2026-07-15

## Context

The eventual V2 vision includes live voice capture during an interview, possibly with a desktop overlay. It would be easy to jump straight to Electron and start building that overlay now, since it's the "real" end goal. But V1's actual job is much smaller: prove that typing a shorthand query returns a correct, grounded, speakable answer. Nothing about proving that requires a desktop shell — a browser tab does the job.

A lot of the interview-copilot tools reviewed during architectural recon (Section 23 of the brief) go straight for the desktop overlay and screen-capture-concealment behavior before they've proven their retrieval is any good. That's optimizing for the wrong problem first.

## Decision

Build V1 as a plain web application: React + Vite + TypeScript frontend, served locally, opened in a browser tab. No Electron packaging, no desktop overlay, no always-on-top window, no screen-capture concealment.

## Alternatives Considered

**Electron from the start:** rejected for V1. Electron adds a packaging and build layer, a different debugging story, and OS-specific quirks (especially for always-on-top / overlay behavior) — all overhead that has nothing to do with whether retrieval actually finds the right note. It's the equivalent of building a custom truck body before you know the load you're hauling. Get the engine and drivetrain (retrieval + generation) right first; the body comes later once you know exactly what it needs to do.

**Desktop overlay as the differentiator:** explicitly rejected per the brief (Section 22) — the differentiator here is accurate, grounded retrieval, not concealment or overlay polish. A browser tab proves that just as well as a floating window does.

## Consequences

**Good:** Faster to build and iterate, ordinary browser dev tools for debugging, no platform-specific packaging work until it's actually needed. Keeps V1 focused on the thing that actually matters — retrieval and answer quality.

**Trade-off:** A browser tab isn't as convenient mid-interview as a small always-on-top overlay would be. That convenience gap is accepted for V1 and deferred to V2, where it belongs — voice input and overlay behavior go together anyway (Section 3, V2 vision), so there's no reason to build half of that experience now and the other half later.

## Conditions That Would Justify Revisiting

- V1 is proven useful in real interview-prep sessions (Phase 4 exit condition) and V2 (voice input) work begins — at that point, an always-on-top overlay becomes a real requirement, not a nice-to-have.
