export function LoadingState() {
  return (
    <div className="animate-pulse rounded-lg border border-border bg-surface p-4">
      <div className="h-4 w-20 rounded bg-zinc-700" />
      <div className="mt-3 h-6 w-3/4 rounded bg-zinc-700" />
      <div className="mt-2 h-6 w-1/2 rounded bg-zinc-700" />
    </div>
  );
}
