"""Research experiment scaffolding."""

from gupiao.research.experiments import (
    LinearBaselineModel,
    Prediction,
    ResearchSample,
    allocate_by_score,
    build_auction_research_samples,
    predict_linear_baseline,
    split_train_validation,
    train_linear_baseline,
)

__all__ = [
    "LinearBaselineModel",
    "Prediction",
    "ResearchSample",
    "allocate_by_score",
    "build_auction_research_samples",
    "predict_linear_baseline",
    "split_train_validation",
    "train_linear_baseline",
]
