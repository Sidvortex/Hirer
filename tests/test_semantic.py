"""The real models aren't downloaded in tests; small stand-ins check the logic around them."""

import numpy as np
import pytest

from hirer_core import rank, semantic

WORDS = ['spark', 'react', 'python', 'sales']


class FakeEmbedder:
    """embeds a text as counts of four words, so similarity is easy to reason about"""
    calls = 0

    def encode(self, texts, normalize_embeddings=True, **_):
        FakeEmbedder.calls += len(texts)
        v = np.array([[t.lower().count(w) for w in WORDS] for t in texts], dtype=float) + 1e-6
        return v / np.linalg.norm(v, axis=1, keepdims=True)


class FakeReranker:
    def predict(self, pairs, **_):
        return np.array([10.0 if 'expert' in doc else -5.0 for _, doc in pairs])


@pytest.fixture(autouse=True)
def fake_models(monkeypatch):
    monkeypatch.setattr(semantic, '_models', {'embed': FakeEmbedder(), 'rerank': FakeReranker()})


def cand(cid, summary='', roles=()):
    return {'candidate_id': cid, 'profile': {'summary': summary, 'current_title': 'Engineer', 'years_of_experience': 6},
            'career_history': [{'title': 'Engineer', 'description': r} for r in roles],
            'skills': [], 'certifications': [],
            'redrob_signals': {'last_active_date': '2026-05-01', 'open_to_work_flag': True}}


def test_best_piece_of_a_candidate_counts():
    a = cand('A', 'sales sales sales', roles=['spark spark python'])     # relevant role, unrelated summary
    b = cand('B', 'sales sales sales', roles=['react react'])
    scores = semantic.semantic_scores([a, b], 'spark python')
    assert scores[0] > 0.9 > scores[1]


def test_embeddings_are_cached():
    cs = [cand('A', 'spark'), cand('B', 'react')]
    semantic.semantic_scores(cs, 'spark')
    first = FakeEmbedder.calls
    semantic.semantic_scores(cs, 'python')          # same candidates, different job
    assert FakeEmbedder.calls == first + 1          # only the job text was encoded again


def test_model_prefixes():
    assert semantic._prefixes('BAAI/bge-small-en-v1.5')[0].startswith('Represent this sentence')
    assert semantic._prefixes('intfloat/multilingual-e5-small') == ('query: ', 'passage: ')
    assert semantic._prefixes('all-MiniLM-L6-v2') == ('', '')


def test_rerank_reorders_the_top_but_keeps_scores_descending():
    cs = [cand('A', 'python spark'), cand('B', 'python spark expert'), cand('C', 'sales')]
    plain = rank(cs, use_semantic=True)['rows']
    again = rank(cs, use_semantic=True, use_rerank=True)
    rows = again['rows']
    assert again['reranked'] and rows[0]['candidate_id'] == 'B' and rows[0]['rerank'] == 1.0
    assert [r['score'] for r in rows] == sorted((r['score'] for r in rows), reverse=True)
    assert {r['candidate_id'] for r in rows} == {r['candidate_id'] for r in plain}
