import { useState } from "react";
import { useQueryAnswer } from "../api/hooks";
import { AnswerPanel } from "./AnswerPanel";
import { QueryInput } from "./QueryInput";
import { TopBar } from "./TopBar";

export function AppShell() {
  const [lastQuery, setLastQuery] = useState("");
  const mutation = useQueryAnswer();

  function handleSubmit(query: string) {
    setLastQuery(query);
    mutation.mutate({ query });
  }

  return (
    <div className="min-h-screen bg-background">
      <TopBar />
      <main className="mx-auto max-w-[760px] px-4 py-8">
        <QueryInput onSubmit={handleSubmit} disabled={mutation.status === "pending"} />
        <div className="mt-4">
          <AnswerPanel mutation={mutation} onRetry={() => mutation.mutate({ query: lastQuery })} />
        </div>
      </main>
    </div>
  );
}
