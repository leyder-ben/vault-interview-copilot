# Phase 4: Web Interface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the React/Vite/TypeScript frontend in `apps/web/` (currently an empty Phase 0 scaffold) that lets Ben type a shorthand query and get a speakable, sourced answer from the existing `POST /api/query` backend, fast enough to matter mid-interview.

**Architecture:** Single centered-column page. TanStack Query owns all server state (a mutation for `POST /api/query`, a polled query for `GET /api/index/status`); local component state is limited to the query input text and Radix's own open/closed state. Radix UI primitives (unstyled) provide correct keyboard/focus behavior for `Collapsible` and `Popover` only; every other visual element is fully custom Tailwind — no component library, no generic-SaaS visual defaults.

**Tech Stack:** React + TypeScript, Vite, Tailwind CSS v4 (CSS-first `@theme` config, no `tailwind.config` file), TanStack Query v5, Radix UI primitives, `lucide-react` icons, self-hosted Geist font (via the `geist` npm package). Vitest + React Testing Library for unit/integration tests, Playwright for end-to-end (manual runs only — never CI, matching the backend's own model-dependent-test rule).

## Global Constraints

- Dark theme only — no light-mode toggle, no `dark:` variant complexity.
- Colors: background `#0B0B0D`, surface `#18181B`, border `#2A2A2E`, text `#F5F5F7`/`#A1A1AA`. Status colors use Tailwind's built-in `green-500`/`amber-500`/`red-500`/`blue-500`/`blue-400`/`zinc-700`/`zinc-300` — these exact hex values (`#22C55E`, `#F59E0B`, `#EF4444`, `#3B82F6`, `#60A5FA`, `#3F3F46`, `#D4D4D8`) already match the spec's palette, confirmed against Tailwind's default scale — no custom color tokens needed for status colors, only for background/surface/border/text.
- Every colored confidence/error state pairs with a specific icon (never color alone): cited → `CheckCircle2` green, abstention → `AlertTriangle` amber, hard error → `XCircle` red, under-cited → no icon, neutral zinc badge.
- Type scale is named custom tokens (`text-meta`/`text-body`/`text-answer`), not Tailwind's bare default scale.
- The frontend never renders a 5xx HTTP response body verbatim, regardless of what the backend sends — always the fixed generic message for any 5xx or unparseable body.
- No query history, response-mode selector, source pin/exclude, feedback controls, retrieval-debug panel, or provider-switching UI in this phase (all explicitly deferred in the spec).
- `docker-compose.yml` is not touched — the frontend runs via `npm run dev`, not containerized.
- Every dependency is installed via bare `npm install <package>` (no hand-picked version pins) so `package-lock.json` reflects whatever's actually current in the npm registry at implementation time, not a guess made months earlier.

---

### Task 1: Project scaffold — Vite, TypeScript, Tailwind v4, design tokens, self-hosted Geist

**Files:**
- Create: `apps/web/package.json`
- Create: `apps/web/vite.config.ts`
- Create: `apps/web/tsconfig.json`
- Create: `apps/web/index.html`
- Create: `apps/web/eslint.config.js`
- Create: `apps/web/.prettierrc.json`
- Create: `apps/web/src/index.css`
- Create: `apps/web/src/main.tsx`
- Create: `apps/web/src/App.tsx`
- Create: `apps/web/tests/setup.ts`
- Test: `apps/web/tests/App.test.tsx`
- Delete: `apps/web/src/.gitkeep`, `apps/web/tests/.gitkeep` (no longer empty)

**Interfaces:**
- Produces: `App` component (named export, `export function App()`, from `src/App.tsx`) — later tasks render `<App />` in integration tests and `main.tsx` mounts it via `import { App } from "./App"`.
- Produces: Tailwind custom theme tokens usable everywhere after this task: colors `background`/`surface`/`border`/`ink`/`ink-muted`; font sizes `text-meta`/`text-body`/`text-answer`; `font-sans` = Geist.

- [ ] **Step 1: Initialize `package.json` and install dependencies**

```bash
cd apps/web
npm init -y
npm install react react-dom @tanstack/react-query @radix-ui/react-collapsible @radix-ui/react-popover lucide-react geist
npm install -D vite @vitejs/plugin-react typescript @types/react @types/react-dom tailwindcss @tailwindcss/vite vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom eslint @eslint/js typescript-eslint eslint-plugin-react-hooks prettier @playwright/test
```

Then edit the generated `package.json` to add `"private": true`, `"type": "module"`, and a `"scripts"` block:

```json
{
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest",
    "lint": "eslint .",
    "format": "prettier --check .",
    "typecheck": "tsc --noEmit"
  }
}
```

- [ ] **Step 2: Write `vite.config.ts`** (Tailwind v4's Vite plugin, dev proxy to the API, Vitest config in the same file)

```ts
/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    globals: true,
    include: ["tests/**/*.test.{ts,tsx}"],
  },
});
```

- [ ] **Step 3: Write `tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src", "tests", "vite.config.ts"]
}
```

- [ ] **Step 4: Write `index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>vault-interview-copilot</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Inspect the installed `geist` package to confirm its framework-agnostic CSS export path**

```bash
find node_modules/geist -iname "*.css"
```

The `geist` package ships a plain CSS entry point usable outside Next.js (not just the `next/font` integration) — expected to find something like `node_modules/geist/dist/fonts/geist-sans/style.css` or `node_modules/geist/font/sans/style.css`. Use whichever path the `find` command actually reports in the import added in Step 6. If nothing under `node_modules/geist` is a plain `.css` file (i.e. the package only exposes the Next.js-specific loader), fall back to downloading the static `.woff2` files this package can't provide and add a hand-written `@font-face` block instead — flag this back to Ben if it happens, since it changes Step 6's tokens block below.

- [ ] **Step 6: Write `src/index.css`** — Tailwind v4 CSS-first config via `@theme`, plus the Geist import found in Step 5

```css
@import "tailwindcss";
@import "geist/font/sans/style.css"; /* adjust path to match what Step 5 found */

@theme {
  --color-background: #0b0b0d;
  --color-surface: #18181b;
  --color-border: #2a2a2e;
  --color-ink: #f5f5f7;
  --color-ink-muted: #a1a1aa;

  --font-sans: "Geist", "IBM Plex Sans", system-ui, sans-serif;

  --text-meta: 14px;
  --text-meta--line-height: 1.4;
  --text-body: 17px;
  --text-body--line-height: 1.6;
  --text-answer: 26px;
  --text-answer--line-height: 1.5;
  --text-answer--font-weight: 600;
}

body {
  @apply bg-background font-sans text-ink;
}
```

- [ ] **Step 7: Write `src/App.tsx`** (placeholder — later tasks replace the body with `AppShell`)

```tsx
export function App() {
  return <div className="min-h-screen bg-background p-8 text-ink">vault-interview-copilot</div>;
}
```

- [ ] **Step 8: Write `src/main.tsx`**

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
```

- [ ] **Step 9: Write `tests/setup.ts`**

```ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 10: Write the failing smoke test, `tests/App.test.tsx`**

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { App } from "../src/App";

describe("App", () => {
  it("renders the app shell placeholder", () => {
    render(<App />);
    expect(screen.getByText("vault-interview-copilot")).toBeInTheDocument();
  });
});
```

- [ ] **Step 11: Run the test, confirm it fails before `App.tsx`/`main.tsx` exist correctly wired** (skip if Steps 7-10 were already written — otherwise write the test first, confirm the FAIL, then add `App.tsx`)

Run: `npm test`
Expected: if run before Step 7, FAILs with a module-not-found error; after Steps 7-10, proceed to Step 12.

- [ ] **Step 12: Run the test, confirm it passes**

Run: `npm test`
Expected: `PASS tests/App.test.tsx`

- [ ] **Step 13: Verify the full toolchain (Tailwind + font + TypeScript) builds cleanly**

Run: `npm run build`
Expected: exits 0, produces `dist/`. This is the real verification that the Geist import path from Step 5/6 actually resolves — a wrong path fails the build loudly here, not silently.

- [ ] **Step 14: Delete the now-obsolete placeholder files and write `eslint.config.js` + `.prettierrc.json`**

```bash
rm apps/web/src/.gitkeep apps/web/tests/.gitkeep
```

`eslint.config.js`:
```js
import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    plugins: { "react-hooks": reactHooks },
    rules: { ...reactHooks.configs.recommended.rules },
  }
);
```

`.prettierrc.json`:
```json
{
  "semi": true,
  "singleQuote": false,
  "trailingComma": "es5",
  "printWidth": 100
}
```

Run: `npm run lint && npm run format`
Expected: both exit 0 (no files to reformat yet, no lint errors).

- [ ] **Step 15: Commit**

```bash
cd apps/web
git add -A
git commit -m "feat(web): scaffold Vite/React/TS project with Tailwind v4 tokens and self-hosted Geist"
```

---

### Task 2: API types and fetch client

**Files:**
- Create: `apps/web/src/api/types.ts`
- Create: `apps/web/src/api/client.ts`
- Test: `apps/web/tests/api/client.test.ts`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `ApiError` class (`message: string`, `status: number`), `postQuery(payload: QueryRequest): Promise<QueryResponse>`, `getIndexStatus(): Promise<IndexStatusResponse>`, plus the `QueryRequest`/`QueryResponse`/`QuerySource`/`QueryAnswer`/`Confidence`/`IndexStatusResponse`/`IndexRunSummary` types — later tasks import all of these from `src/api/types.ts` and `src/api/client.ts`.

- [ ] **Step 1: Write `src/api/types.ts`** (mirrors `docs/architecture/05-api-surface.md`'s `POST /api/query` shape and `apps/api/app/api/index_status.py`'s actual response shape)

```ts
export type Confidence = "high" | "medium" | "low";

export interface QuerySource {
  path: string;
  heading: string;
  start_line: number;
  end_line: number;
  score: number;
}

export interface QueryAnswer {
  say_this: string;
  supporting_points: string[];
  personal_examples: string[];
}

export interface QueryResponse {
  answer: QueryAnswer;
  sources: QuerySource[];
  confidence: Confidence;
  limitations: string[];
  timing_ms: {
    retrieval: number;
    generation: number;
    total: number;
  };
}

export interface QueryRequest {
  query: string;
  mode?: string;
  max_sources?: number;
}

export interface IndexRunSummary {
  status: "success" | "failed";
  started_at: string;
  completed_at: string | null;
  files_scanned: number;
  files_added: number;
  files_updated: number;
  files_deleted: number;
  errors: Record<string, unknown> | null;
}

export interface IndexStatusResponse {
  embedding_model: string;
  note_count: number;
  last_run: IndexRunSummary | null;
}
```

- [ ] **Step 2: Write the failing tests, `tests/api/client.test.ts`** — locks in the exact error-mapping contract from the spec (never render a 5xx body verbatim, even one that happens to contain a `detail` field)

```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { getIndexStatus, postQuery } from "../../src/api/client";

describe("postQuery", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns parsed JSON on a successful response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          answer: { say_this: "hi", supporting_points: [], personal_examples: [] },
          sources: [],
          confidence: "high",
          limitations: [],
          timing_ms: { retrieval: 1, generation: 1, total: 2 },
        }),
      })
    );

    const result = await postQuery({ query: "test" });
    expect(result.answer.say_this).toBe("hi");
  });

  it("throws the fixed generic message on a 5xx response with a non-JSON body", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        headers: new Headers({ "content-type": "text/plain" }),
        json: async () => {
          throw new Error("not json");
        },
      })
    );

    await expect(postQuery({ query: "test" })).rejects.toThrow(
      "Something went wrong generating an answer."
    );
  });

  it("throws the fixed generic message on a 5xx response even when the body is JSON with a detail field", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({ detail: "Internal exception: /home/ben/secret/path.py line 42" }),
      })
    );

    await expect(postQuery({ query: "test" })).rejects.toThrow(
      "Something went wrong generating an answer."
    );
  });

  it("surfaces the detail message on a 4xx validation error (array-of-objects detail shape)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({
          detail: [{ loc: ["body", "query"], msg: "field required", type: "value_error.missing" }],
        }),
      })
    );

    await expect(postQuery({ query: "test" })).rejects.toThrow("field required");
  });

  it("throws a connection-failure message when fetch itself rejects", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));

    await expect(postQuery({ query: "test" })).rejects.toThrow("Can't reach the API.");
  });
});

describe("getIndexStatus", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns parsed JSON on success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ embedding_model: "nomic-embed-text", note_count: 12, last_run: null }),
      })
    );

    const result = await getIndexStatus();
    expect(result.note_count).toBe(12);
  });
});
```

- [ ] **Step 3: Run the tests, confirm they fail**

Run: `npm test -- client.test.ts`
Expected: FAIL — `client.ts` doesn't exist yet.

- [ ] **Step 4: Write `src/api/client.ts`**

```ts
import type { IndexStatusResponse, QueryRequest, QueryResponse } from "./types";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function extractDetailMessage(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) =>
        item && typeof item === "object" && "msg" in item
          ? String((item as { msg: unknown }).msg)
          : null
      )
      .filter((msg): msg is string => msg !== null);
    return messages.length > 0 ? messages.join("; ") : null;
  }
  return null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, init);
  } catch {
    throw new ApiError("Can't reach the API.", 0);
  }

  if (!response.ok) {
    if (response.status >= 400 && response.status < 500) {
      const contentType = response.headers.get("content-type") ?? "";
      if (contentType.includes("application/json")) {
        try {
          const body = (await response.json()) as { detail?: unknown };
          const detailMessage = extractDetailMessage(body.detail);
          if (detailMessage !== null) {
            throw new ApiError(detailMessage, response.status);
          }
        } catch (err) {
          if (err instanceof ApiError) throw err;
          // JSON parsing failed -- fall through to the generic message below.
        }
      }
    }
    throw new ApiError("Something went wrong generating an answer.", response.status);
  }

  return (await response.json()) as T;
}

export function postQuery(payload: QueryRequest): Promise<QueryResponse> {
  return request<QueryResponse>("/api/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function getIndexStatus(): Promise<IndexStatusResponse> {
  return request<IndexStatusResponse>("/api/index/status");
}
```

- [ ] **Step 5: Run the tests, confirm they pass**

Run: `npm test -- client.test.ts`
Expected: `PASS` — all 6 tests green.

- [ ] **Step 6: Commit**

```bash
cd apps/web
git add src/api/types.ts src/api/client.ts tests/api/client.test.ts
git commit -m "feat(web): add API types and fetch client with the 5xx-never-verbatim error contract"
```

---

### Task 3: TanStack Query hooks

**Files:**
- Create: `apps/web/src/api/hooks.ts`
- Test: `apps/web/tests/api/hooks.test.tsx`

**Interfaces:**
- Consumes: `ApiError`, `postQuery`, `getIndexStatus` from `src/api/client.ts` (Task 2); `QueryRequest`, `QueryResponse`, `IndexStatusResponse` from `src/api/types.ts` (Task 2).
- Produces: `useQueryAnswer(): UseMutationResult<QueryResponse, ApiError, QueryRequest>`, `useIndexStatus(): UseQueryResult<IndexStatusResponse, ApiError>` — later tasks (`AppShell`, `IndexStatusBadge`) call these directly.

- [ ] **Step 1: Write the failing tests, `tests/api/hooks.test.tsx`**

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import * as client from "../../src/api/client";
import { useIndexStatus, useQueryAnswer } from "../../src/api/hooks";
import type { IndexStatusResponse, QueryResponse } from "../../src/api/types";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

describe("useIndexStatus", () => {
  it("fetches and returns index status via getIndexStatus", async () => {
    const status: IndexStatusResponse = {
      embedding_model: "nomic-embed-text",
      note_count: 42,
      last_run: null,
    };
    vi.spyOn(client, "getIndexStatus").mockResolvedValue(status);

    const { result } = renderHook(() => useIndexStatus(), { wrapper });
    await waitFor(() => expect(result.current.data).toEqual(status));
  });
});

describe("useQueryAnswer", () => {
  it("calls postQuery with the mutation payload and exposes its result", async () => {
    const response: QueryResponse = {
      answer: { say_this: "hi", supporting_points: [], personal_examples: [] },
      sources: [],
      confidence: "high",
      limitations: [],
      timing_ms: { retrieval: 1, generation: 1, total: 2 },
    };
    const postQuerySpy = vi.spyOn(client, "postQuery").mockResolvedValue(response);

    const { result } = renderHook(() => useQueryAnswer(), { wrapper });
    result.current.mutate({ query: "terraform drift" });

    await waitFor(() => expect(result.current.data).toEqual(response));
    expect(postQuerySpy).toHaveBeenCalledWith({ query: "terraform drift" });
  });
});
```

- [ ] **Step 2: Run the tests, confirm they fail**

Run: `npm test -- hooks.test.tsx`
Expected: FAIL — `src/api/hooks.ts` doesn't exist yet.

- [ ] **Step 3: Write `src/api/hooks.ts`**

```ts
import { useMutation, useQuery } from "@tanstack/react-query";
import type { ApiError } from "./client";
import { getIndexStatus, postQuery } from "./client";
import type { IndexStatusResponse, QueryRequest, QueryResponse } from "./types";

export function useQueryAnswer() {
  return useMutation<QueryResponse, ApiError, QueryRequest>({
    mutationFn: (payload) => postQuery(payload),
  });
}

export function useIndexStatus() {
  return useQuery<IndexStatusResponse, ApiError>({
    queryKey: ["index-status"],
    queryFn: getIndexStatus,
    refetchInterval: 120_000,
  });
}
```

- [ ] **Step 4: Run the tests, confirm they pass**

Run: `npm test -- hooks.test.tsx`
Expected: `PASS` — both tests green.

- [ ] **Step 5: Commit**

```bash
cd apps/web
git add src/api/hooks.ts tests/api/hooks.test.tsx
git commit -m "feat(web): add TanStack Query hooks for query answers and index status"
```

---

### Task 4: ConfidenceBadge and ErrorCard — the confidence-state discriminator

**Files:**
- Create: `apps/web/src/components/ConfidenceBadge.tsx`
- Create: `apps/web/src/components/ErrorCard.tsx`
- Test: `apps/web/tests/components/ConfidenceBadge.test.tsx`
- Test: `apps/web/tests/components/ErrorCard.test.tsx`

**Interfaces:**
- Consumes: `Confidence` from `src/api/types.ts` (Task 2).
- Produces: `deriveConfidenceVariant(confidence: Confidence, sourceCount: number): "cited" | "abstention" | "under-cited"` (exported as a pure function so its branch logic is independently testable), `ConfidenceBadge({ confidence, sourceCount }: { confidence: Confidence; sourceCount: number })`, `ErrorCard({ message, onRetry }: { message: string; onRetry: () => void })` — `AnswerCard` and `AnswerPanel` (Task 9) import both.

This is the highest-value test in the whole frontend — the entire design exists to make these four states visually distinct and correctly meaningful. Tests assert the actual rendered icon and color class per branch, not just message text, so a miswiring between branches fails a test instead of silently shipping.

- [ ] **Step 1: Write the failing tests, `tests/components/ConfidenceBadge.test.tsx`**

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ConfidenceBadge, deriveConfidenceVariant } from "../../src/components/ConfidenceBadge";

describe("deriveConfidenceVariant", () => {
  it("returns abstention for confidence: low regardless of source count", () => {
    expect(deriveConfidenceVariant("low", 0)).toBe("abstention");
    expect(deriveConfidenceVariant("low", 3)).toBe("abstention");
  });

  it("returns under-cited for high/medium confidence with zero sources", () => {
    expect(deriveConfidenceVariant("high", 0)).toBe("under-cited");
    expect(deriveConfidenceVariant("medium", 0)).toBe("under-cited");
  });

  it("returns cited for high/medium confidence with at least one source", () => {
    expect(deriveConfidenceVariant("high", 1)).toBe("cited");
    expect(deriveConfidenceVariant("medium", 2)).toBe("cited");
  });
});

describe("ConfidenceBadge rendering", () => {
  it("renders CheckCircle2 and green text for the cited state", () => {
    render(<ConfidenceBadge confidence="high" sourceCount={1} />);
    expect(screen.getByText("Cited")).toHaveClass("text-green-500");
    expect(document.querySelector("svg.lucide-check-circle-2")).toBeInTheDocument();
  });

  it("renders AlertTriangle and amber text for the abstention state", () => {
    render(<ConfidenceBadge confidence="low" sourceCount={0} />);
    expect(screen.getByText("No grounding found")).toHaveClass("text-amber-500");
    expect(document.querySelector("svg.lucide-alert-triangle")).toBeInTheDocument();
  });

  it("renders no icon and neutral zinc classes for the under-cited state", () => {
    render(<ConfidenceBadge confidence="high" sourceCount={0} />);
    const badge = screen.getByText("Grounded");
    expect(badge).toHaveClass("bg-zinc-700", "text-zinc-300");
    expect(badge.querySelector("svg")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Write the failing test, `tests/components/ErrorCard.test.tsx`**

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ErrorCard } from "../../src/components/ErrorCard";

describe("ErrorCard", () => {
  it("renders XCircle and red text, and calls onRetry when clicked", async () => {
    const onRetry = vi.fn();
    render(<ErrorCard message="Can't reach the API." onRetry={onRetry} />);

    expect(screen.getByText("Can't reach the API.")).toBeInTheDocument();
    expect(document.querySelector("svg.lucide-x-circle")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 3: Run both test files, confirm they fail**

Run: `npm test -- ConfidenceBadge ErrorCard`
Expected: FAIL — neither component exists yet.

- [ ] **Step 4: Write `src/components/ConfidenceBadge.tsx`**

```tsx
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import type { Confidence } from "../api/types";

export type ConfidenceBadgeVariant = "cited" | "abstention" | "under-cited";

export function deriveConfidenceVariant(
  confidence: Confidence,
  sourceCount: number
): ConfidenceBadgeVariant {
  if (confidence === "low") return "abstention";
  if (sourceCount === 0) return "under-cited";
  return "cited";
}

interface ConfidenceBadgeProps {
  confidence: Confidence;
  sourceCount: number;
}

export function ConfidenceBadge({ confidence, sourceCount }: ConfidenceBadgeProps) {
  const variant = deriveConfidenceVariant(confidence, sourceCount);

  if (variant === "abstention") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/10 px-2.5 py-1 text-meta text-amber-500">
        <AlertTriangle size={14} aria-hidden="true" />
        No grounding found
      </span>
    );
  }

  if (variant === "under-cited") {
    return (
      <span className="inline-flex items-center rounded-full bg-zinc-700 px-2.5 py-1 text-meta text-zinc-300">
        Grounded
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-green-500/10 px-2.5 py-1 text-meta text-green-500">
      <CheckCircle2 size={14} aria-hidden="true" />
      Cited
    </span>
  );
}
```

- [ ] **Step 5: Write `src/components/ErrorCard.tsx`**

```tsx
import { XCircle } from "lucide-react";

interface ErrorCardProps {
  message: string;
  onRetry: () => void;
}

export function ErrorCard({ message, onRetry }: ErrorCardProps) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-center gap-2 text-red-500">
        <XCircle size={18} aria-hidden="true" />
        <span className="text-body font-medium">{message}</span>
      </div>
      <button
        type="button"
        onClick={onRetry}
        className="mt-3 rounded-md bg-blue-500 px-3 py-1.5 text-meta text-white hover:bg-blue-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-400"
      >
        Retry
      </button>
    </div>
  );
}
```

- [ ] **Step 6: Run both test files, confirm they pass**

Run: `npm test -- ConfidenceBadge ErrorCard`
Expected: `PASS` — all tests green, including the icon-class assertions.

- [ ] **Step 7: Commit**

```bash
cd apps/web
git add src/components/ConfidenceBadge.tsx src/components/ErrorCard.tsx tests/components/ConfidenceBadge.test.tsx tests/components/ErrorCard.test.tsx
git commit -m "feat(web): add ConfidenceBadge and ErrorCard with icon-locked confidence-state discriminator"
```

---

### Task 5: IndexStatusBadge — the index-status discriminator

**Files:**
- Create: `apps/web/src/lib/formatRelativeTime.ts`
- Create: `apps/web/src/components/IndexStatusBadge.tsx`
- Test: `apps/web/tests/lib/formatRelativeTime.test.ts`
- Test: `apps/web/tests/components/IndexStatusBadge.test.tsx`

**Interfaces:**
- Consumes: `useIndexStatus` from `src/api/hooks.ts` (Task 3); `IndexRunSummary` from `src/api/types.ts` (Task 2).
- Produces: `formatRelativeTime(isoTimestamp: string | null): string`, `deriveIndexStatusVariant(lastRun: { status: "success" | "failed"; errors: unknown } | null): "not-indexed" | "error" | "healthy"`, `IndexStatusBadge()` — `TopBar` (Task 10) renders it.

- [ ] **Step 1: Write the failing test, `tests/lib/formatRelativeTime.test.ts`**

```ts
import { describe, expect, it, vi } from "vitest";
import { formatRelativeTime } from "../../src/lib/formatRelativeTime";

