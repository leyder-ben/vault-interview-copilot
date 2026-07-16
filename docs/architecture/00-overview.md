# Overview — Goals, Non-Goals, Priorities

## What V1 does

User types a short, shorthand query:

```text
terraform drift prod
helm scaling
jenkins oidc secrets
why use staging
blue green explanation
```

App returns:

1. **Say this** — concise first-person answer, suitable for speaking out loud.
2. **Supporting points** — additional detail the user can expand on.
3. **Personal examples** — relevant real projects/incidents from the vault.
4. **Sources** — exact vault notes, headings, and line ranges.
5. **Confidence and limitations** — explicit when the vault doesn't support a personal claim.

## V2 (later, separate effort — do not build now)

Adds audio capture, speech-to-text, transcript buffering, and question-boundary detection. Must reuse the V1 retrieval/generation pipeline as-is, not a separate answer system.

## Goals

- Retrieve correct notes from terse, imperfect queries.
- Produce concise, speakable, first-person answers.
- Cite exact source material.
- Avoid unsupported claims about personal experience.
- Local operation, private vault access only.
- Model/embedding providers replaceable independently.
- Incremental indexing (changed/renamed/deleted notes).
- Measurable retrieval and answer-quality benchmarks.
- Portfolio-quality repo with clear architectural reasoning.

## Non-goals for V1 (see CLAUDE.md for the enforced list)

Continuous audio capture, Electron/desktop overlay, screen-capture concealment, multi-user SaaS, Kubernetes, microservice decomposition, multi-agent orchestration, custom model training, cloud-hosting the real vault, general Obsidian replacement.

## Performance priorities, in order

1. Retrieval accuracy
2. Grounded personal claims
3. Shorthand tolerance
4. End-to-end latency
5. Incremental indexing
6. Speakability
7. Visual polish

If a tradeoff has to be made between two of these, the higher one wins. Visual polish never wins against retrieval accuracy.

## Architectural principles (expanded)

- **Modular monolith first** — one backend app, clear internal module boundaries. Simple to build and debug; boundaries can become real service seams later if measurement justifies it.
- **Retrieval before generation** — the most important question is whether the correct evidence was retrieved at all. A polished answer from the wrong context is still a failure.
- **The vault is the authority** — general technical explanation may use model knowledge; claims about personal actions/projects/outcomes must be grounded in retrieved vault content.
- **Providers are replaceable** — embedding, reranking, STT, and generation providers sit behind narrow interfaces. Never hard-couple to Ollama/OpenAI/Anthropic/Gemini or one embedding model.
- **V2 is a new input path** — voice feeds the same query pipeline; it must not require rebuilding retrieval.
- **Measure before adding complexity** — start with exact vector search, no reranker. Add approximate indexes, reranking, caching, or background workers only when evaluation shows a real bottleneck.

## Reference public repos (context only, not to be copied)

shubhamshnd/Open-Cluely, elias-soykat/interview-copilot, FarzamHejaziK/AnswerCue, hi2brain/second-brain, royisme/pikabaka, AhsanRiaz786/clutch-ai. Reviewed for architectural patterns during design. Not a dependency, not a source to pull code from — license unreviewed, and the design here was made independently.
