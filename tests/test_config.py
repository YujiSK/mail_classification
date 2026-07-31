from pathlib import Path

import pytest
import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from mail_classification.preprocessing import EnglishPreprocessingConfig
from mail_classification.schemas import MailLabel

CONFIG_PATH = Path(__file__).parents[1] / "configs" / "phase1.yml"


class FoldConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    n_splits: int
    group_column: str


def load_config() -> dict[str, object]:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def test_phase1_config_matches_schema_contracts() -> None:
    config = load_config()
    labels = config["project"]["labels"]
    assert set(labels) == {label.value for label in MailLabel}
    FoldConfig.model_validate(config["folds"])
    EnglishPreprocessingConfig.model_validate(config["preprocessing"])


def test_unknown_preprocessing_option_is_not_silently_ignored() -> None:
    config = load_config()["preprocessing"]
    config["segmentation"]["future_magic"] = True
    with pytest.raises(ValidationError, match="future_magic"):
        EnglishPreprocessingConfig.model_validate(config)


def test_unsupported_feature_true_fails_explicitly() -> None:
    config = EnglishPreprocessingConfig(
        segmentation={**load_config()["preprocessing"]["segmentation"], "lemmatize": True}
    )
    from mail_classification.preprocessing import EnglishPreprocessor

    with pytest.raises(NotImplementedError):
        EnglishPreprocessor(config)