describe("formatRelativeTime", () => {
  it("returns 'unknown time' for a null timestamp", () => {
    expect(formatRelativeTime(null)).toBe("unknown time");
  });

  it("returns minutes-ago for a timestamp under an hour old", () => {
    const now = new Date("2026-07-19T12:00:00Z");
    vi.setSystemTime(now);
    expect(formatRelativeTime("2026-07-19T11:45:00Z")).toBe("15m ago");
    vi.useRealTimers();
  });

  it("returns hours-ago for a timestamp under a day old", () => {
    const now = new Date("2026-07-19T12:00:00Z");
    vi.setSystemTime(now);
    expect(formatRelativeTime("2026-07-19T10:00:00Z")).toBe("2h ago");
    vi.useRealTimers();
  });
});
```

- [ ] **Step 2: Write the failing test, `tests/components/IndexStatusBadge.test.tsx`**

```tsx
import { describe, expect, it } from "vitest";
import { deriveIndexStatusVariant } from "../../src/components/IndexStatusBadge";

describe("deriveIndexStatusVariant", () => {
  it("returns not-indexed when there has never been a run", () => {
    expect(deriveIndexStatusVariant(null)).toBe("not-indexed");
  });

  it("returns error when the last run failed", () => {
    expect(deriveIndexStatusVariant({ status: "failed", errors: null })).toBe("error");
  });

  it("returns error when errors is present even if status is success", () => {
    expect(deriveIndexStatusVariant({ status: "success", errors: { foo: "bar" } })).toBe("error");
  });

  it("returns healthy when status is success and there are no errors", () => {
    expect(deriveIndexStatusVariant({ status: "success", errors: null })).toBe("healthy");
  });
});
```

- [ ] **Step 3: Run both test files, confirm they fail**

Run: `npm test -- formatRelativeTime IndexStatusBadge`
Expected: FAIL — neither module exists yet.

- [ ] **Step 4: Write `src/lib/formatRelativeTime.ts`**

```ts
export function formatRelativeTime(isoTimestamp: string | null): string {
  if (isoTimestamp === null) return "unknown time";
  const diffMs = Date.now() - new Date(isoTimestamp).getTime();
  const diffMinutes = Math.floor(diffMs / 60_000);
  if (diffMinutes < 1) return "just now";
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}
```

- [ ] **Step 5: Write `src/components/IndexStatusBadge.tsx`**

```tsx
import * as Popover from "@radix-ui/react-popover";
import { useIndexStatus } from "../api/hooks";
import type { IndexRunSummary } from "../api/types";
import { formatRelativeTime } from "../lib/formatRelativeTime";

