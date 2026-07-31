"""Validated, JSON-compatible artifact schemas."""

from .dataset import Difficulty, MailLabel, RawMailRecord
from .folds import FoldArtifact, FoldMetadata, FoldRecord, FoldRole
from .run_manifest import RunManifest, sha256_bytes, sha256_file

__all__ = [
    "Difficulty",
    "FoldArtifact",
    "FoldMetadata",
    "FoldRecord",
    "FoldRole",
    "MailLabel",
    "RawMailRecord",
    "RunManifest",
    "sha256_bytes",
    "sha256_file",
]
