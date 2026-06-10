from __future__ import annotations

from datetime import datetime, timezone
from unittest import TestCase

from gupiao.auction import build_auction_profile, score_auction_profile
from gupiao.data import AuctionMinuteBar


class AuctionFeaturesTest(TestCase):
    def test_build_auction_profile_scores_gap_volume_and_range(self) -> None:
        profile = build_auction_profile(
            "000001",
            auction_minutes(),
            previous_close=10.0,
            average_daily_volume=10_000.0,
        )

        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(profile.symbol, "000001")
        self.assertEqual(profile.trade_date.isoformat(), "2026-06-10")
        self.assertAlmostEqual(profile.gap_pct or 0.0, 0.035)
        self.assertAlmostEqual(profile.volume_ratio_to_daily or 0.0, 0.3)
        self.assertGreater(profile.strength_score, 60.0)

    def test_score_auction_profile_is_bounded(self) -> None:
        self.assertEqual(
            score_auction_profile(
                gap_pct=0.2,
                range_pct=0.0,
                volume_ratio_to_daily=1.0,
            ),
            100.0,
        )


def auction_minutes() -> list[AuctionMinuteBar]:
    fetched_at = datetime(2026, 6, 10, 1, 30, tzinfo=timezone.utc)  # noqa: UP017 - Python 3.10 compatibility
    return [
        AuctionMinuteBar(
            symbol="000001",
            trade_time=datetime(2026, 6, 10, 9, 24),
            open=10.1,
            close=10.2,
            high=10.2,
            low=10.1,
            volume=1000.0,
            amount=1_020_000.0,
            latest_price=10.2,
            provider="test",
            fetched_at=fetched_at,
        ),
        AuctionMinuteBar(
            symbol="000001",
            trade_time=datetime(2026, 6, 10, 9, 25),
            open=10.2,
            close=10.35,
            high=10.4,
            low=10.2,
            volume=2000.0,
            amount=2_070_000.0,
            latest_price=10.35,
            provider="test",
            fetched_at=fetched_at,
        ),
    ]
