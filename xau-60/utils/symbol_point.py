"""Symbol point size helpers for strategy pip/SL calculations."""


def symbol_point(symbol: str) -> float:
    """Approximate price point by instrument type (fallback when MT5 info unavailable)."""
    upper = (symbol or "").upper()
    if "XAU" in upper or "GOLD" in upper:
        return 0.1
    if any(tag in upper for tag in ("ETH", "BTC", "LTC", "XRP", "SOL")):
        return 0.01
    return 0.0001
