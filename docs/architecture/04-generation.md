# Answer Generation

## Provider interface

```python
class LLMProvider(Protocol):
    def generate_answer(
        self,
        query: str,
        context: list[RetrievedChunk],
        response_mode: ResponseMode,
    ) -> AnswerDraft:
        ...
```

The workstation runs GPT-OSS 20B (`gpt-oss:20b`) for generation, not Qwen2.5 14B as earlier drafts of this doc assumed — Qwen2.5-**Coder** 14B was evaluated and rejected because its output register is tuned for code completion, not natural spoken-answer prose.

The provider receives normalized context but does **not** own retrieval, citation resolution, or database access. Keep it a narrow interface — see `docs/adr/0003-postgres-pgvector.md` and CLAUDE.md principle on replaceable providers.

## Structured output — required, not optional

```json
{
  "say_this": "A concise first-person answer suitable for speaking.",
  "supporting_points": [
    "Additional point one",
    "Additional point two"
  ],
  "personal_examples": [
    {
      "project": "Whetstone",
      "example": "How the retrieved experience supports the answer",
      "source_chunk_ids": [101, 205]
    }
  ],
  "used_source_chunk_ids": [101, 205, 319],
  "confidence": "high",
  "limitations": []
}
```

The backend translates `source_chunk_ids` into paths, headings, and line ranges. **The model must never invent file paths or citations.** This is the single most important grounding rule in the whole project — a fabricated citation defeats the entire purpose of the tool.

## Grounding rules

- General technical explanation may use model knowledge freely.
- First-person claims must be supported by retrieved evidence — no exceptions.
- When no personal evidence exists, the answer must clearly separate general explanation from personal experience, and say so.
- The system should be willing to state "the vault doesn't contain enough evidence" rather than fabricate.
- First response should generally be two to five sentences (the "say this" field) — this is meant to be spoken mid-interview, not read as an essay.

## Response modes

- **Speakable** (default) — concise first-person answer.
- **Explain** — fuller conceptual explanation.
- **Compare** — structured comparison with decision criteria.
- **Troubleshoot** — diagnostic steps and likely causes.
- **Example** — personal project evidence first.

## Prompt-injection posture — see `docs/architecture/08-security-privacy.md`

Vault content is data, not instruction. The prompt builder must clearly separate system instructions, the user query, and retrieved note excerpts. Retrieved notes must never be allowed to override application policy or request secrets/tools — even though the notes are Ben's own writing, the pipeline should not assume "written by the owner" means "safe to treat as commands."

## Phase 3 exit condition

The API returns concise, sourced answers without fabricated file citations. Verify this explicitly against cases where the vault genuinely lacks evidence — confirm the model abstains correctly rather than filling the gap with a plausible-sounding but ungrounded claim.