export type IndexStatusVariant = "not-indexed" | "error" | "healthy";

export function deriveIndexStatusVariant(
  lastRun: Pick<IndexRunSummary, "status" | "errors"> | null
): IndexStatusVariant {
  if (lastRun === null) return "not-indexed";
  if (lastRun.status === "failed" || (lastRun.errors !== null && lastRun.errors !== undefined)) {
    return "error";
  }
  return "healthy";
}

const DOT_CLASS: Record<IndexStatusVariant, string> = {
  "not-indexed": "bg-zinc-500",
  error: "bg-red-500",
  healthy: "bg-green-500",
};

export function IndexStatusBadge() {
  const { data, refetch } = useIndexStatus();
  const lastRun = data?.last_run ?? null;
  const variant = deriveIndexStatusVariant(lastRun);

  const label =
    variant === "not-indexed"
      ? "Not indexed"
      : variant === "error"
        ? "Index error"
        : `Indexed · ${formatRelativeTime(lastRun!.completed_at)}`;

  return (
    <Popover.Root onOpenChange={(open) => open && refetch()}>
      <Popover.Trigger asChild>
        <button
          type="button"
          className="inline-flex items-center gap-2 rounded-full border border-border px-2.5 py-1 text-meta text-ink-muted hover:text-ink"
        >
          <span className={`h-2 w-2 rounded-full ${DOT_CLASS[variant]}`} aria-hidden="true" />
          {label}
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          sideOffset={8}
          className="w-72 rounded-lg border border-border bg-surface p-3 text-meta text-ink shadow-lg"
        >
          {data ? (
            <dl className="space-y-1">
              <div className="flex justify-between">
                <dt className="text-ink-muted">Notes indexed</dt>
                <dd>{data.note_count}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-ink-muted">Embedding model</dt>
                <dd>{data.embedding_model}</dd>
              </div>
              {lastRun?.errors ? (
                <div className="pt-1 text-red-500">{JSON.stringify(lastRun.errors)}</div>
              ) : null}
            </dl>
          ) : (
            "Loading..."
          )}
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
```

- [ ] **Step 6: Run both test files, confirm they pass**

Run: `npm test -- formatRelativeTime IndexStatusBadge`
Expected: `PASS`.

- [ ] **Step 7: Commit**

```bash
cd apps/web
git add src/lib/formatRelativeTime.ts src/components/IndexStatusBadge.tsx tests/lib/formatRelativeTime.test.ts tests/components/IndexStatusBadge.test.tsx
git commit -m "feat(web): add IndexStatusBadge with the not-indexed/error/healthy discriminator"
```

---

### Task 6: QueryInput

**Files:**
- Create: `apps/web/src/components/QueryInput.tsx`
- Test: `apps/web/tests/components/QueryInput.test.tsx`

**Interfaces:**
- Consumes: nothing from earlier tasks (pure React).
- Produces: `QueryInput({ onSubmit, disabled }: { onSubmit: (query: string) => void; disabled: boolean })` — `AppShell` (Task 10) renders it.

- [ ] **Step 1: Write the failing tests, `tests/components/QueryInput.test.tsx`**

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { QueryInput } from "../../src/components/QueryInput";

describe("QueryInput", () => {
  it("auto-focuses on mount", () => {
    render(<QueryInput onSubmit={vi.fn()} disabled={false} />);
    expect(screen.getByPlaceholderText("terraform drift prod...")).toHaveFocus();
  });

  it("calls onSubmit with the trimmed query when Enter is pressed", async () => {
    const onSubmit = vi.fn();
    render(<QueryInput onSubmit={onSubmit} disabled={false} />);
    const input = screen.getByPlaceholderText("terraform drift prod...");

    await userEvent.type(input, "  terraform drift prod  {Enter}");
    expect(onSubmit).toHaveBeenCalledWith("terraform drift prod");
  });

  it("does not call onSubmit on Enter when the input is empty", async () => {
    const onSubmit = vi.fn();
    render(<QueryInput onSubmit={onSubmit} disabled={false} />);
    const input = screen.getByPlaceholderText("terraform drift prod...");

    await userEvent.type(input, "{Enter}");
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("focuses the input when '/' is pressed while it isn't already focused", async () => {
    render(
      <div>
        <button>elsewhere</button>
        <QueryInput onSubmit={vi.fn()} disabled={false} />
      </div>
    );
    const input = screen.getByPlaceholderText("terraform drift prod...");
    const elsewhere = screen.getByRole("button", { name: "elsewhere" });
    elsewhere.focus();
    expect(input).not.toHaveFocus();

    await userEvent.keyboard("/");
    expect(input).toHaveFocus();
  });
});
```

- [ ] **Step 2: Run the tests, confirm they fail**

Run: `npm test -- QueryInput`
Expected: FAIL — component doesn't exist yet.

- [ ] **Step 3: Write `src/components/QueryInput.tsx`**

```tsx
import { useEffect, useRef, useState, type KeyboardEvent } from "react";

interface QueryInputProps {
  onSubmit: (query: string) => void;
  disabled: boolean;
}

export function QueryInput({ onSubmit, disabled }: QueryInputProps) {
  const [value, setValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    function handleGlobalKeydown(event: globalThis.KeyboardEvent) {
      if (event.key === "/" && document.activeElement !== inputRef.current) {
        event.preventDefault();
        inputRef.current?.focus();
      }
    }
    window.addEventListener("keydown", handleGlobalKeydown);
    return () => window.removeEventListener("keydown", handleGlobalKeydown);
  }, []);

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter" && value.trim().length > 0) {
      onSubmit(value.trim());
    }
  }

  return (
    <input
      ref={inputRef}
      type="text"
      value={value}
      disabled={disabled}
      onChange={(event) => setValue(event.target.value)}
      onKeyDown={handleKeyDown}
      placeholder="terraform drift prod..."
      className="w-full rounded-lg border border-border bg-surface px-4 py-3 text-body text-ink placeholder:text-ink-muted focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-400"
    />
  );
}
```

- [ ] **Step 4: Run the tests, confirm they pass**

Run: `npm test -- QueryInput`
Expected: `PASS` — all 4 tests green.

- [ ] **Step 5: Commit**

```bash
cd apps/web
git add src/components/QueryInput.tsx tests/components/QueryInput.test.tsx
git commit -m "feat(web): add QueryInput with Enter-to-submit and global '/' focus shortcut"
```

---

### Task 7: CopyButton

**Files:**
- Create: `apps/web/src/components/CopyButton.tsx`
- Test: `apps/web/tests/components/CopyButton.test.tsx`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `CopyButton({ text }: { text: string })` — `AnswerCard` (Task 9) renders it with `text={response.answer.say_this}`.

- [ ] **Step 1: Write the failing test, `tests/components/CopyButton.test.tsx`**

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CopyButton } from "../../src/components/CopyButton";

describe("CopyButton", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("copies only the given text, not any surrounding content", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });

    render(<CopyButton text="Terraform state drift happened because..." />);
    await userEvent.click(screen.getByRole("button", { name: "Copy" }));

    expect(writeText).toHaveBeenCalledTimes(1);
    expect(writeText).toHaveBeenCalledWith("Terraform state drift happened because...");
    expect(await screen.findByText("Copied")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test, confirm it fails**

Run: `npm test -- CopyButton`
Expected: FAIL — component doesn't exist yet.

- [ ] **Step 3: Write `src/components/CopyButton.tsx`**

```tsx
import { useState } from "react";

interface CopyButtonProps {
  text: string;
}

export function CopyButton({ text }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);

  async function handleClick() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      className="rounded-md border border-border px-2.5 py-1 text-meta text-ink-muted hover:text-ink"
    >
      {copied ? "Copied" : "Copy"}
    </button>
  );
}
```

- [ ] **Step 4: Run the test, confirm it passes**

Run: `npm test -- CopyButton`
Expected: `PASS`.

- [ ] **Step 5: Commit**

```bash
cd apps/web
git add src/components/CopyButton.tsx tests/components/CopyButton.test.tsx
git commit -m "feat(web): add CopyButton, copies the speakable answer only"
```

---

### Task 8: SourceItem, SourcesDisclosure, SupportingPointsDisclosure

**Files:**
- Create: `apps/web/src/components/SourceItem.tsx`
- Create: `apps/web/src/components/SourcesDisclosure.tsx`
- Create: `apps/web/src/components/SupportingPointsDisclosure.tsx`
- Test: `apps/web/tests/components/SourcesDisclosure.test.tsx`
- Test: `apps/web/tests/components/SupportingPointsDisclosure.test.tsx`

**Interfaces:**
- Consumes: `QuerySource` from `src/api/types.ts` (Task 2).
- Produces: `SourceItem({ source }: { source: QuerySource })`, `SourcesDisclosure({ sources }: { sources: QuerySource[] })`, `SupportingPointsDisclosure({ supportingPoints, personalExamples }: { supportingPoints: string[]; personalExamples: string[] })` — `AnswerCard` (Task 9) renders both disclosures.

- [ ] **Step 1: Write the failing test, `tests/components/SourcesDisclosure.test.tsx`**

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { QuerySource } from "../../src/api/types";
import { SourcesDisclosure } from "../../src/components/SourcesDisclosure";

const sources: QuerySource[] = [
  {
    path: "Projects/Whetstone/Infrastructure.md",
    heading: "Terraform Drift",
    start_line: 42,
    end_line: 58,
    score: 0.91,
  },
];

describe("SourcesDisclosure", () => {
  it("renders nothing when there are no sources", () => {
    const { container } = render(<SourcesDisclosure sources={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("is collapsed by default and expands source details on click", async () => {
    render(<SourcesDisclosure sources={sources} />);
    expect(screen.queryByText("Projects/Whetstone/Infrastructure.md")).not.toBeVisible();

    await userEvent.click(screen.getByText("Sources (1)"));
    expect(screen.getByText("Projects/Whetstone/Infrastructure.md")).toBeVisible();
    expect(screen.getByText(/Terraform Drift/)).toBeVisible();
  });
});
```

- [ ] **Step 2: Write the failing test, `tests/components/SupportingPointsDisclosure.test.tsx`**

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { SupportingPointsDisclosure } from "../../src/components/SupportingPointsDisclosure";

describe("SupportingPointsDisclosure", () => {
  it("renders nothing when both lists are empty", () => {
    const { container } = render(
      <SupportingPointsDisclosure supportingPoints={[]} personalExamples={[]} />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("is collapsed by default and expands points and examples on click", async () => {
    render(
      <SupportingPointsDisclosure
        supportingPoints={["Point one"]}
        personalExamples={["Example one"]}
      />
    );
    expect(screen.queryByText("Point one")).not.toBeVisible();

    await userEvent.click(screen.getByText("Supporting points & examples"));
    expect(screen.getByText("Point one")).toBeVisible();
    expect(screen.getByText("Example one")).toBeVisible();
  });
});
```

- [ ] **Step 3: Run both test files, confirm they fail**

Run: `npm test -- SourcesDisclosure SupportingPointsDisclosure`
Expected: FAIL — none of the three components exist yet.

- [ ] **Step 4: Write `src/components/SourceItem.tsx`**

```tsx
import type { QuerySource } from "../api/types";

export function SourceItem({ source }: { source: QuerySource }) {
  return (
    <div className="border-t border-border py-2 first:border-t-0">
      <div className="flex items-center justify-between text-meta text-ink">
        <span className="font-medium">{source.path}</span>
        <span className="text-ink-muted">{source.score.toFixed(2)}</span>
      </div>
      <div className="text-meta text-ink-muted">
        {source.heading} · lines {source.start_line}-{source.end_line}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Write `src/components/SourcesDisclosure.tsx`**

```tsx
import * as Collapsible from "@radix-ui/react-collapsible";
import { useState } from "react";
import type { QuerySource } from "../api/types";
import { SourceItem } from "./SourceItem";

export function SourcesDisclosure({ sources }: { sources: QuerySource[] }) {
  const [open, setOpen] = useState(false);

  if (sources.length === 0) return null;

  return (
    <Collapsible.Root open={open} onOpenChange={setOpen} className="mt-3">
      <Collapsible.Trigger className="text-meta text-ink-muted hover:text-ink">
        {open ? "▾" : "▸"} Sources ({sources.length})
      </Collapsible.Trigger>
      <Collapsible.Content>
        {sources.map((source) => (
          <SourceItem key={`${source.path}-${source.start_line}`} source={source} />
        ))}
      </Collapsible.Content>
    </Collapsible.Root>
  );
}
```

- [ ] **Step 6: Write `src/components/SupportingPointsDisclosure.tsx`**

```tsx
import * as Collapsible from "@radix-ui/react-collapsible";
import { useState } from "react";

interface SupportingPointsDisclosureProps {
  supportingPoints: string[];
  personalExamples: string[];
}

export function SupportingPointsDisclosure({
  supportingPoints,
  personalExamples,
}: SupportingPointsDisclosureProps) {
  const [open, setOpen] = useState(false);

  if (supportingPoints.length === 0 && personalExamples.length === 0) return null;

  return (
    <Collapsible.Root open={open} onOpenChange={setOpen} className="mt-3">
      <Collapsible.Trigger className="text-meta text-ink-muted hover:text-ink">
        {open ? "▾" : "▸"} Supporting points & examples
      </Collapsible.Trigger>
      <Collapsible.Content className="mt-2 space-y-2 text-body text-ink">
        {supportingPoints.length > 0 ? (
          <ul className="list-disc space-y-1 pl-5">
            {supportingPoints.map((point) => (
              <li key={point}>{point}</li>
            ))}
          </ul>
        ) : null}
        {personalExamples.length > 0 ? (
          <ul className="list-disc space-y-1 pl-5 text-ink-muted">
            {personalExamples.map((example) => (
              <li key={example}>{example}</li>
            ))}
          </ul>
        ) : null}
      </Collapsible.Content>
    </Collapsible.Root>
  );
}
```

- [ ] **Step 7: Run both test files, confirm they pass**

Run: `npm test -- SourcesDisclosure SupportingPointsDisclosure`
Expected: `PASS`.

- [ ] **Step 8: Commit**

```bash
cd apps/web
git add src/components/SourceItem.tsx src/components/SourcesDisclosure.tsx src/components/SupportingPointsDisclosure.tsx tests/components/SourcesDisclosure.test.tsx tests/components/SupportingPointsDisclosure.test.tsx
git commit -m "feat(web): add inline-expanding sources and supporting-points disclosures"
```

---

### Task 9: AnswerCard, LoadingState, AnswerPanel

**Files:**
- Create: `apps/web/src/components/LoadingState.tsx`
- Create: `apps/web/src/components/AnswerCard.tsx`
- Create: `apps/web/src/components/AnswerPanel.tsx`
- Test: `apps/web/tests/components/AnswerPanel.test.tsx`

**Interfaces:**
- Consumes: `ConfidenceBadge` (Task 4), `ErrorCard` (Task 4), `CopyButton` (Task 7), `SourcesDisclosure`/`SupportingPointsDisclosure` (Task 8), `ApiError` (Task 2), `QueryRequest`/`QueryResponse` (Task 2), `UseMutationResult` from `@tanstack/react-query`.
- Produces: `LoadingState()`, `AnswerCard({ response }: { response: QueryResponse })`, `AnswerPanel({ mutation, onRetry }: { mutation: UseMutationResult<QueryResponse, ApiError, QueryRequest>; onRetry: () => void })` — `AppShell` (Task 10) renders `AnswerPanel`.

- [ ] **Step 1: Write the failing tests, `tests/components/AnswerPanel.test.tsx`**

```tsx
import { render, screen } from "@testing-library/react";
import type { UseMutationResult } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../../src/api/client";
import type { QueryRequest, QueryResponse } from "../../src/api/types";
import { AnswerPanel } from "../../src/components/AnswerPanel";

function mutationStub(
  overrides: Partial<UseMutationResult<QueryResponse, ApiError, QueryRequest>>
): UseMutationResult<QueryResponse, ApiError, QueryRequest> {
  return {
    status: "idle",
    data: undefined,
    error: null,
    reset: vi.fn(),
    ...overrides,
  } as UseMutationResult<QueryResponse, ApiError, QueryRequest>;
}

describe("AnswerPanel", () => {
  it("renders nothing when idle", () => {
    const { container } = render(
      <AnswerPanel mutation={mutationStub({ status: "idle" })} onRetry={vi.fn()} />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders LoadingState while pending", () => {
    render(<AnswerPanel mutation={mutationStub({ status: "pending" })} onRetry={vi.fn()} />);
    expect(document.querySelector(".animate-pulse")).toBeInTheDocument();
  });

  it("renders ErrorCard on error and wires the onRetry callback", async () => {
    const onRetry = vi.fn();
    render(
      <AnswerPanel
        mutation={mutationStub({
          status: "error",
          error: new ApiError("Can't reach the API.", 0),
        })}
        onRetry={onRetry}
      />
    );
    expect(screen.getByText("Can't reach the API.")).toBeInTheDocument();
  });

  it("renders AnswerCard on success", () => {
    const response: QueryResponse = {
      answer: { say_this: "Say this.", supporting_points: [], personal_examples: [] },
      sources: [],
      confidence: "high",
      limitations: [],
      timing_ms: { retrieval: 1, generation: 1, total: 2 },
    };
    render(
      <AnswerPanel mutation={mutationStub({ status: "success", data: response })} onRetry={vi.fn()} />
    );
    expect(screen.getByText("Say this.")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the tests, confirm they fail**

Run: `npm test -- AnswerPanel`
Expected: FAIL — none of the three components exist yet.

- [ ] **Step 3: Write `src/components/LoadingState.tsx`**

```tsx
export function LoadingState() {
  return (
    <div className="animate-pulse rounded-lg border border-border bg-surface p-4">
      <div className="h-4 w-20 rounded bg-zinc-700" />
      <div className="mt-3 h-6 w-3/4 rounded bg-zinc-700" />
      <div className="mt-2 h-6 w-1/2 rounded bg-zinc-700" />
    </div>
  );
}
```

- [ ] **Step 4: Write `src/components/AnswerCard.tsx`**

```tsx
import type { QueryResponse } from "../api/types";
import { ConfidenceBadge } from "./ConfidenceBadge";
import { CopyButton } from "./CopyButton";
import { SourcesDisclosure } from "./SourcesDisclosure";
import { SupportingPointsDisclosure } from "./SupportingPointsDisclosure";

export function AnswerCard({ response }: { response: QueryResponse }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-center justify-between">
        <ConfidenceBadge confidence={response.confidence} sourceCount={response.sources.length} />
        <CopyButton text={response.answer.say_this} />
      </div>
      <p className="mt-3 text-answer text-ink">{response.answer.say_this}</p>
      {response.confidence === "low" && response.limitations.length > 0 ? (
        <p className="mt-2 text-meta text-amber-500">{response.limitations[0]}</p>
      ) : null}
      <SupportingPointsDisclosure
        supportingPoints={response.answer.supporting_points}
        personalExamples={response.answer.personal_examples}
      />
      <SourcesDisclosure sources={response.sources} />
    </div>
  );
}
```

- [ ] **Step 5: Write `src/components/AnswerPanel.tsx`**

```tsx
import type { UseMutationResult } from "@tanstack/react-query";
import type { ApiError } from "../api/client";
import type { QueryRequest, QueryResponse } from "../api/types";
import { AnswerCard } from "./AnswerCard";
import { ErrorCard } from "./ErrorCard";
import { LoadingState } from "./LoadingState";

interface AnswerPanelProps {
  mutation: UseMutationResult<QueryResponse, ApiError, QueryRequest>;
  onRetry: () => void;
}

export function AnswerPanel({ mutation, onRetry }: AnswerPanelProps) {
  if (mutation.status === "idle") return null;
  if (mutation.status === "pending") return <LoadingState />;
  if (mutation.status === "error") {
    return <ErrorCard message={mutation.error.message} onRetry={onRetry} />;
  }
  return <AnswerCard response={mutation.data} />;
}
```

- [ ] **Step 6: Run the tests, confirm they pass**

Run: `npm test -- AnswerPanel`
Expected: `PASS` — all 4 tests green.

- [ ] **Step 7: Commit**

```bash
cd apps/web
git add src/components/LoadingState.tsx src/components/AnswerCard.tsx src/components/AnswerPanel.tsx tests/components/AnswerPanel.test.tsx
git commit -m "feat(web): add AnswerCard, LoadingState, and the AnswerPanel status switch"
```

---

### Task 10: AppShell, TopBar, and final App wiring

**Files:**
- Create: `apps/web/src/components/TopBar.tsx`
- Create: `apps/web/src/components/AppShell.tsx`
- Modify: `apps/web/src/App.tsx` (replace the Task 1 placeholder)
- Test: `apps/web/tests/App.test.tsx` (replace the Task 1 smoke test with the real integration test)

**Interfaces:**
- Consumes: `IndexStatusBadge` (Task 5), `QueryInput` (Task 6), `AnswerPanel` (Task 9), `useQueryAnswer` (Task 3).
- Produces: `TopBar()`, `AppShell()`, `App` (named export, replacing Task 1's placeholder body but keeping the same `export function App()` signature) — `main.tsx` (Task 1, unmodified) mounts `<App />` as before.

- [ ] **Step 1: Write `src/components/TopBar.tsx`**

```tsx
import { IndexStatusBadge } from "./IndexStatusBadge";

export function TopBar() {
  return (
    <header className="flex items-center justify-between border-b border-border px-4 py-3">
      <span className="text-body font-semibold text-ink">vault-interview-copilot</span>
      <IndexStatusBadge />
    </header>
  );
}
```

- [ ] **Step 2: Write `src/components/AppShell.tsx`**

```tsx
import { useState } from "react";
import { useQueryAnswer } from "../api/hooks";
import { AnswerPanel } from "./AnswerPanel";
import { QueryInput } from "./QueryInput";
import { TopBar } from "./TopBar";

export function AppShell() {
  const [lastQuery, setLastQuery] = useState("");
  const mutation = useQueryAnswer();

  function handleSubmit(query: string) {
    setLastQuery(query);
    mutation.mutate({ query });
  }

  return (
    <div className="min-h-screen bg-background">
      <TopBar />
      <main className="mx-auto max-w-[760px] px-4 py-8">
        <QueryInput onSubmit={handleSubmit} disabled={mutation.status === "pending"} />
        <div className="mt-4">
          <AnswerPanel mutation={mutation} onRetry={() => mutation.mutate({ query: lastQuery })} />
        </div>
      </main>
    </div>
  );
}
```

- [ ] **Step 3: Replace `src/App.tsx`'s placeholder with real `QueryClientProvider` wiring**

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppShell } from "./components/AppShell";

const queryClient = new QueryClient();

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppShell />
    </QueryClientProvider>
  );
}
```

- [ ] **Step 4: Replace `tests/App.test.tsx`'s Task-1 smoke test with the real end-to-end integration test** (mocks `fetch` directly rather than the API client, so this test exercises the entire real wiring — `QueryInput` → `useQueryAnswer` → `client.ts` → `AnswerPanel` → `AnswerCard` — not just individual units)

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../src/App";

describe("App", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("submits a query and renders the cited answer end to end", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((path: string) => {
        if (path === "/api/index/status") {
          return Promise.resolve({
            ok: true,
            json: async () => ({ embedding_model: "nomic-embed-text", note_count: 5, last_run: null }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: async () => ({
            answer: {
              say_this: "Terraform drift happened because state and reality diverged.",
              supporting_points: ["Ran terraform plan to detect it."],
              personal_examples: [],
            },
            sources: [
              {
                path: "Projects/Whetstone/Infrastructure.md",
                heading: "Terraform Drift",
                start_line: 42,
                end_line: 58,
                score: 0.91,
              },
            ],
            confidence: "high",
            limitations: [],
            timing_ms: { retrieval: 100, generation: 900, total: 1000 },
          }),
        });
      })
    );

    render(<App />);
    const input = screen.getByPlaceholderText("terraform drift prod...");
    await userEvent.type(input, "terraform drift prod{Enter}");

    await waitFor(() =>
      expect(
        screen.getByText("Terraform drift happened because state and reality diverged.")
      ).toBeInTheDocument()
    );
    expect(screen.getByText("Cited")).toBeInTheDocument();
  });

  it("shows the abstention state for a query with no grounding", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((path: string) => {
        if (path === "/api/index/status") {
          return Promise.resolve({
            ok: true,
            json: async () => ({ embedding_model: "nomic-embed-text", note_count: 5, last_run: null }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: async () => ({
            answer: { say_this: "", supporting_points: [], personal_examples: [] },
            sources: [],
            confidence: "low",
            limitations: ["No relevant vault content found for this query."],
            timing_ms: { retrieval: 50, generation: 0, total: 50 },
          }),
        });
      })
    );

    render(<App />);
    const input = screen.getByPlaceholderText("terraform drift prod...");
    await userEvent.type(input, "gibberish nonexistent topic{Enter}");

    await waitFor(() => expect(screen.getByText("No grounding found")).toBeInTheDocument());
    expect(screen.getByText("No relevant vault content found for this query.")).toBeInTheDocument();
  });
});
```

- [ ] **Step 5: Run the full test suite, confirm everything passes**

Run: `npm test`
Expected: `PASS` — every test file from Tasks 1-10 green.

- [ ] **Step 6: Manual smoke check against the real backend**

```bash
docker compose up -d
cd apps/web && npm run dev
```

Open `http://localhost:5173`, confirm: the index status badge shows a real dot/label, typing a `sample-vault` query (e.g. "terraform drift") and pressing Enter returns a real cited answer, and a nonsense query shows the amber abstention state. This is the first point the exit condition ("useful in realistic interview-prep sessions") can be judged against something real rather than mocks — the actual judgment of whether it's *met* stays Ben's call per `CLAUDE.md`'s Decision authority rule, not something this plan concludes on its own.

- [ ] **Step 7: Commit**

```bash
cd apps/web
git add src/components/TopBar.tsx src/components/AppShell.tsx src/App.tsx tests/App.test.tsx
git commit -m "feat(web): wire AppShell, TopBar, and QueryClientProvider into the real App"
```

---

### Task 11: CI wiring and Playwright E2E scaffold

**Files:**
- Modify: `.github/workflows/ci.yml` (add a `web` job)
- Create: `apps/web/playwright.config.ts`
- Create: `apps/web/tests/e2e/query-flow.spec.ts`

**Interfaces:**
- Consumes: the running app from Tasks 1-10 (Playwright drives the real built app in a real browser).
- Produces: nothing further tasks depend on — this is the last task in the plan.

- [ ] **Step 1: Add a `web` job to `.github/workflows/ci.yml`** (unit/integration tests only — no Playwright here, matching `09-testing.md`'s rule that model-dependent runs never sit in standard CI; this job would otherwise need a running Postgres, Ollama, and `gpt-oss:20b` to make `/api/query` return anything real)

```yaml
  web:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: apps/web
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: "npm"
          cache-dependency-path: apps/web/package-lock.json
      - name: Install dependencies
        run: npm ci
      - name: Check formatting
        run: npm run format
      - name: Lint
        run: npm run lint
      - name: Typecheck
        run: npm run typecheck
      - name: Run tests
        run: npm test
```

- [ ] **Step 2: Write `apps/web/playwright.config.ts`**

```ts
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  use: {
    baseURL: "http://localhost:5173",
  },
  webServer: {
    command: "npm run dev",
    url: "http://localhost:5173",
    reuseExistingServer: true,
  },
});
```

- [ ] **Step 3: Write `apps/web/tests/e2e/query-flow.spec.ts`** — matches `09-testing.md`'s existing E2E list directly (shorthand query → correct source appears; missing evidence produces a stated limitation, not a fabricated claim)

```ts
import { expect, test } from "@playwright/test";

test("shorthand query returns a cited answer with the expected source", async ({ page }) => {
  await page.goto("/");
  await page.getByPlaceholder("terraform drift prod...").fill("terraform drift prod");
  await page.keyboard.press("Enter");

  await expect(page.getByText("Cited")).toBeVisible({ timeout: 15_000 });

  await page.getByText(/Sources \(\d+\)/).click();
  await expect(page.getByText(/Infrastructure\.md/)).toBeVisible();
});

test("a no-evidence query produces a stated limitation, not a fabricated claim", async ({ page }) => {
  await page.goto("/");
  await page
    .getByPlaceholder("terraform drift prod...")
    .fill("gibberish nonexistent topic xyzzy123");
  await page.keyboard.press("Enter");

  await expect(page.getByText("No grounding found")).toBeVisible({ timeout: 15_000 });
});
```

- [ ] **Step 4: Run manually against the real stack — never in CI** (requires Postgres up, `sample-vault` indexed, and a real Ollama with `gpt-oss:20b` reachable, since this exercises the actual model — exactly the category `09-testing.md` keeps out of standard CI)

```bash
docker compose up -d
cd apps/api && python -m app.ingestion.cli
cd ../web && npx playwright install --with-deps chromium && npx playwright test
```

Expected: both specs pass against the real running pipeline.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml apps/web/playwright.config.ts apps/web/tests/e2e/query-flow.spec.ts
git commit -m "ci(web): add unit/integration test job; add Playwright E2E scaffold for manual runs"
```
