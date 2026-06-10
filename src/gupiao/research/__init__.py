"""Research experiment scaffolding."""

from gupiao.research.auction_validation import (
    AuctionStrategyComparisonConfig,
    AuctionStrategyComparisonResult,
    AuctionStrategySymbolResult,
    build_public_summary,
    run_auction_strategy_comparison,
)
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
    "AuctionStrategyComparisonConfig",
    "AuctionStrategyComparisonResult",
    "AuctionStrategySymbolResult",
    "LinearBaselineModel",
    "Prediction",
    "ResearchSample",
    "allocate_by_score",
    "build_public_summary",
    "build_auction_research_samples",
    "predict_linear_baseline",
    "run_auction_strategy_comparison",
    "split_train_validation",
    "train_linear_baseline",
]
