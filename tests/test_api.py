import io
import json
import time
import zipfile

import pytest
from fastapi.testclient import TestClient

import main
from store import JobStore

client = TestClient(main.app)


def profile(i, work):
    return {'candidate_id': f'C{i:03d}',
            'profile': {'headline': '', 'summary': '', 'current_title': 'Engineer', 'years_of_experience': 6},
            'career_history': [{'title': 'Engineer', 'description': work}], 'skills': [], 'certifications': [],
            'redrob_signals': {'last_active_date': '2026-05-01', 'open_to_work_flag': i % 2 == 0}}


JSONL = '\n'.join(json.dumps(profile(i, w)) for i, w in enumerate(
    ['Built FAISS vector search in Python', 'React dashboards', 'Spark and Airflow pipelines in Python'])).encode()


def wait(job_id):
    for _ in range(200):
        status = client.get(f'/status/{job_id}').json()
        if status['status'] != 'running':
            return status
        time.sleep(0.05)
    raise AssertionError('job did not finish')


def upload(**data):
    return client.post('/rank', files={'file': ('c.jsonl', JSONL)}, data={'top_n': '10', **data})


def test_rank_default_job_and_download():
    status = wait(upload().json()['job_id'])
    assert status['status'] == 'done' and status['result']['job_title'] == 'Senior AI Engineer'
    preview = client.get(f"/preview/{status['job_id']}").json()
    assert preview['results'][0]['candidate_id'] == 'C000'
    assert preview['meta']['weights_used']['semantic'] == 0
    csv_text = client.get(f"/download/{status['job_id']}").text
    assert csv_text.splitlines()[0] == 'candidate_id,rank,score,reasoning'
    assert not (main.DATA_DIR / status['job_id'] / 'candidates.jsonl').exists()     # upload deleted after use


def test_rank_against_pasted_job_and_preset():
    status = wait(upload(job_text='Data Engineer\nRequirements: Spark, Airflow, Python').json()['job_id'])
    assert status['result']['job']['must_have'] == ['python', 'spark', 'airflow']
    assert client.get(f"/preview/{status['job_id']}").json()['results'][0]['candidate_id'] == 'C002'
    status = wait(upload(job_preset='6').json()['job_id'])
    assert status['result']['job_title'] == 'Frontend Developer'


def test_bad_requests():
    assert upload(job_text='Chef\nMust cook well').status_code == 400
    assert upload(job_preset='99').status_code == 400
    assert upload(skill_weight='0.9').status_code == 400
    assert client.get('/preview/nope').status_code == 404


def test_parse_job_and_config():
    job = client.post('/parse-job', json={'text': 'Backend\nRequired: FastAPI, Postgres. 2-5 years. Pune',
                                          'extra_skills': 'grpc'}).json()
    assert job['must_have'] == ['postgresql', 'fastapi', 'grpc'] and job['years'] == [2, 5]
    assert job['locations'] == ['pune']
    assert len(client.get('/jobs').json()['jobs']) == 20
    assert client.get('/config').json()['access_required'] is False


def test_entry_limit(monkeypatch):
    monkeypatch.setattr(main, 'JSONL_ENTRY_LIMIT', 2)
    r = upload()
    assert r.status_code == 400 and 'up to 2 entries' in r.json()['detail']


def test_access_code_guards_recruiter_tools_only(monkeypatch):
    monkeypatch.setattr(main, 'ACCESS_CODE', 'letmein')
    assert upload().status_code == 401
    ok = client.post('/rank', files={'file': ('c.jsonl', JSONL)}, headers={'X-Access-Code': 'letmein'})
    assert ok.status_code == 200
    assert client.post('/match-single', json={'candidate': profile(1, 'python')}).status_code == 200


def test_rate_limit(monkeypatch):
    monkeypatch.setattr(main, 'RATE_LIMIT_PER_MIN', 2)
    main._hits.clear()
    codes = [upload().status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_resume_zip_flow(tmp_path):
    canvas = pytest.importorskip('reportlab.pdfgen.canvas')

    def pdf(lines):
        buf = io.BytesIO()
        c = canvas.Canvas(buf)
        for i, line in enumerate(lines):
            c.drawString(40, 800 - 16 * i, line)
        c.save()
        return buf.getvalue()

    zb = io.BytesIO()
    with zipfile.ZipFile(zb, 'w') as z:
        z.writestr('asha.pdf', pdf(['Asha Rao', 'ML Engineer', 'Experience', 'ML Engineer, Acme 2019 - Present',
                                    'Built semantic search with FAISS and Python']))
        z.writestr('asha.txt', 'Notice period: 30 days\nLocation: Pune')
        z.writestr('ravi.pdf', pdf(['Ravi Kumar', 'Frontend Developer', 'Skills: React, CSS']))
    job_id = client.post('/extract-bulk', files={'file': ('r.zip', zb.getvalue())}).json()['job_id']
    assert wait(job_id)['status'] == 'done'
    assert not (main.DATA_DIR / job_id / 'resumes.zip').exists()                    # originals deleted

    resumes = client.get(f'/extracted/{job_id}').json()['resumes']
    assert [(r['name'], r['has_details']) for r in resumes] == [('Asha Rao', True), ('Ravi Kumar', False)]

    ravi = resumes[1]['candidate_id']
    ranked = client.post('/rank-bulk', json={'extract_job_id': job_id,
                                             'edits': {ravi: {'notice_period_days': 90}}}).json()['job_id']
    status = wait(ranked)
    rows = client.get(f'/preview/{ranked}').json()['results']
    assert status['result']['relative'] is False
    assert [r['name'] for r in rows] == ['Asha Rao', 'Ravi Kumar'] and '90-day notice' in rows[1]['reasoning']


def test_job_store_survives_restart_and_purges(tmp_path):
    path = tmp_path / 'jobs.sqlite3'
    store = JobStore(path)
    store.create('done-job')
    store.update('done-job', status='done', result={'ranked': 3})
    store.create('half-done')
    store.step('half-done', 'Encoding...', 60)

    reopened = JobStore(path)                                   # what a restart sees
    assert reopened.get('done-job')['result'] == {'ranked': 3}
    assert reopened.get('half-done')['status'] == 'error' and 'restarted' in reopened.get('half-done')['error']
    assert set(reopened.purge(-1)) == {'done-job', 'half-done'} and reopened.get('done-job') is None
