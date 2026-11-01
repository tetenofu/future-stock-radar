from __future__ import annotations
import json, os, math, time
from datetime import datetime, timezone
from pathlib import Path
from agents.research import enrich_universe, write_agent_reviews
import numpy as np
import pandas as pd
try:
    import yfinance as yf
except ImportError:  # allows offline unit tests; runtime data downloads still require yfinance
    yf = None

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
REPORTS = ROOT / "reports"
HISTORY = DATA / "prediction_history.csv"
CONFIG_PATH = ROOT / "config.json"

def load_config():
    if not CONFIG_PATH.exists():
        raise FileNotFoundError("config.json is missing. Restore it from the repository root.")
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)

def symbols_from_config(cfg):
    u = cfg["universe"]
    syms = list(dict.fromkeys(u.get("us_symbols", []) + u.get("jp_symbols", [])))
    limit = int(u.get("max_symbols_per_run", 250))
    return syms[:limit]

def download_history(symbol, period="2y"):
    if yf is None:
        print("[WARN] yfinance is not installed; cannot download market data")
        return None
    try:
        df = yf.download(symbol, period=period, auto_adjust=True, progress=False, threads=False)
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        required = {"Close", "Volume"}
        if not required.issubset(set(df.columns)):
            return None
        df = df[["Close", "Volume"]].copy()
        df = df.dropna(subset=["Close"])
        df = df[~df.index.duplicated(keep="last")]
        return df if len(df) >= 30 else None
    except Exception as exc:
        print(f"[WARN] download failed {symbol}: {exc}")
        return None

def safe_pct(series, periods):
    if len(series) <= periods or pd.isna(series.iloc[-periods-1]) or series.iloc[-periods-1] == 0:
        return np.nan
    return float(series.iloc[-1] / series.iloc[-periods-1] - 1)

def score_symbol(symbol, df, cfg):
    s = df["Close"].astype(float).dropna()
    vol = df["Volume"].fillna(0).astype(float)
    min_rows = int(cfg["screening"]["min_history_rows"])
    if len(s) < min_rows:
        return None
    last = float(s.iloc[-1])
    if not np.isfinite(last) or last <= 0:
        return None

    ret_1m = safe_pct(s, 21)
    ret_3m = safe_pct(s, int(cfg["screening"]["momentum_period_days"]))
    ma20 = float(s.tail(20).mean())
    ma50 = float(s.tail(50).mean())
    ma200 = float(s.tail(200).mean()) if len(s) >= 200 else np.nan
    daily = s.pct_change().dropna()
    vol20 = float(daily.tail(20).std() * np.sqrt(252)) if len(daily) >= 20 else np.nan
    peak_3m = float(s.tail(63).max())
    drawdown = (last / peak_3m - 1) if peak_3m else np.nan
    avgvol20 = float(vol.tail(20).mean()) if len(vol) >= 20 else 0
    avgvol5 = float(vol.tail(5).mean()) if len(vol) >= 5 else 0
    vol_ratio = avgvol5 / avgvol20 if avgvol20 > 0 else np.nan

    weights = cfg["scoring_weights"]
    parts = {}
    # Bounded, transparent rules-based signals; not an ML model or price prediction.
    parts["momentum_3m"] = 100 if pd.notna(ret_3m) and ret_3m >= .30 else 75 if pd.notna(ret_3m) and ret_3m >= .15 else 55 if pd.notna(ret_3m) and ret_3m >= 0 else 25 if pd.notna(ret_3m) and ret_3m > -.15 else 0
    parts["momentum_1m"] = 100 if pd.notna(ret_1m) and ret_1m >= .10 else 75 if pd.notna(ret_1m) and ret_1m >= .03 else 50 if pd.notna(ret_1m) and ret_1m >= 0 else 20 if pd.notna(ret_1m) and ret_1m > -.10 else 0
    parts["trend"] = 100 if last > ma20 > ma50 and (pd.isna(ma200) or ma50 > ma200) else 60 if last > ma20 else 25 if last > ma50 else 0
    parts["volume_confirmation"] = 100 if pd.notna(vol_ratio) and vol_ratio >= 1.5 else 75 if pd.notna(vol_ratio) and vol_ratio >= 1.1 else 50 if pd.notna(vol_ratio) and vol_ratio >= .8 else 20
    parts["volatility_quality"] = 100 if pd.notna(vol20) and vol20 <= .35 else 70 if pd.notna(vol20) and vol20 <= .60 else 35 if pd.notna(vol20) and vol20 <= .90 else 0
    parts["drawdown_quality"] = 100 if pd.notna(drawdown) and drawdown >= -.05 else 75 if pd.notna(drawdown) and drawdown >= -.12 else 45 if pd.notna(drawdown) and drawdown >= -.20 else 15
    parts["liquidity"] = 100 if avgvol20 >= 1_000_000 else 75 if avgvol20 >= 250_000 else 50 if avgvol20 >= float(cfg["screening"]["min_average_volume_20d"]) else 0
    parts["data_quality"] = 100 if len(s) >= 200 and s.tail(20).notna().mean() >= .98 else 70 if len(s) >= min_rows else 0
    total_weight = sum(float(weights[k]) for k in parts)
    score = sum(parts[k] * float(weights[k]) for k in parts) / total_weight if total_weight else 0
    recent_daily = float(daily.iloc[-1]) if len(daily) else np.nan
    if pd.notna(recent_daily) and abs(recent_daily) > float(cfg["screening"]["max_abs_daily_return"]):
        quality_flag = "CHECK_EXTREME_MOVE"
    else:
        quality_flag = "OK"

    return {
        "symbol": symbol, "as_of": str(s.index[-1].date()), "close": round(last, 4),
        "return_1m": round(ret_1m, 4) if pd.notna(ret_1m) else None,
        "return_3m": round(ret_3m, 4) if pd.notna(ret_3m) else None,
        "ma20": round(ma20, 4), "ma50": round(ma50, 4),
        "ma200": round(ma200, 4) if pd.notna(ma200) else None,
        "annualized_volatility_20d": round(vol20, 4) if pd.notna(vol20) else None,
        "drawdown_from_63d_high": round(drawdown, 4) if pd.notna(drawdown) else None,
        "volume_ratio_5d_to_20d": round(vol_ratio, 3) if pd.notna(vol_ratio) else None,
        "average_volume_20d": round(avgvol20, 0),
        "score": round(score, 2), "quality_flag": quality_flag,
        "score_momentum_3m": parts["momentum_3m"], "score_momentum_1m": parts["momentum_1m"],
        "score_trend": parts["trend"], "score_volume": parts["volume_confirmation"],
        "score_volatility": parts["volatility_quality"], "score_drawdown": parts["drawdown_quality"],
        "score_liquidity": parts["liquidity"], "score_data_quality": parts["data_quality"],
        "method": "rules_v1_not_a_forecast"
    }

