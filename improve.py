
from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config.json"
EVALUATION = ROOT / "reports" / "evaluation_summary.csv"
OUTPUT = ROOT / "reports" / "improvement_review.md"


def main():
    with CONFIG.open("r", encoding="utf-8") as f:
        cfg = json.load(f)

    lines = [
        "# Automated Improvement Review",
        "",
        "This report reviews historical outcomes.",
        "It does not automatically change strategy rules.",
        "",
    ]

    if not EVALUATION.exists():
        lines.append(
            "No evaluation file found. "
            "Collect prediction history first."
        )
    else:
        df = pd.read_csv(EVALUATION)

        lines.append(
            f"- Evaluated observations: {len(df)}"
        )

        for column in (
            "return_1d",
            "return_5d",
            "return_20d",
        ):
            if column not in df.columns:
                continue

            values = pd.to_numeric(
                df[column], errors="coerce"
            ).dropna()

            if values.empty:
                continue

            lines.append(
                f"- {column}: "
                f"n={len(values)}, "
                f"mean={values.mean():.4f}, "
                f"median={values.median():.4f}, "
                f"win_rate={(values > 0).mean():.3f}"
            )

        minimum = int(
            cfg["evaluation"]["minimum_predictions_for_review"]
        )

        lines.extend(["", "## Review decision", ""])

        if len(df) < minimum:
            lines.append(
                f"Insufficient observations: {len(df)} "
                f"of {minimum} required."
            )
            lines.append(
                "Do not change scoring weights yet."
            )
        else:
            lines.append(
                "Review results against a benchmark, "
                "transaction costs, drawdowns, and "
                "a separate out-of-sample period."
            )
            lines.append(
                "These statistics alone do not establish "
                "a profitable trading strategy."
            )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    print(f"Saved improvement review: {OUTPUT}")


if __name__ == "__main__":
    main()
