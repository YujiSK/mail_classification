"""Generate the approved Phase 2 Full dataset and quality artifacts."""

from pathlib import Path

from mail_classification.generation import run_generation_stage


if __name__ == "__main__":
    result = run_generation_stage("full", Path(__file__).parents[1])
    print(f"{result.stage}: {result.count} records, sha256={result.data_hash}")
