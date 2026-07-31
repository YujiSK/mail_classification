"""Phase 2 generation and quality-artifact orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.metadata import version
import json
import platform
from pathlib import Path
import subprocess

from mail_classification.quality import (
    audit_leakage,
    build_full_spot_review_samples,
    build_quality_statistics,
    build_review_samples,
    find_duplicates,
)
from mail_classification.quality.duplicates import DUPLICATE_FIELDS
from mail_classification.quality.leakage import LEAKAGE_FIELDS
from mail_classification.quality.review import REVIEW_FIELDS
from mail_classification.schemas import RunManifest, sha256_bytes, sha256_file

from .generator import SyntheticMailGenerator
from .io import records_to_jsonl_bytes, write_csv, write_json, write_jsonl
from .models import load_generation_config
from .templates import load_template_catalog


@dataclass(frozen=True)
class StageResult:
    stage: str
    count: int
    data_hash: str
    summary_path: Path
    data_path: Path
    manifest_path: Path
    automatic_quality_pass: bool


def _git_value(root: Path, *args: str) -> str | None:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    return (
        completed.stdout.strip() or None
        if completed.returncode == 0
        else None
    )


def _git_dirty(root: Path) -> bool | None:
    completed = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    return bool(completed.stdout.strip()) if completed.returncode == 0 else None


def run_generation_stage(
    stage: str,
    root: str | Path,
    config_path: str | Path = "configs/phase2.yml",
) -> StageResult:
    project_root = Path(root).resolve()
    resolved_config = project_root / config_path
    config = load_generation_config(resolved_config)
    template_path = project_root / config.paths.templates
    catalog = load_template_catalog(template_path)
    generator = SyntheticMailGenerator(config, catalog)
    approval_path: Path | None = None
    approval_hash: str | None = None
    if stage == "full":
        approval_path = project_root / config.paths.pilot_review_decision
        _validate_pilot_approval(
            approval_path,
            generator,
            template_path,
            config.generator.version,
        )
        approval_hash = sha256_file(approval_path)
    records = generator.generate(stage)

    relative_data_path = {
        "smoke": config.paths.smoke_data,
        "pilot": config.paths.pilot_data,
        "full": config.paths.full_data,
    }[stage]
    data_path = project_root / relative_data_path
    data_hash = write_jsonl(data_path, records)
    config_hash = sha256_file(resolved_config)
    template_hash = sha256_file(template_path)
    stage_generator_version = (
        config.generator.full_version
        if stage == "full"
        else config.generator.version
    )

    duplicates = find_duplicates(records)
    if stage == "smoke":
        audit_thresholds = config.quality.model_copy(
            update={
                "min_template_groups_per_label": 1,
                "max_template_group_share": 1.0,
            }
        )
    elif stage == "full":
        audit_thresholds = config.quality.model_copy(
            update={
                "exclusive_feature_min_count": (
                    config.quality.full_exclusive_feature_min_count
                )
            }
        )
    else:
        audit_thresholds = config.quality
    leakage = audit_leakage(records, audit_thresholds)
    statistics = build_quality_statistics(records)
    warnings = _quality_warnings(stage, statistics, duplicates, leakage, config)
    error_findings = [
        finding for finding in leakage if finding["severity"] == "error"
    ]
    automatic_pass = not warnings and not error_findings

    quality_dir = project_root / config.paths.quality_dir
    summary_path = quality_dir / f"{stage}_summary.json"
    duplicate_counts = {
        match_type: sum(
            finding["match_type"] == match_type for finding in duplicates
        )
        for match_type in ("exact", "normalized")
    }
    summary = {
        **statistics,
        "stage": stage,
        "duplicate_group_counts": duplicate_counts,
        "leakage_finding_counts": {
            severity: sum(
                finding["severity"] == severity for finding in leakage
            )
            for severity in ("error", "warning", "info")
        },
        "quality_warnings": warnings,
        "automatic_quality_pass": automatic_pass,
        "human_review_status": (
            "pending" if stage in {"pilot", "full"} else "not_required"
        ),
        "full_generation_allowed": stage == "full",
        "phase3_data_allowed": False,
        "approval_decision_path": (
            config.paths.pilot_review_decision if approval_path else None
        ),
        "approval_decision_hash": approval_hash,
        "config_hash": config_hash,
        "template_definition_hash": template_hash,
        "output_data_hash": data_hash,
        "generator_version": stage_generator_version,
    }
    write_json(summary_path, summary)

    if stage in {"pilot", "full"}:
        write_csv(
            quality_dir / f"{stage}_duplicates.csv",
            duplicates,
            DUPLICATE_FIELDS,
        )
        write_csv(
            quality_dir / f"{stage}_leakage_findings.csv",
            leakage,
            LEAKAGE_FIELDS,
        )
        review_rows = (
            build_review_samples(
                records,
                config.quality.review_samples_per_label,
                duplicates,
                leakage,
            )
            if stage == "pilot"
            else build_full_spot_review_samples(records, leakage)
        )
        write_csv(
            quality_dir / f"{stage}_review_samples.csv",
            review_rows,
            REVIEW_FIELDS,
        )

    run_id = f"phase2-{stage}-seed{config.generator.seed}"
    manifest_path = project_root / config.paths.manifest_dir / f"{run_id}.json"
    manifest = RunManifest(
        run_id=run_id,
        created_at=datetime.now(timezone.utc),
        git_commit=_git_value(project_root, "rev-parse", "HEAD"),
        git_dirty=_git_dirty(project_root),
        command=["generate", stage],
        python_version=platform.python_version(),
        platform=platform.platform(),
        dependency_versions={
            package: version(package) for package in ("pydantic", "pyyaml")
        },
        config_path=str(config_path),
        config_hash=config_hash,
        data_path=relative_data_path,
        data_hash=data_hash,
        data_generation_seed=config.generator.seed,
        template_path=config.paths.templates,
        template_hash=template_hash,
        generator_version=stage_generator_version,
        approval_decision_path=(
            config.paths.pilot_review_decision if approval_path else None
        ),
        approval_decision_hash=approval_hash,
        cv_seed=None,
        fold_artifact_path=None,
        fold_artifact_hash=None,
        preprocessor_name="english_minimal",
        preprocessor_version="1.0.0",
        model_name=None,
        model_parameters=None,
        primary_metric="macro_f1",
        output_directory=config.paths.quality_dir,
    )
    write_json(manifest_path, manifest.model_dump(mode="json"))
    return StageResult(
        stage=stage,
        count=len(records),
        data_hash=data_hash,
        summary_path=summary_path,
        data_path=data_path,
        manifest_path=manifest_path,
        automatic_quality_pass=automatic_pass,
    )


def _quality_warnings(stage, statistics, duplicates, leakage, config) -> list[str]:
    warnings: list[str] = []
    exact_count = sum(item["match_type"] == "exact" for item in duplicates)
    normalized_count = sum(item["match_type"] == "normalized" for item in duplicates)
    if exact_count > config.quality.max_exact_duplicate_groups:
        warnings.append("exact duplicate groups exceed threshold")
    if normalized_count > config.quality.max_normalized_duplicate_groups:
        warnings.append("normalized duplicate groups exceed threshold")
    expected_ratio = 1 / len(statistics["class_ratios"])
    if any(
        abs(ratio - expected_ratio) > config.quality.max_class_ratio_deviation
        for ratio in statistics["class_ratios"].values()
    ):
        warnings.append("class ratio deviation exceeds threshold")
    if stage in {"pilot", "full"}:
        missing_difficulties = set(
            item.value for item in config.quality.required_difficulties
        ) - set(statistics["difficulty_counts"])
        if missing_difficulties:
            warnings.append(
                "required difficulties missing: "
                + ",".join(sorted(missing_difficulties))
            )
    if any(
        item["severity"] == "error"
        or (stage == "pilot" and item["severity"] == "warning")
        for item in leakage
    ):
        warnings.append("leakage audit has error or warning findings")
    if stage == "full":
        _append_full_distribution_warnings(warnings, statistics, config)
    return warnings


def _validate_pilot_approval(
    decision_path: Path,
    generator: SyntheticMailGenerator,
    template_path: Path,
    generator_version: str,
) -> None:
    if not decision_path.is_file():
        raise ValueError(f"tracked Pilot approval is missing: {decision_path}")
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    required = {
        "status",
        "pilot_data_hash",
        "template_definition_hash",
        "generator_version",
        "reviewed_count",
        "passed_count",
        "leakage_info_candidates",
        "approved_at",
        "review_basis",
        "review_csv_sha256",
        "phase2c_ready",
    }
    missing = required - set(decision)
    if missing:
        raise ValueError(
            "tracked Pilot approval is missing fields: " + ",".join(sorted(missing))
        )
    pilot_hash = sha256_bytes(
        records_to_jsonl_bytes(generator.generate("pilot"))
    )
    checks = {
        "status": decision["status"] == "approved",
        "phase2c_ready": decision["phase2c_ready"] is True,
        "pilot_data_hash": decision["pilot_data_hash"] == pilot_hash,
        "template_definition_hash": (
            decision["template_definition_hash"] == sha256_file(template_path)
        ),
        "generator_version": decision["generator_version"] == generator_version,
        "review_counts": (
            decision["reviewed_count"] == decision["passed_count"]
            and decision["reviewed_count"] > 0
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ValueError(
            "tracked Pilot approval does not match current inputs: "
            + ",".join(failed)
        )


def _append_full_distribution_warnings(
    warnings: list[str], statistics: dict[str, object], config
) -> None:
    class_counts = statistics["class_counts"]
    if set(class_counts.values()) != {200}:
        warnings.append("Full class counts must be exactly 200")

    group_counts = statistics["template_group_counts"]
    if max(group_counts.values()) - min(group_counts.values()) > (
        config.quality.max_template_group_count_difference
    ):
        warnings.append("Full template-group count difference exceeds threshold")

    cross = statistics["class_difficulty_counts"]
    for label in class_counts:
        values = [
            count for key, count in cross.items() if key.startswith(f"{label}|")
        ]
        if max(values) - min(values) > (
            config.quality.max_difficulty_count_difference
        ):
            warnings.append(
                f"Full difficulty count difference exceeds threshold for {label}"
            )

    urgency = statistics["class_urgency_counts"]
    for label in class_counts:
        values = [
            count for key, count in urgency.items() if key.startswith(f"{label}|")
        ]
        if len(values) != 4 or set(values) != {50}:
            warnings.append(f"Full urgency counts must be 50 each for {label}")
