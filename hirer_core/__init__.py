"""Hirer's scoring code, shared by the CLI (scripts/rank.py) and the web backend."""

from .jobs import DEFAULT_JOB, PRESETS, Job, get_job, parse_job  # noqa: F401
from .scoring import DEFAULT_WEIGHTS, rank  # noqa: F401
