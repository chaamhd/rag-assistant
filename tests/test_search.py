from app.search import SearchResult, rrf_fuse, to_or_query


def make(id: str) -> SearchResult:
    return SearchResult(id, "a.md", "Titre", "Section", "texte", 0.5)


def test_to_or_query_relie_les_mots():
    assert to_or_query("How do I pin Python?") == "How or do or I or pin or Python"


def test_to_or_query_ignore_le_mot_or_et_la_ponctuation():
    assert "or or" not in to_or_query("x or y")
    assert to_or_query("???") == ""


def test_rrf_favorise_les_passages_presents_dans_les_deux_listes():
    a, b, c = make("a"), make("b"), make("c")
    fused = rrf_fuse([[a, b], [c, b]], rrf_k=60)
    assert [r.id for r in fused] == ["b", "a", "c"]