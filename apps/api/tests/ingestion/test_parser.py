from app.ingestion.parser import parse_note

FRONTMATTER_NOTE = """---
title: Terraform Fundamentals
tags: [terraform, iac]
aliases: [tf-fundamentals]
---

# Terraform Fundamentals

## State Management

### Drift Management

State drift happens when real infra diverges from the state file.

```hcl
resource "aws_instance" "example" {
  ami = "ami-123456"
}
```

See [[Meridian-Tool-Stack-Articulation]] and [Terraform docs](https://terraform.io).
"""


def test_parses_frontmatter_fields():
    parsed = parse_note(FRONTMATTER_NOTE, fallback_title="fallback.md")
    assert parsed.title == "Terraform Fundamentals"
    assert parsed.tags == ["terraform", "iac"]
    assert parsed.aliases == ["tf-fundamentals"]


def test_builds_heading_ancestry():
    parsed = parse_note(FRONTMATTER_NOTE, fallback_title="fallback.md")
    heading_paths = [s.heading_path for s in parsed.sections]
    assert "Terraform Fundamentals > State Management > Drift Management" in heading_paths


def test_code_block_is_captured_within_its_section():
    parsed = parse_note(FRONTMATTER_NOTE, fallback_title="fallback.md")
    drift_section = next(
        s for s in parsed.sections if s.heading_path and s.heading_path.endswith("Drift Management")
    )
    assert drift_section.code_block_ranges, "expected the hcl fence to be captured"
    start, end = drift_section.code_block_ranges[0]
    fenced_text = "\n".join(FRONTMATTER_NOTE.splitlines()[start - 1 : end])
    assert 'resource "aws_instance"' in fenced_text


def test_extracts_wikilinks_and_markdown_links():
    parsed = parse_note(FRONTMATTER_NOTE, fallback_title="fallback.md")
    wikilinks = [link for link in parsed.links if link.link_type == "wikilink"]
    mdlinks = [link for link in parsed.links if link.link_type == "markdown"]
    assert wikilinks[0].target == "Meridian-Tool-Stack-Articulation"
    assert mdlinks[0].target == "https://terraform.io"


def test_note_without_headings_becomes_single_section():
    parsed = parse_note("Just a quick capture, no structure yet.\n", fallback_title="Quick-Note.md")
    assert len(parsed.sections) == 1
    assert parsed.sections[0].heading_path is None


def test_title_falls_back_to_first_heading_then_filename():
    parsed = parse_note("# My Heading\n\nBody\n", fallback_title="fallback.md")
    assert parsed.title == "My Heading"
    parsed_no_heading = parse_note("Body only\n", fallback_title="fallback.md")
    assert parsed_no_heading.title == "fallback.md"


def test_heading_inside_code_block_is_not_treated_as_a_heading():
    note = "# Real Heading\n\n```text\n# not a heading\n```\n\nBody after.\n"
    parsed = parse_note(note, fallback_title="fallback.md")
    heading_paths = {s.heading_path for s in parsed.sections}
    assert heading_paths == {"Real Heading"}


def test_section_content_includes_heading_line():
    parsed = parse_note(FRONTMATTER_NOTE, fallback_title="fallback.md")
    state_mgmt_section = next(
        s for s in parsed.sections if s.heading_path and s.heading_path.endswith("State Management")
    )
    assert state_mgmt_section.content.startswith("## State Management")
