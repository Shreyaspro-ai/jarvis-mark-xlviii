"""
Delta Exchange market data + technical analysis for JARVIS.

READ-ONLY. This module only reads PUBLIC market data (candles, tickers) from
Delta Exchange India and computes technical analysis locally. It never places,
modifies, or cancels orders, and it needs no API key or account — it uses the
public market-data endpoints only. Purely for analysis.

Actions:
  analyze  (default) - full technical read on a symbol/timeframe:
                       price, trend (EMAs), RSI, MACD, ATR, swing high/low, bias.
  price / ticker      - quick spot price + 24h change for a symbol.

Symbols are Delta perpetuals like BTCUSD, ETHUSD, SOLUSD.
"""

import time
from urllib.parse import urlencode

try:
    import requests
    _REQUESTS_OK = True
except ImportError:
    _REQUESTS_OK = False

BASE_URL = "https://api.india.delta.exchange"

_HEADERS = {"Accept": "application/json", "User-Agent": "JARVIS/1.0 (analysis)"}

# Friendly timeframe words -> Delta resolution strings.
_TF_ALIASES = {
    "1m": "1m", "1min": "1m", "1minute": "1m", "1": "1m",
    "3m": "3m", "5m": "5m", "5min": "5m", "5minute": "5m", "5": "5m",
    "15m": "15m", "15min": "15m", "15minute": "15m", "15": "15m",
    "30m": "30m", "30min": "30m", "30": "30m",
    "1h": "1h", "1hr": "1h", "1hour": "1h", "hourly": "1h", "60": "1h",
    "2h": "2h", "4h": "4h", "6h": "6h", "12h": "12h",
    "1d": "1d", "1day": "1d", "daily": "1d", "day": "1d", "d": "1d",
    "1w": "1w", "1week": "1w", "weekly": "1w", "week": "1w", "w": "1w",
}

_RES_SECONDS = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "2h": 7200, "4h": 14400, "6h": 21600, "12h": 43200,
    "1d": 86400, "1w": 604800,
}


# ── symbol / timeframe normalisation ──────────────────────────────────────
def _norm_symbol(sym: str) -> str:
    if not sym:
        return "BTCUSD"
    s = sym.upper().replace(" ", "").replace("-", "").replace("/", "")
    # common spoken forms
    aliases = {
        "BTC": "BTCUSD", "BITCOIN": "BTCUSD", "BTCUSDT": "BTCUSD",
        "ETH": "ETHUSD", "ETHEREUM": "ETHUSD", "ETHUSDT": "ETHUSD",
        "SOL": "SOLUSD", "SOLANA": "SOLUSD", "SOLUSDT": "SOLUSD",
        "XRP": "XRPUSD", "RIPPLE": "XRPUSD",
        "DOGE": "DOGEUSD", "BNB": "BNBUSD", "AVAX": "AVAXUSD",
    }
    if s in aliases:
        return aliases[s]
    if not s.endswith("USD") and not s.endswith("USDT"):
        s = s + "USD"
    return s


def _norm_tf(tf: str) -> str:
    if not tf:
        return "1h"
    t = tf.lower().replace(" ", "")
    return _TF_ALIASES.get(t, t if t in _RES_SECONDS else "1h")


