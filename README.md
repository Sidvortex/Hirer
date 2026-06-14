# Hirer

Candidate ranking system for the Redrob Data and AI Challenge.

## Problem Statement

Given 100k candidate profiles and a job description for a Senior AI Engineer at Redrob,
rank the top 100 candidates by fit. Each candidate has skills, work history, education,
and platform behavioral signals.

## Approach

Built in phases:

- Phase 1 - Explored the dataset, understood what fields matter for this JD
- Phase 2 - Keyword matching baseline against must-have skills from the JD
- Phase 3 - Sentence transformer embeddings (all-MiniLM-L6-v2) comparing candidate text vs JD
- Phase 4 - Behavioral signals from redrob_signals: response rate, activity, github score etc
- Phase 5 - Weighted combination: Skills 40% + Semantic 35% + Behavioral 25%

## Folder Structure

```
Hirer/
├── data/
│   ├── candidate_schema.json
│   ├── sample_candidates.json
│   └── candidates.jsonl        <- download separately (465MB, not in repo)
├── notebooks/
│   └── exploration.ipynb
├── src/
│   ├── feature_engineering.py
│   ├── ranking.py
│   └── utils.py
├── output/
│   └── submission.csv          <- generated after running pipeline
├── README.md
└── requirements.txt
```

## Setup

### 1. Clone the repo

```
git clone https://github.com/Sidvortex/Hirer
cd Hirer
```

### 2. Create virtual environment

```
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```
pip install -r requirements.txt
```

### 4. Get the dataset

Download candidates.jsonl from the Redrob challenge page and place it inside the data/ folder:
Here is the link to the dataset : https://hack2skill.com/event/india_runs/dashboard/resources?utm_source=hack2skill&utm_medium=homepage

```
data/candidates.jsonl
```

## How to Run

### Full run (with semantic scoring, slower ~3-4 mins)

```
python src/ranking.py --candidates data/candidates.jsonl --out output/submission.csv
```

### Fast run (no semantic scoring, ~30 seconds)

```
python src/ranking.py --candidates data/candidates.jsonl --out output/submission.csv --no-semantic
```

### Test on sample data first

```
python src/ranking.py --candidates data/sample_candidates.json --out output/test_output.csv --no-semantic
```

Note: first full run downloads the sentence transformer model (~80MB). Cached after that.

## Results

Top candidates are ML/AI engineers with 5-9 years experience, strong Python and
embeddings background, and high platform engagement.

Average semantic similarity of top 10 vs random: 0.71 vs 0.34

Runs in about 3-4 minutes on CPU for full 100k dataset.

## Team

Ravada Siddharth - ML Engineer  
Ishan Gupta - Data Engineer     
Ayush Mishra - Frontend Dev