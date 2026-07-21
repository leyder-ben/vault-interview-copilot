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
