import type { IndexStatusResponse, QueryRequest, QueryResponse } from "./types";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function extractDetailMessage(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) =>
        item && typeof item === "object" && "msg" in item
          ? String((item as { msg: unknown }).msg)
          : null
      )
      .filter((msg): msg is string => msg !== null);
    return messages.length > 0 ? messages.join("; ") : null;
  }
  return null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, init);
  } catch {
    throw new ApiError("Can't reach the API.", 0);
  }

  if (!response.ok) {
    if (response.status >= 400 && response.status < 500) {
      const contentType = response.headers.get("content-type") ?? "";
      if (contentType.includes("application/json")) {
        try {
          const body = (await response.json()) as { detail?: unknown };
          const detailMessage = extractDetailMessage(body.detail);
          if (detailMessage !== null) {
            throw new ApiError(detailMessage, response.status);
          }
        } catch (err) {
          if (err instanceof ApiError) throw err;
          // JSON parsing failed -- fall through to the generic message below.
        }
      }
    }
    throw new ApiError("Something went wrong generating an answer.", response.status);
  }

  return (await response.json()) as T;
}

export function postQuery(payload: QueryRequest): Promise<QueryResponse> {
  return request<QueryResponse>("/api/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function getIndexStatus(): Promise<IndexStatusResponse> {
  return request<IndexStatusResponse>("/api/index/status");
}
