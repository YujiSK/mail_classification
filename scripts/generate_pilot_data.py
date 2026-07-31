"""Generate the Phase 2 Pilot dataset and checks; never generates Full."""

from pathlib import Path

from mail_classification.generation import run_generation_stage


if __name__ == "__main__":
    result = run_generation_stage("pilot", Path(__file__).parents[1])
    print(f"{result.stage}: {result.count} records, sha256={result.data_hash}")
