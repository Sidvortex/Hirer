# Hirer

Hirer is a simple candidate ranking system built for the Redrob Data & AI Challenge.

## Team Members

* Ravada Siddharth
* Ishan Gupta

## Dataset

The dataset contains around 100,000 candidate profiles with information such as:

* Skills
* Work experience
* Education
* Certifications
* Behavioral signals from the platform

A job description for a Senior AI Engineer role is provided and candidates are ranked according to their relevance.

## What I Did

1. Explored the dataset and identified useful fields.
2. Created a basic keyword matching baseline.
3. Used sentence embeddings to compare candidate profiles with the job description.
4. Added behavioral signals like recruiter response rate and profile activity.
5. Combined the scores to generate the final ranking.

## Tech Stack

* Python
* Pandas
* NumPy
* Scikit-learn
* Sentence Transformers

## Project Structure

```text
Hirer/
├── data/
├── notebooks/
├── src/
├── output/
├── README.md
└── requirements.txt
```

## Running the Project

```bash
pip install -r requirements.txt
python src/ranking.py --candidates
```
```bash
"just for myself coz i dont't want to write this whole command every time"
pip install -r requirements.txt
python src/ranking.py --candidates "/home/sidvortex/Documents/project/[PUB] India_runs_data_and_ai_challenge/[PUB] India_runs_data_and_ai_challenge/India_runs_data_and_ai_challenge/candidates.jsonl" --out output/submission.csv
```
```bash
"No-semantic run pipeline for faster outputs"
pip install -r requirements.txt
python src/ranking.py --candidates "/home/sidvortex/Documents/project/[PUB] India_runs_data_and_ai_challenge/[PUB] India_runs_data_and_ai_challenge/India_runs_data_and_ai_challenge/candidates.jsonl" --out output/submission.csv --no-semantic
```

The ranked output file will be generated in the output folder.

## Results

The final ranking is based on:

* Skill match
* Semantic similarity
* Candidate activity and engagement

## Future Work

* Better weighting strategy
* LLM-based reranking
* More feature engineering
* Improved handling of behavioral signals
