import io
import os
import sys
import zipfile

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'hirer-backend'))

from resumes import clean_edits, find_detail_files, apply_edits  # noqa: E402


def test_clean_edits_understands_loose_input():
    e = clean_edits({'Notice Period': '2 months', 'Open to work': 'Yes', 'relocate': 'no',
                     'Experience': '6.5 years', 'skills': 'Python, NLP ,', 'city': 'Pune'})
    assert e == {'notice_period_days': 60, 'open_to_work': True, 'willing_to_relocate': False,
                 'years_of_experience': 6.5, 'skills': ['Python', 'NLP'], 'location': 'Pune'}


def test_detail_files_same_name_and_csv():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('cv/asha.pdf', b'x')
        z.writestr('cv/asha.txt', 'notice: 30\nopen to work: yes')
        z.writestr('cv/ravi.pdf', b'x')
        z.writestr('cv/neha.pdf', b'x')
        z.writestr('cv/neha.json', '{"location": "Noida"}')
        z.writestr('details.csv', 'filename,notice_period\nravi.pdf,90\n')
    with zipfile.ZipFile(buf) as z:
        found = find_detail_files(z, ['cv/asha.pdf', 'cv/ravi.pdf', 'cv/neha.pdf'])
    assert set(found) == {'cv/asha.pdf', 'cv/ravi.pdf', 'cv/neha.pdf'}
    assert found['cv/ravi.pdf'][1] == 'details.csv'


def test_apply_edits_sets_profile_and_details():
    c = {'candidate_id': 'A', 'profile': {'name': 'X'}, 'skills': []}
    apply_edits(c, {'name': 'Asha', 'years_of_experience': '7', 'skills': ['Python'],
                    'notice_period_days': 30, 'location': 'Pune'})
    assert c['profile']['name'] == 'Asha' and c['profile']['years_of_experience'] == 7.0
    assert c['skills'] == [{'name': 'Python'}]
    assert c['_details'] == {'notice_period_days': 30, 'location': 'Pune'}