# ── data fetch ────────────────────────────────────────────────────────────
def _get(path: str, params: dict) -> dict:
    url = f"{BASE_URL}{path}?{urlencode(params)}"
    r = requests.get(url, headers=_HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()


def _fetch_candles(symbol: str, resolution: str, bars: int = 220) -> list[dict]:
    end = int(time.time())
    start = end - bars * _RES_SECONDS.get(resolution, 3600)
    data = _get("/v2/history/candles",
                {"resolution": resolution, "symbol": symbol,
                 "start": start, "end": end})
    rows = data.get("result", []) or []
    return sorted(rows, key=lambda c: c["time"])  # oldest-first


def _fetch_ticker(symbol: str) -> dict:
    data = _get(f"/v2/tickers/{symbol}", {})
    return data.get("result", {}) or {}


# ── indicators (pure python) ──────────────────────────────────────────────
def _ema(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    k = 2 / (period + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def _rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) <= period:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_g = (avg_g * (period - 1) + gains[i]) / period
        avg_l = (avg_l * (period - 1) + losses[i]) / period
    if avg_l == 0:
        return 100.0
    rs = avg_g / avg_l
    return 100 - (100 / (1 + rs))


def _macd(closes: list[float]) -> tuple[float, float, float] | None:
    if len(closes) < 35:
        return None
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd_line = [a - b for a, b in zip(ema12, ema26)]
    signal = _ema(macd_line, 9)
    return macd_line[-1], signal[-1], macd_line[-1] - signal[-1]


def _atr(candles: list[dict], period: int = 14) -> float | None:
    if len(candles) <= period:
        return None
    trs = []
    for i in range(1, len(candles)):
        h = candles[i]["high"]; l = candles[i]["low"]; pc = candles[i - 1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    atr = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period
    return atr


def _fmt(n: float) -> str:
    if n is None:
        return "n/a"
    if abs(n) >= 100:
        return f"{n:,.2f}"
    if abs(n) >= 1:
        return f"{n:,.3f}"
    return f"{n:.5f}"


# ── report builders ───────────────────────────────────────────────────────
def _analyze(symbol: str, tf: str) -> str:
    candles = _fetch_candles(symbol, tf, bars=220)
    if len(candles) < 40:
        return (f"Not enough candle data for {symbol} on {tf}, sir. "
                "The symbol may be wrong — try BTCUSD, ETHUSD, or SOLUSD.")

    closes = [c["close"] for c in candles]
    price = closes[-1]

    ema20 = _ema(closes, 20)[-1]
    ema50 = _ema(closes, 50)[-1]
    ema200 = _ema(closes, 200)[-1] if len(closes) >= 200 else None
    rsi = _rsi(closes, 14)
    macd = _macd(closes)
    atr = _atr(candles, 14)

    recent = candles[-50:]
    swing_high = max(c["high"] for c in recent)
    swing_low = min(c["low"] for c in recent)

    # --- bias scoring ---
    score = 0
    reasons = []
    if price > ema20:
        score += 1; reasons.append("price above EMA20")
    else:
        score -= 1; reasons.append("price below EMA20")
    if price > ema50:
        score += 1; reasons.append("above EMA50")
    else:
        score -= 1; reasons.append("below EMA50")
    if ema200 is not None:
        if price > ema200:
            score += 1; reasons.append("above EMA200 (macro up)")
        else:
            score -= 1; reasons.append("below EMA200 (macro down)")
    if rsi is not None:
        if rsi >= 70:
            reasons.append(f"RSI {rsi:.0f} overbought")
        elif rsi <= 30:
            reasons.append(f"RSI {rsi:.0f} oversold")
        else:
            reasons.append(f"RSI {rsi:.0f} neutral")
            score += 1 if rsi > 50 else -1
    if macd:
        if macd[2] > 0:
            score += 1; reasons.append("MACD bullish")
        else:
            score -= 1; reasons.append("MACD bearish")

    if score >= 2:
        bias = "BULLISH"
    elif score <= -2:
        bias = "BEARISH"
    else:
        bias = "NEUTRAL / RANGING"

    atr_pct = (atr / price * 100) if atr else None

    lines = [
        f"Technical read — {symbol} · {tf}",
        f"Price: {_fmt(price)}",
        f"Bias: {bias}  (score {score:+d})",
        f"EMAs: 20={_fmt(ema20)}  50={_fmt(ema50)}"
        + (f"  200={_fmt(ema200)}" if ema200 is not None else "  200=n/a"),
        f"RSI(14): {rsi:.1f}" if rsi is not None else "RSI(14): n/a",
    ]
    if macd:
        lines.append(f"MACD: {_fmt(macd[0])}  signal {_fmt(macd[1])}  hist {_fmt(macd[2])}")
    if atr is not None:
        lines.append(f"ATR(14): {_fmt(atr)}"
                     + (f"  ({atr_pct:.2f}% of price)" if atr_pct else ""))
    lines.append(f"Recent range (50 bars): {_fmt(swing_low)} — {_fmt(swing_high)}")
    lines.append("Read: " + ", ".join(reasons) + ".")
    lines.append("(Analysis only — not financial advice.)")
    return "\n".join(lines)


def _price(symbol: str) -> str:
    t = _fetch_ticker(symbol)
    if not t:
        return f"Couldn't fetch a price for {symbol}, sir."
    last = t.get("close") or t.get("mark_price") or t.get("spot_price")
    try:
        last = float(last)
    except (TypeError, ValueError):
        last = None
    chg = t.get("change_24h")
    parts = [f"{symbol}: {_fmt(last) if last else 'n/a'}"]
    if chg is not None:
        try:
            parts.append(f"({float(chg):+.2f}% 24h)")
        except (TypeError, ValueError):
            pass
    high = t.get("high"); low = t.get("low")
    if high and low:
        parts.append(f"24h range {_fmt(float(high))}–{_fmt(float(low))}")
    return " ".join(parts) + ". (Analysis only.)"


_ACTIONS = {"analyze": _analyze, "price": _price, "ticker": _price}


def delta_market(parameters: dict = None, response=None, player=None,
                 session_memory=None, speak=None) -> str:
    if not _REQUESTS_OK:
        return "The 'requests' package is required for market data. Run: pip install requests"

    p = parameters or {}
    action = (p.get("action", "analyze") or "analyze").lower().strip()
    symbol = _norm_symbol(p.get("symbol", "") or p.get("coin", ""))
    tf = _norm_tf(p.get("timeframe", "") or p.get("resolution", ""))

    if player:
        player.write_log(f"[delta] {action} {symbol} {tf}")

    try:
        if action in ("price", "ticker"):
            return _price(symbol)
        return _analyze(symbol, tf)
    except requests.HTTPError as e:
        return (f"Delta returned an error for {symbol} ({tf}): {e}. "
                "Check the symbol — try BTCUSD, ETHUSD, SOLUSD.")
    except Exception as e:
        return f"Market analysis failed, sir: {e}"
