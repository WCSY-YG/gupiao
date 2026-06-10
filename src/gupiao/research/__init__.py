"""Research experiment scaffolding."""

from gupiao.research.auction_validation import (
    AuctionRollingEvaluation,
    AuctionRollingValidationConfig,
    AuctionRollingValidationResult,
    AuctionRollingWindow,
    AuctionStrategyComparisonConfig,
    AuctionStrategyComparisonResult,
    AuctionStrategySymbolResult,
    build_rolling_public_summary,
    build_public_summary,
    month_windows,
    run_auction_rolling_validation,
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
    "AuctionRollingEvaluation",
    "AuctionRollingValidationConfig",
    "AuctionRollingValidationResult",
    "AuctionRollingWindow",
    "LinearBaselineModel",
    "Prediction",
    "ResearchSample",
    "allocate_by_score",
    "build_rolling_public_summary",
    "build_public_summary",
    "build_auction_research_samples",
    "month_windows",
    "run_auction_rolling_validation",
    "predict_linear_baseline",
    "run_auction_strategy_comparison",
    "split_train_validation",
    "train_linear_baseline",
]
