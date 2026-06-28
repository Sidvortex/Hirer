# Hirer

Candidate ranking system for the Redrob Data and AI Challenge.

## Problem Statement

Given 100,000 candidate profiles and a job description for a Senior AI Engineer at Redrob, rank the top 100 candidates by fit.

Each candidate profile contains:

* Skills
* Work history
* Education
* Certifications
* Platform behavioral signals

The goal is to move beyond simple keyword matching and identify candidates who genuinely fit the role.

---

## Approach

The project was built in phases:

### Phase 1 - Dataset Exploration

* Explored candidate profile structure
* Identified relevant fields for ranking
* Analyzed job description requirements

### Phase 2 - Keyword Matching Baseline

* Extracted important skills from the JD
* Built a simple keyword-based scoring system
* Used as an initial benchmark

### Phase 3 - Semantic Matching

* Generated embeddings using `all-MiniLM-L6-v2`
* Compared candidate profiles with the job description
* Calculated semantic similarity scores

### Phase 4 - Behavioral Signals

Used information from `redrob_signals`, including:

* Recruiter response rate
* Platform activity
* GitHub activity score
* Interview completion rate
* Saved by recruiters

### Phase 5 - Final Ranking

Combined multiple signals into a final score:

| Component           | Weight |
| ------------------- | ------ |
| Skills Score        | 40%    |
| Semantic Similarity | 35%    |
| Behavioral Signals  | 25%    |

---

## Folder Structure

```text
project/
├── data/
├── notebooks/
│   └── exploration.ipynb
├── src/
│   ├── feature_engineering.py
│   ├── ranking.py
│   └── utils.py
├── output/
├── README.md
└── requirements.txt
```

## How to Run

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the ranking pipeline:

```bash
python src/ranking.py \
    --candidates data/candidates.jsonl \
    --out output/submission.csv
```

Run without semantic scoring (faster):

```bash
python src/ranking.py \
    --candidates data/candidates.jsonl \
    --out output/submission.csv \
    --no-semantic
```

---

## Results

The highest-ranked candidates typically show:

* Strong AI/ML engineering experience
* Python proficiency
* Experience with embeddings and retrieval systems
* Relevant work history
* High recruiter engagement and platform activity

The full pipeline processes the dataset and generates a ranked shortlist of recommended candidates.

---

## Future Improvements

* LLM-based re-ranking
* Better startup-fit detection
* Fine-tuned embedding models
* Automated honeypot profile detection
* Learning-to-rank approaches

```
```
