import { IndexStatusBadge } from "./IndexStatusBadge";

export function TopBar() {
  return (
    <header className="flex items-center justify-between border-b border-border px-4 py-3">
      <span className="text-body font-semibold text-ink">vault-interview-copilot</span>
      <IndexStatusBadge />
    </header>
  );
}
