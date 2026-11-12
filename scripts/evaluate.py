"""
Measure how good the ranking is against labels made by people.

1. Make a sheet to label (150 candidates, shuffled so rank doesn't bias you):
       python scripts/evaluate.py sheet --candidates data/candidates_small.jsonl
2. Open data/labels.csv and fill the "label" column for each row:
       3 = strong fit for the job    2 = good fit    1 = weak fit    0 = not a fit
3. Score the current ranking, and optionally search for better weights:
       python scripts/evaluate.py score --candidates data/candidates_small.jsonl
       python scripts/evaluate.py score --candidates data/candidates_small.jsonl --semantic --tune

Metrics (computed over the labelled candidates only):
    NDCG@10  how well the top 10 are ordered, 1.0 is perfect
    P@10     share of the top 10 that are good or strong fits
    MRR      1 / rank of the first good-or-strong fit
"""

import argparse
import csv
import itertools
import math
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from hirer_core import rank, get_job, DEFAULT_WEIGHTS                    # noqa: E402
from hirer_core.scoring import score, combine, effective_weights         # noqa: E402
from hirer_core.utils import load_candidates                             # noqa: E402

GOOD = 2   # labels at or above this count as relevant for P@10 and MRR


def ndcg(labels, k=10):
    def dcg(xs):
        return sum((2 ** x - 1) / math.log2(i + 2) for i, x in enumerate(xs[:k]))
    ideal = dcg(sorted(labels, reverse=True))
    return dcg(labels) / ideal if ideal else 0.0


def metrics(ordered_labels):
    """ordered_labels: labels of the labelled candidates, best-ranked first"""
    first = next((i for i, x in enumerate(ordered_labels) if x >= GOOD), None)
    top = ordered_labels[:10]
    return {'ndcg@10': ndcg(ordered_labels, 10),
            'p@10': sum(x >= GOOD for x in top) / len(top) if top else 0.0,
            'mrr': 1 / (first + 1) if first is not None else 0.0}


def read_labels(path):
    with open(path, newline='', encoding='utf-8') as f:
        return {r['candidate_id']: int(r['label']) for r in csv.DictReader(f)
                if (r.get('label') or '').strip() != ''}


def make_sheet(args):
    candidates = load_candidates(args.candidates)
    job = get_job(preset=args.preset, text=_read(args.job))
    by_id = {c['candidate_id']: c for c in candidates}
    # half from the current top (where ordering matters most), half at random
    top = [r['candidate_id'] for r in rank(candidates, use_semantic=False, job=job, top_n=args.n // 2)['rows']]
    rng = random.Random(7)
    rest = rng.sample([i for i in by_id if i not in set(top)], min(args.n - len(top), len(by_id) - len(top)))
    picked = top + rest
    rng.shuffle(picked)

    with open(args.labels, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['candidate_id', 'label', 'title', 'years', 'location', 'headline', 'skills', 'recent_work'])
        for cid in picked:
            c = by_id[cid]
            p = c.get('profile', {})
            work = (c.get('career_history') or [{}])[0]
            w.writerow([cid, '', p.get('current_title', ''), p.get('years_of_experience', ''),
                        p.get('location', ''), p.get('headline', ''),
                        ', '.join(s['name'] for s in c.get('skills', [])),
                        (work.get('description') or '')[:400]])
    print(f'Wrote {len(picked)} candidates to {args.labels} for the job "{job.title}".')
    print('Fill the "label" column (0-3), then run: python scripts/evaluate.py score --candidates', args.candidates)


def run_score(args):
    labels = read_labels(args.labels)
    if len(labels) < 20:
        sys.exit(f'Only {len(labels)} labelled rows in {args.labels}; label at least 20 first.')
    candidates = [c for c in load_candidates(args.candidates)]
    job = get_job(preset=args.preset, text=_read(args.job))
    ids = [c['candidate_id'] for c in candidates]
    missing = set(labels) - set(ids)
    if missing:
        sys.exit(f'{len(missing)} labelled ids are not in {args.candidates}, e.g. {sorted(missing)[:3]}')

    def evaluate(order):
        return metrics([labels[ids[i]] for i in order if ids[i] in labels])

    if args.rerank:
        rows = rank(candidates, use_semantic=args.semantic, use_rerank=True, top_n=len(candidates), job=job)['rows']
        m = metrics([labels[r['candidate_id']] for r in rows if r['candidate_id'] in labels])
        print(f"With re-ranking: NDCG@10 {m['ndcg@10']:.3f}  P@10 {m['p@10']:.2f}  MRR {m['mrr']:.3f}")
        return

    s = score(candidates, job, use_semantic=args.semantic)

    def order_for(weights):
        used = effective_weights(weights, s['components'], s['available'], s['relative'])
        final = combine(s['components'], used)
        return sorted(range(len(ids)), key=lambda i: (-round(float(final[i]), 4), ids[i]))

    base = evaluate(order_for(DEFAULT_WEIGHTS))
    print(f'{len(labels)} labelled candidates, job "{job.title}", semantic {"on" if args.semantic else "off"}')
    print(f"Current weights {DEFAULT_WEIGHTS}:")
    print(f"  NDCG@10 {base['ndcg@10']:.3f}  P@10 {base['p@10']:.2f}  MRR {base['mrr']:.3f}")

    if args.tune:
        steps = [x / 20 for x in range(0, 21)]
        sem_steps = steps if args.semantic else [0.0]
        results = []
        for ws, we in itertools.product(steps, sem_steps):
            wb = round(1 - ws - we, 2)
            if wb < 0 or ws == 0:
                continue
            w = {'skill': ws, 'semantic': we, 'behavioral': wb}
            results.append((evaluate(order_for(w))['ndcg@10'], w))
        results.sort(key=lambda x: -x[0])
        print('\nBest weights by NDCG@10:')
        for value, w in results[:5]:
            print(f"  {value:.3f}  skill {w['skill']:.2f}  semantic {w['semantic']:.2f}  behavioral {w['behavioral']:.2f}")
        print('\nWith few labels the best row can win by chance. Prefer weights that stay near the top\n'
              'when you add more labels, then set them in DEFAULT_WEIGHTS (hirer_core/scoring.py).')


def _read(path):
    return open(path, encoding='utf-8').read() if path else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('sheet', 'score'):
        p = sub.add_parser(name)
        p.add_argument('--candidates', required=True)
        p.add_argument('--labels', default='data/labels.csv')
        p.add_argument('--job', help='text file with a job description')
        p.add_argument('--preset', type=int, help='id of a built-in job (1-20)')
    sub.choices['sheet'].add_argument('--n', type=int, default=150)
    sub.choices['score'].add_argument('--semantic', action='store_true')
    sub.choices['score'].add_argument('--rerank', action='store_true')
    sub.choices['score'].add_argument('--tune', action='store_true', help='search for better weights')
    args = ap.parse_args()
    (make_sheet if args.cmd == 'sheet' else run_score)(args)


if __name__ == '__main__':
    main()
