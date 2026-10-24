"""Run from the repo root: python -m pytest -q"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from hirer_core import rank                                        # noqa: E402
from hirer_core.features import skill_matches, behavioral_score    # noqa: E402
from hirer_core.scoring import effective_weights                   # noqa: E402
from hirer_core.utils import contains_term, reference_date, normalize_0_1  # noqa: E402


def cand(cid, text='', last_active='2026-05-01', otw=True, yoe=6, title='ML Engineer'):
    return {
        'candidate_id': cid,
        'profile': {'headline': text, 'summary': '', 'current_title': title,
                    'years_of_experience': yoe},
        'career_history': [], 'skills': [], 'certifications': [], 'education': [],
        'redrob_signals': {'last_active_date': last_active, 'open_to_work_flag': otw,
                           'recruiter_response_rate': 0.5},
    }


# whole-word matching

def test_cv_does_not_match_opencv():
    assert not contains_term('built tools with opencv and python', 'cv')
    assert contains_term('cv and image work', 'cv')


def test_ui_does_not_match_building():
    assert not contains_term('building apis', 'ui')


def test_plural_and_punctuation():
    assert contains_term('fine-tuned llms on a/b testing data', 'llm')
    assert contains_term('ran a/b testing weekly', 'a/b testing')
    assert contains_term('sentence-transformers, faiss', 'faiss')


def test_opencv_candidate_not_penalised():
    m = skill_matches(cand('A', 'python nlp embeddings opencv'))
    assert m['negative'] == []


# recency

def test_reference_date_is_newest_activity():
    cs = [cand('A', last_active='2026-01-01'), cand('B', last_active='2026-05-27')]
    assert reference_date(cs).isoformat() == '2026-05-27'


def test_recent_candidate_scores_higher_on_any_day():
    cs = [cand('A', last_active='2026-05-25'), cand('B', last_active='2025-01-01')]
    ref = reference_date(cs)
    assert behavioral_score(cs[0], ref) > behavioral_score(cs[1], ref)


# weights

def test_constant_component_gives_its_weight_away():
    comps = {'skill': np.array([0.1, 0.9]), 'semantic': np.zeros(2),
             'behavioral': np.array([0.5, 0.5])}
    w = effective_weights({'skill': 0.4, 'semantic': 0.35, 'behavioral': 0.25}, comps)
    assert w == {'skill': 1.0, 'semantic': 0.0, 'behavioral': 0.0}


def test_normalize_constant_is_zero():
    assert normalize_0_1([3, 3, 3]).tolist() == [0, 0, 0]


# ranking

def test_rank_orders_and_breaks_ties_by_id():
    cs = [cand('C', 'python'), cand('B', 'python'), cand('A', 'python nlp embeddings faiss')]
    rows = rank(cs, use_semantic=False)['rows']
    assert [r['candidate_id'] for r in rows] == ['A', 'B', 'C']
    assert [r['rank'] for r in rows] == [1, 2, 3]


def test_resume_reasoning_has_no_placeholder_signals():
    c = cand('A', 'python')
    c['_source_file'] = 'a.pdf'
    row = rank([c, cand('B')], use_semantic=False)['rows'][0]
    assert 'open to work' not in row['reasoning']
