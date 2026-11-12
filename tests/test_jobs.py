import pytest

from hirer_core import rank, parse_job, get_job
from hirer_core.features import skill_evidence, experience_score, title_score
from hirer_core.skills import find_skills, term_in

JD = """Data Engineer
We are hiring in Bangalore.
Requirements:
- 3+ years building pipelines with Spark, Airflow and SQL
- Strong Python
Nice to have: dbt, Kubernetes
Docker is a plus.
Not looking for: pure frontend (React) profiles.
"""


def cand(cid, summary='', work='', skills=(), yoe=5, title='Data Engineer'):
    return {'candidate_id': cid,
            'profile': {'headline': '', 'summary': summary, 'current_title': title, 'years_of_experience': yoe},
            'career_history': [{'title': title, 'description': work}] if work else [],
            'skills': [{'name': s, 'proficiency': 'intermediate'} for s in skills],
            'certifications': [], 'education': [],
            'redrob_signals': {'last_active_date': '2026-05-01', 'open_to_work_flag': True}}


def test_parse_job_sections():
    job = parse_job(JD)
    assert job.title == 'Data Engineer'
    assert set(job.must_have) == {'spark', 'airflow', 'sql', 'python'}
    assert set(job.nice_to_have) == {'dbt', 'kubernetes', 'docker'}
    assert job.negative == ['react']
    assert job.years == (3, None)
    assert job.locations == ['bangalore']


def test_parse_job_range_and_extra_skills():
    job = parse_job('Platform role\nRequired: PyTorch. 4-7 years.', extra_skills=['Triton', ' '])
    assert job.years == (4, 7)
    assert job.must_have == ['pytorch', 'triton']


def test_synonyms_match():
    assert find_skills('deployed on k8s with sklearn models') == ['scikit-learn', 'kubernetes']
    assert term_in('worked on natural language processing', 'nlp')
    assert not term_in('my cv is attached', 'computer vision')


def test_work_evidence_beats_a_bare_mention():
    did = cand('A', work='Built Spark pipelines')
    listed = cand('B', skills=['Spark'])
    said = cand('C', summary='Interested in Spark')
    strengths = [skill_evidence(c, ['spark'])['spark'] for c in (did, listed, said)]
    assert strengths[0] > strengths[1] > strengths[2] > 0


def test_skill_test_score_tempers_a_claim():
    c = cand('A', work='Built Spark pipelines')
    c['redrob_signals']['skill_assessment_scores'] = {'Spark': 20}
    assert skill_evidence(c, ['spark'])['spark'] == pytest.approx(0.6)


def test_experience_range_and_open_ended():
    job = parse_job(JD)
    assert experience_score(cand('A', yoe=12), job) == 1.0
    assert experience_score(cand('A', yoe=2.5), job) == 0.8
    assert experience_score(cand('A', yoe=0), job) == 0.2
    assert experience_score(cand('A', yoe=11), get_job()) == 0.75      # default job wants 5-9


def test_title_overlap_for_custom_jobs():
    job = parse_job(JD)
    assert title_score(cand('A', title='Senior Data Engineer'), job) == 1.0
    assert title_score(cand('A', title='Accountant'), job) < 0.2


def test_rank_against_pasted_job():
    cs = [cand('A', work='React frontend work', skills=['React']),
          cand('B', work='Spark and Airflow pipelines in Python', skills=['SQL'])]
    res = rank(cs, use_semantic=False, job=parse_job(JD))
    assert res['rows'][0]['candidate_id'] == 'B'
    assert res['rows'][0]['missing_skills'] == []
    assert res['job']['title'] == 'Data Engineer'


def test_job_without_known_skills_needs_semantic():
    with pytest.raises(ValueError, match='No known skills'):
        rank([cand('A'), cand('B')], use_semantic=False, job=parse_job('Chef\nMust cook well.'))


def test_presets():
    assert get_job(preset=14).title == 'Data Engineer'
    with pytest.raises(ValueError):
        get_job(preset=99)
