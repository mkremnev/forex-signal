"""Correlation analysis for market instruments.

Uses Pearson correlation on log-returns to measure co-movement
between different instruments over a specified lookback period.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class CorrelationResult:
    """Result of correlation analysis for a symbol pair.

    Attributes:
        symbol1: First symbol in the pair
        symbol2: Second symbol in the pair
        correlation: Pearson correlation coefficient (-1 to 1)
        data_points: Number of data points used
    """

    symbol1: str
    symbol2: str
    correlation: float
    data_points: int


class CorrelationAnalyzer:
    """Analyzes correlation between market instruments.

    Uses Pearson correlation on log-returns to measure the degree
    of co-movement between different instruments.

    Example:
        analyzer = CorrelationAnalyzer(lookback_hours=24)

        # Build correlation matrix from price data
        price_data = {
            "EUR/USD": df_eurusd,
            "GBP/USD": df_gbpusd,
            "USD/JPY": df_usdjpy,
        }
        matrix = analyzer.build_correlation_matrix(price_data)

        # Get correlated pairs for a symbol
        pairs = analyzer.get_correlated_pairs("EUR/USD", threshold=0.7)
    """

    def __init__(
        self,
        lookback_hours: int = 24,
        min_data_points: int = 20,
        high_correlation_threshold: float = 0.7,
    ):
        """Initialize correlation analyzer.

        Args:
            lookback_hours: Hours of data to use for correlation
            min_data_points: Minimum data points required for valid correlation
            high_correlation_threshold: Threshold for "high" correlation
        """
        self._lookback_hours = lookback_hours
        self._min_data_points = min_data_points
        self._high_threshold = high_correlation_threshold
        self._correlation_matrix: pd.DataFrame | None = None
        self._symbols: list[str] = []

    @property
    def lookback_hours(self) -> int:
        """Get lookback period in hours."""
        return self._lookback_hours

    @property
    def min_data_points(self) -> int:
        """Get minimum required data points."""
        return self._min_data_points

    def build_correlation_matrix(
        self,
        price_data: dict[str, pd.DataFrame],
    ) -> pd.DataFrame:
        """Build correlation matrix from price data.

        Computes Pearson correlation on log-returns for all pairs
        of instruments in the provided data.

        Args:
            price_data: Dictionary mapping symbol to OHLCV DataFrame
                        Each DataFrame should have 'close' column

        Returns:
            DataFrame with correlation matrix (symbols as both index and columns)
        """
        if not price_data:
            logger.warning("Empty price data provided")
            return pd.DataFrame()

        # Extract log-returns for each symbol
        log_returns: dict[str, pd.Series] = {}

        for symbol, df in price_data.items():
            if df.empty or "close" not in df.columns:
                logger.warning(f"Invalid data for {symbol}, skipping")
                continue

            # Filter to lookback period
            df_filtered = self._filter_to_lookback(df)

            if len(df_filtered) < self._min_data_points:
                logger.debug(
                    f"Insufficient data for {symbol}: {len(df_filtered)} points"
                )
                continue

            # Compute log-returns
            close = df_filtered["close"]
            returns = np.log(close / close.shift(1)).dropna()

            if len(returns) >= self._min_data_points - 1:
                log_returns[symbol] = returns

        if len(log_returns) < 2:
            logger.warning("Need at least 2 symbols for correlation")
            return pd.DataFrame()

        # Align all series to common index
        returns_df = pd.DataFrame(log_returns)
        returns_df = returns_df.dropna()

        if len(returns_df) < self._min_data_points - 1:
            logger.warning(
                f"Insufficient overlapping data: {len(returns_df)} points"
            )
            return pd.DataFrame()

        # Compute correlation matrix
        self._correlation_matrix = returns_df.corr(method="pearson")
        self._symbols = list(self._correlation_matrix.columns)

        logger.debug(
            f"Built correlation matrix for {len(self._symbols)} symbols "
            f"with {len(returns_df)} data points"
        )

        return self._correlation_matrix

    def get_correlated_pairs(
        self,
        symbol: str,
        threshold: float | None = None,
    ) -> list[CorrelationResult]:
        """Get pairs correlated with a symbol above threshold.

        Args:
            symbol: Symbol to find correlations for
            threshold: Correlation threshold (default: high_correlation_threshold)

        Returns:
            List of CorrelationResult for pairs above threshold,
            sorted by absolute correlation (descending)
        """
        if self._correlation_matrix is None or self._correlation_matrix.empty:
            logger.warning("No correlation matrix built")
            return []

        if symbol not in self._symbols:
            logger.warning(f"Symbol {symbol} not in correlation matrix")
            return []

        threshold = threshold if threshold is not None else self._high_threshold
        results: list[CorrelationResult] = []

        for other_symbol in self._symbols:
            if other_symbol == symbol:
                continue

            corr = self._correlation_matrix.loc[symbol, other_symbol]

            if abs(corr) >= threshold:
                results.append(
                    CorrelationResult(
                        symbol1=symbol,
                        symbol2=other_symbol,
                        correlation=float(corr),
                        data_points=len(self._correlation_matrix),
                    )
                )

        # Sort by absolute correlation descending
        results.sort(key=lambda x: abs(x.correlation), reverse=True)

        return results

    def get_correlation(self, symbol1: str, symbol2: str) -> float | None:
        """Get correlation between two symbols.

        Args:
            symbol1: First symbol
            symbol2: Second symbol

        Returns:
            Correlation coefficient or None if not available
        """
        if self._correlation_matrix is None or self._correlation_matrix.empty:
            return None

        if symbol1 not in self._symbols or symbol2 not in self._symbols:
            return None

        return float(self._correlation_matrix.loc[symbol1, symbol2])

    def get_average_correlation(self, symbol: str) -> float | None:
        """Get average absolute correlation for a symbol.

        Computes the mean of absolute correlation values between
        the given symbol and all other symbols in the matrix.

        Args:
            symbol: Symbol to compute average correlation for

        Returns:
            Average absolute correlation or None if not available
        """
        if self._correlation_matrix is None or self._correlation_matrix.empty:
            return None

        if symbol not in self._symbols:
            return None

        # Get correlations with all other symbols
        correlations = self._correlation_matrix.loc[symbol]

        # Exclude self-correlation (always 1.0)
        other_correlations = correlations.drop(symbol)

        if other_correlations.empty:
            return None

        # Return average of absolute values
        return float(np.abs(other_correlations).mean())

    def is_highly_correlated(self, symbol1: str, symbol2: str) -> bool:
        """Check if two symbols are highly correlated.

        Args:
            symbol1: First symbol
            symbol2: Second symbol

        Returns:
            True if absolute correlation >= high_correlation_threshold
        """
        corr = self.get_correlation(symbol1, symbol2)
        if corr is None:
            return False
        return abs(corr) >= self._high_threshold

    def _filter_to_lookback(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filter DataFrame to lookback period.

        Args:
            df: DataFrame with datetime index

        Returns:
            Filtered DataFrame containing only data within lookback period
        """
        if df.empty:
            return df

        # Get the latest timestamp
        latest = df.index.max()

        # Calculate cutoff time
        cutoff = latest - pd.Timedelta(hours=self._lookback_hours)

        return df[df.index >= cutoff]
