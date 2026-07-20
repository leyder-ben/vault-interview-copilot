export type Confidence = "high" | "medium" | "low";

export interface QuerySource {
  path: string;
  heading: string | null;
  start_line: number;
  end_line: number;
  score: number;
}

export interface PersonalExample {
  project: string;
  example: string;
  source_chunk_ids: number[];
}

export interface QueryAnswer {
  say_this: string;
  supporting_points: string[];
  personal_examples: PersonalExample[];
}

export interface QueryResponse {
  answer: QueryAnswer;
  sources: QuerySource[];
  confidence: Confidence;
  limitations: string[];
  timing_ms: {
    retrieval: number;
    generation: number;
    total: number;
  };
}

export interface QueryRequest {
  query: string;
  mode?: string;
  max_sources?: number;
}

export interface IndexRunSummary {
  status: "success" | "failed";
  started_at: string;
  completed_at: string | null;
  files_scanned: number;
  files_added: number;
  files_updated: number;
  files_deleted: number;
  errors: Record<string, unknown> | null;
}

export interface IndexStatusResponse {
  embedding_model: string;
  note_count: number;
  last_run: IndexRunSummary | null;
}
