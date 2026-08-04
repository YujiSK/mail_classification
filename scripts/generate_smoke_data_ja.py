"""Generate the Japanese-track Smoke dataset and checks."""

from pathlib import Path

from mail_classification.generation import run_ja_generation_stage


if __name__ == "__main__":
    result = run_ja_generation_stage("smoke", Path(__file__).parents[1])
    print(f"{result.stage}: {result.count} records, sha256={result.data_hash}")
