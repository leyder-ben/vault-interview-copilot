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
