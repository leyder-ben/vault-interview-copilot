import * as HoverCard from "@radix-ui/react-hover-card";
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
    <HoverCard.Root onOpenChange={(open) => open && refetch()}>
      <HoverCard.Trigger asChild>
        <button
          type="button"
          className="inline-flex items-center gap-2 rounded-full border border-border px-2.5 py-1 text-meta text-ink-muted hover:text-ink"
        >
          <span className={`h-2 w-2 rounded-full ${DOT_CLASS[variant]}`} aria-hidden="true" />
          {label}
        </button>
      </HoverCard.Trigger>
      <HoverCard.Portal>
        <HoverCard.Content
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
        </HoverCard.Content>
      </HoverCard.Portal>
    </HoverCard.Root>
  );
}
