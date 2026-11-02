from pathlib import Path

from scripts.dataset import load_dataset

DATASET = Path(__file__).parent.parent / "eval" / "dataset.yaml"


def test_dataset_is_valid_and_has_both_kinds_of_questions():
    questions = load_dataset(DATASET)
    assert len(questions) > 0
    assert any(q.should_refuse for q in questions)
    assert any(not q.should_refuse for q in questions)