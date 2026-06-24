# Hirer

Candidate ranking system for the Redrob Data and AI Challenge.

## Problem

Given 100k candidate profiles and a job description for a Senior AI Engineer,
rank the top 100 candidates by fit.

## Approach

Three scoring components combined with weights:

- Skill score (40%) - keyword matching + experience + title + education
- Semantic score (35%) - sentence transformer embeddings vs JD
- Behavioral score (25%) - platform signals like response rate, activity, github

## Folder Structure

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

## How to Run

pip install -r requirements.txt

python src/ranking.py --candidates data/candidates.jsonl --out output/submission.csv

# to skip semantic scoring (faster)
python src/ranking.py --candidates data/candidates.jsonl --out output/submission.csv --no-semantic