def append_prediction_history(ranked, as_of_run):
    if ranked.empty:
        return
    rows = ranked[["symbol", "as_of", "close", "score", "quality_flag"]].copy()
    rows["run_date"] = as_of_run
    rows["evaluated"] = False
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    if HISTORY.exists():
        old = pd.read_csv(HISTORY)
        combined = pd.concat([old, rows], ignore_index=True)
    else:
        combined = rows
    combined = combined.drop_duplicates(subset=["symbol", "as_of"], keep="last")
    combined.to_csv(HISTORY, index=False)

def main():
    cfg = load_config()
    DATA.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    run_date = datetime.now(timezone.utc).date().isoformat()
    results = []
    symbols = symbols_from_config(cfg)
    print(f"Scanning {len(symbols)} configured symbols")
    for i, symbol in enumerate(symbols, 1):
        print(f"[{i}/{len(symbols)}] {symbol}")
        hist = download_history(symbol)
        if hist is None:
            print(f"[WARN] no usable data for {symbol}")
            continue
        row = score_symbol(symbol, hist, cfg)
        if row:
            results.append(row)

    if not results:
        raise RuntimeError("No symbols produced valid results. Check data source/network and config.")
    ranked = pd.DataFrame(results).sort_values(["score", "average_volume_20d"], ascending=False)
    ranked.insert(0, "rank", range(1, len(ranked) + 1))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    out = DATA / f"radar_{stamp}.csv"
    ranked.to_csv(out, index=False)
    ranked.head(int(cfg["screening"]["watchlist_size"])).to_csv(DATA / "latest_watchlist.csv", index=False)
    ranked.head(int(cfg["screening"]["top_candidates"])).to_csv(REPORTS / "latest_top_candidates.csv", index=False)
    append_prediction_history(ranked, run_date)
    # Optional enrichment is deliberately fault-tolerant: the technical radar remains available
    # if a provider has missing fields, rate limits, or temporary outages.
    try:
        enriched = enrich_universe(ranked, cfg)
        if not enriched.empty:
            enriched.to_csv(REPORTS / "research_enrichment.csv", index=False)
            write_agent_reviews(enriched, REPORTS / "agent_review.md", cfg)
            enriched.sort_values(["research_score", "score"], ascending=False).head(
                int(cfg["screening"]["top_candidates"])
            ).to_csv(REPORTS / "latest_research_candidates.csv", index=False)
    except Exception as exc:
        print(f"[WARN] enrichment failed; technical radar still saved: {exc}")
    print(f"Wrote {out}; valid symbols={len(ranked)}")
    print(ranked.head(10)[["rank", "symbol", "close", "score", "quality_flag"]].to_string(index=False))

if __name__ == "__main__":
    main()
