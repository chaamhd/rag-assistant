from app import rerank as rerank_module
from app.search import SearchResult


def make(id: str, text: str) -> SearchResult:
    return SearchResult(id, "a.md", "Titre", "Section", text, 0.5)


class FakeModel:
    """Fausse notation : plus le texte est long, plus la note est haute."""

    def rerank(self, question, documents):
        return [float(len(document)) for document in documents]


def test_rerank_ordonne_les_candidats_par_note_decroissante(monkeypatch):
    monkeypatch.setattr(rerank_module, "_model", lambda: FakeModel())
    court, long, moyen = make("court", "a"), make("long", "aaaa"), make("moyen", "aa")
    result = rerank_module.rerank("question", [court, long, moyen])
    assert [r.id for r in result] == ["long", "moyen", "court"]


def test_rerank_sans_candidat_retourne_une_liste_vide():
    assert rerank_module.rerank("question", []) == []