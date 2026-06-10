"""Simple long-only backtest engine for MVP strategy validation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date

from gupiao.data import AuctionProfile, DailyBar, has_errors, validate_daily_bars
from gupiao.signals import SignalPlan, build_breakout_signal
from gupiao.strategies import MovingAverageVolumeBreakoutStrategy


@dataclass(frozen=True)
class BacktestConfig:
    initial_cash: float = 100_000.0
    commission_rate: float = 0.0003
    slippage_rate: float = 0.0005
    max_holding_bars: int = 20
    atr_window: int = 14
    stop_atr_multiple: float = 2.0
    take_profit_r_multiple: float = 2.0
    apply_a_share_constraints: bool = True
    min_holding_bars_before_exit: int = 1
    limit_up_pct: float = 0.10
    limit_down_pct: float = 0.10
    block_suspended: bool = True


@dataclass(frozen=True)
class EquityPoint:
    trade_date: date
    equity: float
    cash: float
    position_value: float


@dataclass(frozen=True)
class Trade:
    symbol: str
    entry_date: date
    exit_date: date
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    return_pct: float
    holding_bars: int
    exit_reason: str


@dataclass(frozen=True)
class BacktestResult:
    symbol: str
    total_return: float
    max_drawdown: float
    win_rate: float
    trade_count: int
    equity_curve: tuple[EquityPoint, ...]
    trades: tuple[Trade, ...]
    assumptions: tuple[str, ...] = field(default_factory=tuple)


def run_breakout_backtest(
    symbol: str,
    bars: Sequence[DailyBar],
    *,
    strategy: MovingAverageVolumeBreakoutStrategy | None = None,
    config: BacktestConfig | None = None,
    auction_profiles: Mapping[date, AuctionProfile] | None = None,
) -> BacktestResult:
    strategy = strategy or MovingAverageVolumeBreakoutStrategy()
    config = config or BacktestConfig()
    ordered_bars = sorted(bars, key=lambda item: item.trade_date)
    quality_issues = validate_daily_bars(ordered_bars)
    if has_errors(quality_issues):
        raise ValueError("Cannot backtest bars with data quality errors.")

    cash = config.initial_cash
    quantity = 0.0
    entry_price = 0.0
    entry_date: date | None = None
    entry_cash = 0.0
    holding_bars = 0
    active_signal: SignalPlan | None = None
    equity_curve: list[EquityPoint] = []
    trades: list[Trade] = []
    auction_profiles = auction_profiles or {}

    for index, bar in enumerate(ordered_bars):
        exited_this_bar = False
        previous_close = ordered_bars[index - 1].close if index > 0 else None
        if quantity > 0 and active_signal is not None and entry_date is not None:
            holding_bars += 1
            exit_price, exit_reason = resolve_exit(
                bar,
                active_signal,
                holding_bars,
                config,
                previous_close=previous_close,
            )
            if exit_price is not None:
                cash, trade = close_position(
                    symbol=symbol,
                    cash=cash,
                    quantity=quantity,
                    entry_price=entry_price,
                    entry_cash=entry_cash,
                    entry_date=entry_date,
                    exit_date=bar.trade_date,
                    exit_price=exit_price,
                    holding_bars=holding_bars,
                    exit_reason=exit_reason,
                    config=config,
                )
                trades.append(trade)
                quantity = 0.0
                entry_price = 0.0
                entry_date = None
                entry_cash = 0.0
                holding_bars = 0
                active_signal = None
                exited_this_bar = True

        if quantity == 0 and not exited_this_bar:
            history = ordered_bars[: index + 1]
            candidate = strategy.evaluate(
                symbol,
                history,
                auction_profile=auction_profiles.get(bar.trade_date),
            )
            if candidate is not None:
                signal = build_breakout_signal(
                    candidate,
                    history,
                    atr_window=config.atr_window,
                    stop_atr_multiple=config.stop_atr_multiple,
                    take_profit_r_multiple=config.take_profit_r_multiple,
                )
                if signal is not None:
                    if can_enter(bar, previous_close, config):
                        entry_price = apply_buy_slippage(signal.entry_price, config)
                        quantity, cash, entry_cash = open_position(cash, entry_price, config)
                        entry_date = bar.trade_date
                        active_signal = signal

        position_value = quantity * bar.close
        equity_curve.append(
            EquityPoint(
                trade_date=bar.trade_date,
                equity=cash + position_value,
                cash=cash,
                position_value=position_value,
            )
        )

    if quantity > 0 and entry_date is not None:
        last_bar = ordered_bars[-1]
        cash, trade = close_position(
            symbol=symbol,
            cash=cash,
            quantity=quantity,
            entry_price=entry_price,
            entry_cash=entry_cash,
            entry_date=entry_date,
            exit_date=last_bar.trade_date,
            exit_price=apply_sell_slippage(last_bar.close, config),
            holding_bars=holding_bars,
            exit_reason="end_of_data",
            config=config,
        )
        trades.append(trade)
        equity_curve[-1] = EquityPoint(
            trade_date=last_bar.trade_date,
            equity=cash,
            cash=cash,
            position_value=0.0,
        )

    final_equity = equity_curve[-1].equity if equity_curve else config.initial_cash
    return BacktestResult(
        symbol=symbol,
        total_return=(final_equity / config.initial_cash) - 1,
        max_drawdown=max_drawdown([point.equity for point in equity_curve]),
        win_rate=win_rate(trades),
        trade_count=len(trades),
        equity_curve=tuple(equity_curve),
        trades=tuple(trades),
        assumptions=(
            "Long-only, single-symbol MVP backtest.",
            "Entries execute at signal close with configured slippage.",
            "A-share constraints apply when config.apply_a_share_constraints is true.",
            "Call-auction profiles are applied only on matching trade dates."
            if auction_profiles
            else "No call-auction filter was applied.",
        ),
    )


def resolve_exit(
    bar: DailyBar,
    signal: SignalPlan,
    holding_bars: int,
    config: BacktestConfig,
    *,
    previous_close: float | None = None,
) -> tuple[float | None, str]:
    if not can_exit(bar, previous_close, holding_bars, config):
        return None, ""
    if bar.low <= signal.stop_loss:
        return apply_sell_slippage(signal.stop_loss, config), "stop_loss"
    if bar.high >= signal.take_profit:
        return apply_sell_slippage(signal.take_profit, config), "take_profit"
    if holding_bars >= config.max_holding_bars:
        return apply_sell_slippage(bar.close, config), "max_holding_bars"
    return None, ""


def can_enter(
    bar: DailyBar,
    previous_close: float | None,
    config: BacktestConfig,
) -> bool:
    if not config.apply_a_share_constraints:
        return True
    if config.block_suspended and is_suspended(bar):
        return False
    return not is_limit_up(bar.close, previous_close, config.limit_up_pct)


def can_exit(
    bar: DailyBar,
    previous_close: float | None,
    holding_bars: int,
    config: BacktestConfig,
) -> bool:
    if not config.apply_a_share_constraints:
        return True
    if holding_bars < config.min_holding_bars_before_exit:
        return False
    if config.block_suspended and is_suspended(bar):
        return False
    return not is_limit_down(bar.close, previous_close, config.limit_down_pct)


def is_suspended(bar: DailyBar) -> bool:
    return bar.volume <= 0


def is_limit_up(price: float, previous_close: float | None, limit_up_pct: float) -> bool:
    if previous_close is None or previous_close <= 0:
        return False
    return price >= previous_close * (1 + limit_up_pct)


def is_limit_down(price: float, previous_close: float | None, limit_down_pct: float) -> bool:
    if previous_close is None or previous_close <= 0:
        return False
    return price <= previous_close * (1 - limit_down_pct)


def open_position(
    cash: float,
    entry_price: float,
    config: BacktestConfig,
) -> tuple[float, float, float]:
    quantity = cash / (entry_price * (1 + config.commission_rate))
    gross_cost = quantity * entry_price
    commission = gross_cost * config.commission_rate
    return quantity, cash - gross_cost - commission, cash


def close_position(
    *,
    symbol: str,
    cash: float,
    quantity: float,
    entry_price: float,
    entry_cash: float,
    entry_date: date,
    exit_date: date,
    exit_price: float,
    holding_bars: int,
    exit_reason: str,
    config: BacktestConfig,
) -> tuple[float, Trade]:
    proceeds = quantity * exit_price
    commission = proceeds * config.commission_rate
    final_cash = cash + proceeds - commission
    pnl = final_cash - entry_cash
    trade = Trade(
        symbol=symbol,
        entry_date=entry_date,
        exit_date=exit_date,
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=quantity,
        pnl=pnl,
        return_pct=pnl / entry_cash if entry_cash > 0 else 0.0,
        holding_bars=holding_bars,
        exit_reason=exit_reason,
    )
    return final_cash, trade


def apply_buy_slippage(price: float, config: BacktestConfig) -> float:
    return price * (1 + config.slippage_rate)


def apply_sell_slippage(price: float, config: BacktestConfig) -> float:
    return price * (1 - config.slippage_rate)


def max_drawdown(equity_values: Sequence[float]) -> float:
    peak = 0.0
    worst = 0.0
    for equity in equity_values:
        peak = max(peak, equity)
        if peak > 0:
            worst = min(worst, (equity / peak) - 1)
    return worst


def win_rate(trades: Sequence[Trade]) -> float:
    if not trades:
        return 0.0
    wins = sum(1 for trade in trades if trade.pnl > 0)
    return wins / len(trades)
