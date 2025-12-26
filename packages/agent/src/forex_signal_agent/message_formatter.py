"""
Telegram message formatters for probability signals and volatility alerts.

Provides Markdown-formatted messages for the new probabilistic analysis system.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .analysis.analyzer_v2 import AnalysisEvent


# Direction names in Russian
DIRECTION_NAMES = {
    "upward": "Рост",
    "downward": "Падение",
    "consolidation": "Консолидация",
}

# Direction emojis
DIRECTION_EMOJIS = {
    "upward": "📈",
    "downward": "📉",
    "consolidation": "➡️",
}

# Volatility regime names in Russian
REGIME_NAMES = {
    "low": "Низкая волатильность",
    "normal": "Нормальная волатильность",
    "high": "Высокая волатильность",
    "extreme": "Экстремальная волатильность",
}

# Sentiment names and emojis
SENTIMENT_NAMES = {
    "risk_on": "Risk-On",
    "risk_off": "Risk-Off",
    "neutral": "Нейтральный",
}

SENTIMENT_EMOJIS = {
    "risk_on": "🟢",
    "risk_off": "🔴",
    "neutral": "⚪",
}


def _confidence_bar(confidence: float) -> str:
    """
    Generate a 5-character visual confidence bar.

    Args:
        confidence: Confidence value (0-1)

    Returns:
        5-character string representing confidence level
    """
    filled = int(round(confidence * 5))
    filled = max(0, min(5, filled))
    return "█" * filled + "░" * (5 - filled)


def format_probability_signal(event: "AnalysisEvent") -> str:
    """
    Format probability signal event as Telegram Markdown message.

    Args:
        event: AnalysisEvent with PROBABILITY_SIGNAL type

    Returns:
        Markdown-formatted message string
    """
    data = event.data
    direction = data.get("direction", "consolidation")
    confidence = data.get("confidence", 0.0)
    probabilities = data.get("probabilities", {})
    is_actionable = data.get("is_actionable", False)

    emoji = DIRECTION_EMOJIS.get(direction, "➡️")
    direction_name = DIRECTION_NAMES.get(direction, direction)
    confidence_bar = _confidence_bar(confidence)

    lines = [
        f"{emoji} *{event.symbol}* ({event.timeframe})",
        f"Направление: *{direction_name}*",
        f"Уверенность: `{confidence_bar}` ({confidence:.0%})",
        "",
        "📊 *Вероятности:*",
    ]

    # Add probabilities in order: upward, downward, consolidation
    prob_order = ["upward", "downward", "consolidation"]
    for prob_key in prob_order:
        if prob_key in probabilities:
            prob_value = probabilities[prob_key]
            prob_name = DIRECTION_NAMES.get(prob_key, prob_key)
            prob_emoji = DIRECTION_EMOJIS.get(prob_key, "")
            lines.append(f"  {prob_emoji} {prob_name}: {prob_value:.1%}")

    # Add market context section if available
    market_sentiment = data.get("market_sentiment")
    market_reasoning = data.get("market_reasoning")

    if market_sentiment:
        sentiment_emoji = SENTIMENT_EMOJIS.get(market_sentiment, "⚪")
        sentiment_name = SENTIMENT_NAMES.get(market_sentiment, market_sentiment)
        lines.append("")
        lines.append(f"{sentiment_emoji} *Контекст:* {sentiment_name}")

        if market_reasoning:
            lines.append(f"  _{market_reasoning}_")

    if is_actionable:
        lines.append("")
        lines.append("✅ *Сигнал к действию*")

    return "\n".join(lines)


def format_volatility_alert(event: "AnalysisEvent") -> str:
    """
    Format volatility alert event as Telegram Markdown message.

    Args:
        event: AnalysisEvent with VOLATILITY_ALERT type

    Returns:
        Markdown-formatted message string
    """
    data = event.data
    regime = data.get("regime", "normal")
    atr_percent = data.get("atr_percent", 0.0)
    is_consolidation = data.get("is_consolidation", False)

    # Emoji based on regime
    emoji = "🔥" if regime == "extreme" else "⚠️"
    regime_name = REGIME_NAMES.get(regime, regime)

    lines = [
        f"{emoji} *{event.symbol}* ({event.timeframe})",
        f"Режим: *{regime_name}*",
        f"ATR: {atr_percent:.2%}",
    ]

    if is_consolidation:
        lines.append("")
        lines.append("📊 Рынок в консолидации")

    return "\n".join(lines)
