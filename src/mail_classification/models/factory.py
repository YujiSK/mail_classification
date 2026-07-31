"""Config-driven Pipeline factory for the Core TF-IDF + linear-classifier models.

Returns an unfit ``Pipeline`` bundling the vectorizer and classifier so a
caller who fits it only on a Fold's train rows and calls ``.transform``/
``.predict`` on validation rows never fits TF-IDF outside that Fold's train
split (the project's binding leakage-prevention rule).
"""

from __future__ import annotations

from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

CORE_CLASSIFIERS: dict[str, type] = {
    "linear_svc": LinearSVC,
    "logistic_regression": LogisticRegression,
}


def build_core_pipeline(
    model_name: str,
    *,
    tfidf_params: dict[str, Any] | None = None,
    model_params: dict[str, Any] | None = None,
) -> Pipeline:
    """Build a ``TfidfVectorizer`` + Core linear-classifier Pipeline."""
    try:
        classifier_cls = CORE_CLASSIFIERS[model_name]
    except KeyError:
        raise ValueError(
            f"unknown Core model_name {model_name!r}; "
            f"expected one of {sorted(CORE_CLASSIFIERS)}"
        ) from None
    vectorizer = TfidfVectorizer(**(tfidf_params or {}))
    classifier = classifier_cls(**(model_params or {}))
    return Pipeline([("tfidf", vectorizer), ("clf", classifier)])
