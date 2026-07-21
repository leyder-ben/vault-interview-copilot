import type { UseMutationResult } from "@tanstack/react-query";
import type { ApiError } from "../api/client";
import type { QueryRequest, QueryResponse } from "../api/types";
import { AnswerCard } from "./AnswerCard";
import { ErrorCard } from "./ErrorCard";
import { LoadingState } from "./LoadingState";

interface AnswerPanelProps {
  mutation: UseMutationResult<QueryResponse, ApiError, QueryRequest>;
  onRetry: () => void;
}

export function AnswerPanel({ mutation, onRetry }: AnswerPanelProps) {
  if (mutation.status === "idle") return null;
  if (mutation.status === "pending") return <LoadingState />;
  if (mutation.status === "error") {
    return <ErrorCard message={mutation.error.message} onRetry={onRetry} />;
  }
  return <AnswerCard response={mutation.data} />;
}
