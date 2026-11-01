from pathlib import Path
import numpy as np
import pandas as pd
try:
    import yfinance as yf
except ImportError:
    yf = None

ROOT = Path(__file__).resolve().parent
HISTORY = ROOT / "data" / "prediction_history.csv"
OUT = ROOT / "reports" / "evaluation_summary.csv"


def get_close(symbol, start, end):
    if yf is None:
        print("[WARN] yfinance is not installed; cannot download evaluation data")
        return None
    try:
        df = yf.download(symbol, start=start, end=end, auto_adjust=True, progress=False, threads=False)
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df["Close"].dropna() if "Close" in df else None
    except Exception as exc:
        print(f"[WARN] evaluation download failed for {symbol}: {exc}")
        return None


def future_returns(close, as_of, base, horizons):
    if close is None or close.empty:
        return {f"return_{n}d": np.nan for n in horizons}
    dates = pd.DatetimeIndex(close.index)
    if dates.tz is not None:
        dates = dates.tz_localize(None)
    positions = np.where(dates > pd.Timestamp(as_of))[0]
    if not len(positions):
        return {f"return_{n}d": np.nan for n in horizons}
    first = int(positions[0])
    out = {}
    for n in horizons:
        pos = first + n - 1
        out[f"return_{n}d"] = float(close.iloc[pos]) / float(base) - 1 if pos < len(close) else np.nan
    return out


def main():
    if not HISTORY.exists():
        print("No prediction history yet.")
        return
    hist = pd.read_csv(HISTORY)
    if hist.empty:
        print("Prediction history is empty.")
        return
    cfg_path = ROOT / "config.json"
    import json
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    horizons = tuple(int(n) for n in cfg.get("evaluation", {}).get("forward_days", [1, 5, 20, 60]))
    benchmark_us = cfg.get("evaluation", {}).get("benchmark_us", "SPY")
    benchmark_jp = cfg.get("evaluation", {}).get("benchmark_jp", "1306.T")
    rows = []
    benchmark_cache = {}
    for _, r in hist.iterrows():
        symbol, as_of = str(r["symbol"]), str(r["as_of"])
        base = pd.to_numeric(pd.Series([r.get("close")]), errors="coerce").iloc[0]
        if not np.isfinite(base) or base <= 0:
            continue
        end = (pd.Timestamp(as_of) + pd.Timedelta(days=max(horizons) * 2 + 20)).strftime("%Y-%m-%d")
        close = get_close(symbol, as_of, end)
        rec = {"symbol": symbol, "as_of": as_of, "score": r.get("score"), "base_price": base}
        rec.update(future_returns(close, as_of, base, horizons))
        benchmark = benchmark_jp if symbol.endswith(".T") else benchmark_us
        cache_key = (benchmark, as_of, end)
        if cache_key not in benchmark_cache:
            benchmark_close = get_close(benchmark, as_of, end)
            benchmark_base = np.nan
            if benchmark_close is not None and not benchmark_close.empty:
                idx = pd.DatetimeIndex(benchmark_close.index)
                if idx.tz is not None:
                    idx = idx.tz_localize(None)
                prior_or_same = np.where(idx <= pd.Timestamp(as_of))[0]
                if len(prior_or_same):
                    benchmark_base = float(benchmark_close.iloc[int(prior_or_same[-1])])
            benchmark_cache[cache_key] = (benchmark_close, benchmark_base)
        benchmark_close, benchmark_base = benchmark_cache[cache_key]
        rec["benchmark_symbol"] = benchmark
        if np.isfinite(benchmark_base) and benchmark_base > 0:
            br = future_returns(benchmark_close, as_of, benchmark_base, horizons)
            for n in horizons:
                rec[f"benchmark_return_{n}d"] = br[f"return_{n}d"]
                a, b = rec.get(f"return_{n}d", np.nan), br[f"return_{n}d"]
                rec[f"excess_return_{n}d"] = a - b if pd.notna(a) and pd.notna(b) else np.nan
        else:
            for n in horizons:
                rec[f"benchmark_return_{n}d"] = np.nan
                rec[f"excess_return_{n}d"] = np.nan
        rows.append(rec)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    columns = ["symbol", "as_of", "score", "base_price", "benchmark_symbol"]
    for n in horizons:
        columns.extend([f"return_{n}d", f"benchmark_return_{n}d", f"excess_return_{n}d"])
    df = pd.DataFrame(rows, columns=columns)
    df.to_csv(OUT, index=False)
    if df.empty:
        print("No observations have future bars available yet.")
        return
    print(f"Saved {OUT}; observations={len(df)}")
    for n in horizons:
        for col in (f"return_{n}d", f"excess_return_{n}d"):
            vals = pd.to_numeric(df[col], errors="coerce").dropna()
            if len(vals):
                print(f"{col}: n={len(vals)} mean={vals.mean():.4f} median={vals.median():.4f} win_rate={(vals > 0).mean():.3f}")


if __name__ == "__main__":
    main()
