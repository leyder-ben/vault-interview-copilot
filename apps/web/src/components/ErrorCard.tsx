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
