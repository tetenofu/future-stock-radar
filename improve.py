from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parent
CFG = ROOT / "config.json"
EVAL = ROOT / "reports" / "evaluation_summary.csv"
OUT = ROOT / "reports" / "improvement_review.md"


def main():
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    minimum = int(cfg.get("evaluation", {}).get("minimum_predictions_for_review", 30))
    lines = ["# Automated improvement review", "", "This is an evidence summary, not an automatic strategy change.", "The system does not silently rewrite scoring weights.", ""]
    if not EVAL.exists():
        lines.append("No evaluation file exists yet. Run the radar daily and wait for future bars to mature.")
    else:
        df = pd.read_csv(EVAL)
        lines.append(f"- Evaluated observations: {len(df)}")
        for col in ["return_1d", "return_5d", "return_20d", "return_60d", "excess_return_1d", "excess_return_5d", "excess_return_20d", "excess_return_60d"]:
            if col not in df:
                continue
            s = pd.to_numeric(df[col], errors="coerce").dropna()
            if len(s):
                lines.append(f"- {col}: n={len(s)}, mean={s.mean():.4f}, median={s.median():.4f}, win rate={(s > 0).mean():.3f}, worst={s.min():.4f}")
        lines += ["", "## Decision gate", ""]
        if len(df) < minimum:
            lines.append(f"Insufficient sample: {len(df)} observations; {minimum} required before a human review.")
        else:
            lines += ["Sample-size threshold reached for a preliminary review only.", "Before changing weights, compare against market benchmarks, account for costs/slippage, check drawdowns, and use walk-forward/out-of-sample validation."]
    lines += ["", "## Known limitations", "", "- Excess returns compare with SPY for US tickers and 1306.T for Japanese tickers where benchmark data is available.", "- Rows are not necessarily independent observations; the same ticker appears on multiple dates.", "- Yahoo Finance data is a third-party source and can be incomplete.", "- Survivorship bias and universe selection can materially inflate apparent performance.", "- No profitability or predictive edge is established by this report.", ""]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
