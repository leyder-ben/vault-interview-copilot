import type { QueryResponse } from "../api/types";
import { ConfidenceBadge } from "./ConfidenceBadge";
import { CopyButton } from "./CopyButton";
import { SourcesDisclosure } from "./SourcesDisclosure";
import { SupportingPointsDisclosure } from "./SupportingPointsDisclosure";

export function AnswerCard({ response }: { response: QueryResponse }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-center justify-between">
        <ConfidenceBadge confidence={response.confidence} sourceCount={response.sources.length} />
        <CopyButton text={response.answer.say_this} />
      </div>
      {response.confidence === "low" && response.limitations.length > 0 ? (
        <p className="mt-1.5 text-meta text-amber-500">{response.limitations[0]}</p>
      ) : null}
      <p className="mt-3 text-answer text-ink">{response.answer.say_this}</p>
      <SupportingPointsDisclosure
        supportingPoints={response.answer.supporting_points}
        personalExamples={response.answer.personal_examples}
      />
      <SourcesDisclosure sources={response.sources} />
    </div>
  );
}
