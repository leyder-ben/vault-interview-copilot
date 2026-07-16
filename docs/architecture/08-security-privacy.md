# Privacy, Security, and Prompt-Injection Posture

## Core requirements

- Mount the real vault **read-only** into the API container. Never write to it.
- Keep the real vault and the generated vector database out of Git.
- Provide a sanitized `sample-vault/` for demos, tests, and evaluation.
- Store provider credentials in environment variables or a local secret store — never hardcoded.
- Never return arbitrary file paths from user-controlled input (see `GET /api/source` in `05-api-surface.md` — resolve strictly through the database, not a raw filesystem read).
- Don't expose the API beyond localhost by default.
- Add authentication before any remote access through Tailscale or the public internet — not needed for local-only V1, but don't accidentally open this up without it.
- Query logging is optional to disable (purge path / `--no-log` flag) even though it's on by default.
- Document which providers receive note excerpts — right now that's Ollama, running locally. If a hosted provider (OpenAI/Anthropic) adapter is ever added, that's a real decision point, not a silent default.

## Threats to address

- Accidental publication of personal vault content (this is why the real vault and vector DB are gitignored, not just "shouldn't be committed").
- Prompt injection contained inside notes.
- Malicious or malformed Markdown files during ingestion.
- Overly broad source-file endpoints.
- API exposure on the local network beyond intended reach.
- Secret leakage in logs or error traces.
- Hosted model requests containing sensitive personal content (not a concern yet — no hosted provider in V1).

## Prompt-injection position

Vault content is data, not instruction. The prompt builder must clearly separate system instructions, the user query, and retrieved note excerpts. Retrieved notes must not be allowed to override application policy or request secrets/tools — see `04-generation.md`. This matters even though Ben wrote every note himself: the pipeline shouldn't assume "I wrote it" implies "safe to treat as a command."
