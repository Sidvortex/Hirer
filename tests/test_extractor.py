import pytest

from extractor import extract_from_text, extract_text_from_pdf, _calc_yoe_from_career

canvas = pytest.importorskip('reportlab.pdfgen.canvas')
pytest.importorskip('pdfplumber')


def make_pdf(path, columns, header=()):
    """columns: list of (x, [lines]); header lines are drawn full-width above them"""
    c = canvas.Canvas(str(path))
    y = 800
    for line in header:
        c.drawString(150, y, line)
        y -= 18
    top = y - 12
    for x, lines in columns:
        y = top
        for line in lines:
            c.drawString(x, y, line)
            y -= 15
    c.save()


LEFT = ['SKILLS', 'Python', 'Spark', 'Airflow', 'SQL', 'Kafka', 'k8s', '', 'EDUCATION', 'B.Tech, VIT',
        '2012 - 2016', '', 'LANGUAGES', 'English', 'Malayalam']
RIGHT = ['EXPERIENCE', 'Senior Data Engineer, DataCo 2020 - Present',
         'Built streaming pipelines on Kafka and Spark for', 'real-time analytics used by forty product teams.',
         'Led migration of batch jobs to Airflow.', 'Data Engineer, Shopline 2016 - 2019',
         'Designed the warehouse schema and the dbt models', 'that power finance and growth reporting.',
         'Reduced nightly load time from six hours to one.', '', 'PROJECTS',
         'Open-source Airflow plugin for data quality checks', 'with more than two hundred GitHub stars.']


def test_two_column_resume_is_read_one_column_at_a_time(tmp_path):
    pdf = tmp_path / 'two.pdf'
    make_pdf(pdf, [(40, LEFT), (210, RIGHT)],
             header=['Meera Nair', 'meera@example.com   Bangalore   github.com/meeranair'])
    text = extract_text_from_pdf(str(pdf))
    assert text.index('LANGUAGES') < text.index('EXPERIENCE')       # left column finishes before the right starts
    assert 'Senior Data Engineer, DataCo 2020 - Present' in text    # lines aren't interleaved
    assert text.count('meera@example.com') == 1                     # header read once

    c = extract_from_text(text, 'two.pdf')
    assert c['profile']['name'] == 'Meera Nair'
    assert c['profile']['github'] == 'meeranair'
    assert c['profile']['location'] == 'Bangalore'
    assert c['profile']['years_of_experience'] == 9.0               # 2020-now plus 2016-2019
    assert [(j['title'], j['company']) for j in c['career_history']] == [
        ('Senior Data Engineer', 'DataCo'), ('Data Engineer', 'Shopline')]
    assert 'Kubernetes' in [s['name'] for s in c['skills']]         # "k8s" on the resume


def test_single_column_resume_is_left_alone(tmp_path):
    pdf = tmp_path / 'one.pdf'
    body = ['Asha Rao', 'Machine Learning Engineer', 'Experience', 'ML Engineer, Acme 2018 - Present'] + [
        f'Line {i} describing the search systems that were built and shipped to many users' for i in range(14)]
    make_pdf(pdf, [(40, body)])
    lines = extract_text_from_pdf(str(pdf)).splitlines()
    assert lines[0] == 'Asha Rao' and lines[3] == 'ML Engineer, Acme 2018 - Present'


def test_experience_ignores_gaps_and_counts_overlaps_once():
    jobs = [{'start_year': 2010, 'end_year': 2012}, {'start_year': 2018, 'end_year': 2021},
            {'start_year': 2019, 'end_year': 2022}]
    assert _calc_yoe_from_career(jobs) == 6.0      # 2 + (2018 to 2022), not 2010 to now
    assert _calc_yoe_from_career([{'start_year': 2021, 'end_year': 2021}]) == 0.5
    assert _calc_yoe_from_career([]) == 0.0


def test_only_real_certificates_are_listed():
    c = extract_from_text('Asha Rao\nSkills: machine learning, data science\nAWS Certified Developer', 'a.pdf')
    assert [x['name'] for x in c['certifications']] == ['Aws Certified']
