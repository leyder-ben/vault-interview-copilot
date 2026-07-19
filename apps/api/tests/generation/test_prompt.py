from app.generation.prompt import build_prompt
from app.retrieval.context import RetrievedChunk


def test_build_prompt_returns_system_and_user_messages():
    messages = build_prompt("terraform drift prod", [])
    roles = [m["role"] for m in messages]
    assert roles == ["system", "user"]
    assert messages[1]["content"] == "terraform drift prod"


def test_build_prompt_includes_chunk_id_path_and_content_in_system_message():
    context = [
        RetrievedChunk(
            chunk_id=101,
            vault_path="Whetstone/Infrastructure.md",
            heading_path="Terraform Drift",
            content="Drift was caused by a manual console change during an incident.",
            rrf_score=0.05,
        )
    ]
    messages = build_prompt("terraform drift", context)
    system_content = messages[0]["content"]
    assert "chunk_id=101" in system_content
    assert "Whetstone/Infrastructure.md" in system_content
    assert "Terraform Drift" in system_content
    assert "Drift was caused by a manual console change" in system_content


def test_build_prompt_with_no_context_states_none_available():
    messages = build_prompt("some obscure query", [])
    assert "No retrieved context is available" in messages[0]["content"]


def test_build_prompt_instructs_grounding_and_data_not_instruction_stance():
    messages = build_prompt("terraform drift", [])
    system_content = messages[0]["content"]
    assert "not instructions" in system_content or "not instruction" in system_content
    assert "chunk" in system_content.lower()


def test_build_prompt_handles_chunk_with_no_heading():
    context = [
        RetrievedChunk(
            chunk_id=42,
            vault_path="Inbox/Note.md",
            heading_path=None,
            content="raw capture",
            rrf_score=0.02,
        )
    ]
    messages = build_prompt("query", context)
    assert "chunk_id=42" in messages[0]["content"]
    assert "(no heading)" in messages[0]["content"]
