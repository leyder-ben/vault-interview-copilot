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
