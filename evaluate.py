
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent
HISTORY = ROOT / "data" / "prediction_history.csv"
OUT = ROOT / "reports" / "evaluation_summary.csv"


def get_close(symbol, start, end):
    try:
        df = yf.download(
            symbol,
            start=start,
            end=end,
            auto_adjust=True,
            progress=False,
            threads=False,
        )
        if df is None or df.empty:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        if "Close" not in df.columns:
            return None

        return df["Close"].dropna()

    except Exception as exc:
        print(f"[WARN] {symbol}: {exc}")
        return None


def main():
    if not HISTORY.exists():
        print("No prediction history yet. Skipping evaluation.")
        return

    history = pd.read_csv(HISTORY)

    if history.empty:
        print("Prediction history is empty.")
        return

    results = []

    for _, row in history.iterrows():
        symbol = str(row["symbol"])
        as_of = str(row["as_of"])
        base_price = float(row["close"])

        if not np.isfinite(base_price) or base_price <= 0:
            continue

        start_date = pd.Timestamp(as_of)
        end_date = start_date + pd.Timedelta(days=60)

        close = get_close(
            symbol,
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
        )

        if close is None or close.empty:
            continue

        dates = pd.DatetimeIndex(close.index)
        if dates.tz is not None:
            dates = dates.tz_localize(None)

        future_positions = np.where(
            dates > start_date
        )[0]

        if len(future_positions) == 0:
            continue

        first = int(future_positions[0])

        result = {
            "symbol": symbol,
            "as_of": as_of,
            "score": row.get("score"),
            "base_price": base_price,
        }

        for days in (1, 5, 20):
            pos = first + days - 1

            if pos < len(close):
                future_price = float(close.iloc[pos])
                result[f"return_{days}d"] = (
                    future_price / base_price - 1
                )
            else:
                result[f"return_{days}d"] = np.nan

        results.append(result)

    OUT.parent.mkdir(parents=True, exist_ok=True)

    columns = [
        "symbol", "as_of", "score", "base_price",
        "return_1d", "return_5d", "return_20d",
    ]

    df = pd.DataFrame(results, columns=columns)
    df.to_csv(OUT, index=False)

    print(f"Saved evaluation results: {OUT}")
    print(f"Evaluated observations: {len(df)}")

    if not df.empty:
        print(
            df[["return_1d", "return_5d", "return_20d"]]
            .describe()
            .to_string()
        )
    else:
        print("No matured predictions available yet.")


if __name__ == "__main__":
    main()
