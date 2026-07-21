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
