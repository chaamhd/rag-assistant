from app.chunking import MAX_CHARS, chunk_document, clean_markdown


def test_front_matter_removed():
    assert clean_markdown("---\ntitle: x\n---\n# Hello\ntext").startswith("# Hello")


def test_hash_in_code_block_is_not_a_heading():
    doc = "# Title\n\nIntro " + "a" * 120 + "\n\n```bash\n# a comment\nuv run x\n```\n"
    chunks = chunk_document("a.md", doc)
    assert chunks
    assert all(c.section == "Title" for c in chunks)


def test_chunks_respect_max_size():
    doc = "# T\n\n" + "\n\n".join(["word " * 60 for _ in range(30)])
    chunks = chunk_document("a.md", doc)
    assert len(chunks) > 1
    assert all(len(c.text) <= MAX_CHARS for c in chunks)