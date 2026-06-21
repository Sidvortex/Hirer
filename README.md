# Redrob Candidate Ranking Challenge

## Problem Statement

Given 100k candidate profiles and a job description for a Senior AI Engineer role, rank the top 100 candidates by fit. Each candidate has skills, work history, education, and platform behavioral signals.

## My Approach

Built in phases:

**Phase 1** - Explored the dataset, understood what fields matter for this JD (embeddings, vector search, Python, ranking eval experience)

**Phase 2** - Keyword matching baseline. Simple TF-IDF style scoring against must-have skills from the JD.

**Phase 3** - Added sentence-transformer embeddings (all-MiniLM-L6-v2) to compare candidate summaries + headlines against the JD text.

**Phase 4** - Behavioral signals from redrob_signals: response rate, activity recency, open-to-work, github score, etc.

**Phase 5** - Weighted combination of all three scores → final ranking

The scoring weights I landed on after experimenting: skills 40%, semantic 35%, behavioral 25%

## Folder Structure

```
project/
├── data/                        # sample data and schema
├── notebooks/
│   └── exploration.ipynb        # initial EDA and experiments
├── src/
│   ├── feature_engineering.py   # extract features from candidate json
│   ├── ranking.py               # main ranking pipeline
│   └── utils.py                 # helpers
├── output/
│   └── submission.csv           # final ranked output
├── README.md
├── requirements.txt
└── validate_submission.py
```

## How to Run

```bash
pip install -r requirements.txt

# rank candidates (reads candidates.jsonl from data/ folder)
python src/ranking.py --candidates data/candidates.jsonl --out output/submission.csv

# validate before submitting
python validate_submission.py output/submission.csv
```

Note: first run downloads the sentence-transformer model (~80MB). After that it's cached.

## Results

Top candidates tend to be ML/AI engineers with 5-9 years experience, strong Python skills, embeddings/retrieval background, and high platform engagement (quick response time, active recently, GitHub linked).

Average semantic similarity of top 10: ~0.71 vs 0.34 for random candidates.

Runs in about 3-4 minutes on CPU for full 100k dataset.
