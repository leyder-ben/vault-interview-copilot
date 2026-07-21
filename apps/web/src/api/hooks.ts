import { useMutation, useQuery } from "@tanstack/react-query";
import type { ApiError } from "./client";
import { getIndexStatus, postQuery } from "./client";
import type { IndexStatusResponse, QueryRequest, QueryResponse } from "./types";

export function useQueryAnswer() {
  return useMutation<QueryResponse, ApiError, QueryRequest>({
    mutationFn: (payload) => postQuery(payload),
  });
}

export function useIndexStatus() {
  return useQuery<IndexStatusResponse, ApiError>({
    queryKey: ["index-status"],
    queryFn: getIndexStatus,
    refetchInterval: 120_000,
  });
}
