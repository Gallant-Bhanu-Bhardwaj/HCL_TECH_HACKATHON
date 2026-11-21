"""Checks rules search on the real documents: citations, dates, newer circulars, live ingest.
Run: python -m pytest -q      (keyword search only, so it is fast and needs no model download)"""
import shutil
import subprocess
import sys

import numpy as np
import pytest

from app import rag

TODAY = "2026-12-03"           # the data kit's reference date


@pytest.fixture(autouse=True)
def fresh(tmp_path):
    subprocess.run([sys.executable, "init_db.py"], check=True, capture_output=True)
    shutil.copytree("data/docs", tmp_path / "docs")        # ingest writes here, not into data/docs
    rag.DOCS_DIR, rag.EMBED_MODEL = tmp_path / "docs", ""
    rag.INDEX.update(embedder=None, vectors=None)
    rag.load_docs()


def ids(results):
    return [r["doc_id"] for r in results]


def test_all_documents_loaded():
    assert len({c["doc_id"] for c in rag.CHUNKS}) == 38


def test_pet_question_cites_luggage_rule():
    results = rag.search("Can I bring my pet dog on the train?", as_of=TODAY)
    assert {"RUL-LUG-01", "FAQ-17"} & set(ids(results))
    assert all(r["section"] for r in results)                 # every result can be cited


def test_newer_circular_wins_today():
    found = ids(rag.search("2AC cancellation charge 48 hours before departure", as_of=TODAY))
    assert "RUL-CAN-01" in found and "CIR-2026-07" in found
    assert "CIR-2026-11" not in found                          # not in force until 10 Dec
    assert "FAQ-07" not in found                               # outdated FAQ


def test_future_circular_after_its_date():
    found = ids(rag.search("2AC cancellation charge 48 hours before departure", as_of="2026-12-10"))
    assert "CIR-2026-11" in found and "CIR-2026-07" not in found and "FAQ-07" not in found


def test_old_faq_still_valid_before_the_circular():
    found = ids(rag.search("What is the cancellation charge for 2AC if I cancel more than 2 days early",
                           as_of="2026-11-01"))
    assert "FAQ-07" in found and "CIR-2026-07" not in found


def test_expired_circular_is_skipped():
    assert "CIR-2026-02" not in ids(rag.search("monsoon luggage reminder", as_of=TODAY))
    assert "CIR-2026-02" in ids(rag.search("monsoon luggage reminder", as_of="2026-07-15"))


def test_rule_shows_revision_note():
    rule = [r for r in rag.search("2AC cancellation charge", as_of=TODAY) if r["doc_id"] == "RUL-CAN-01"][0]
    assert "CIR-2026-07" in rule["note"]


def test_hindi_question():
    assert "CIR-2026-03" in ids(rag.search("प्रतीक्षा सूची RAC", as_of=TODAY))


def test_nothing_found_for_off_topic():
    assert rag.search("best pizza in Delhi", as_of=TODAY) == []


def test_live_ingest_with_settings():
    circular = {"doc_id": "CIR-2026-20", "doc_type": "circular", "title": "Pets in AC coaches",
                "effective_from": "2026-12-04", "supersedes": ["RUL-LUG-01"],
                "text": "## 1. Pets\nFrom 4 December 2026 small pets may travel in 1AC coupes only.",
                "settings": [{"name": "pet_fee_1AC", "value": 500}]}
    assert rag.ingest(circular)["chunks"] == 1
    assert "CIR-2026-20" not in ids(rag.search("pets 1AC coupe", as_of=TODAY))
    assert "CIR-2026-20" in ids(rag.search("pets 1AC coupe", as_of="2026-12-04"))
    from app.db import get_setting
    assert get_setting("pet_fee_1AC", "2026-12-04") == (500, "CIR-2026-20")


def test_hybrid_ranking_runs():
    class FakeEmbedder:                                        # stands in for the real model
        def encode(self, texts, normalize_embeddings=True):
            return np.array([[len(t) % 7 + 1.0, 1.0] for t in texts]) / 10
    rag.INDEX["embedder"] = FakeEmbedder()
    rag.rebuild()
    assert rag.search("pet dog", as_of=TODAY)
