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
