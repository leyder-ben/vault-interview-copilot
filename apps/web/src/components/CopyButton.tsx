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
