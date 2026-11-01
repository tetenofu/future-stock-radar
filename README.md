# Future Stock Radar — Integrated Free Research Pipeline

日本株・米国株の候補抽出、テクニカル採点、利用可能な範囲での財務情報・見出しの取得、担当別レビュー、予測結果の評価、改善レポートを日次実行するための研究用パイプラインです。

## Included
- `radar.py`: existing rules-based technical radar and daily prediction history.
- `agents/research.py`: best-effort Yahoo Finance summary fundamentals, headline retrieval, heuristic specialist roles, risk flags, and optional local Ollama review.
- `evaluate.py`: 1/5/20/60 trading-bar forward returns once future data is available.
- `improve.py`: performance summaries and validation gates; never silently changes production weights.
- `.github/workflows/daily-radar.yml`: weekday scheduled run plus manual dispatch.
- `prompts/agents.md`: reusable prompts for deeper manual or local-model analysis.

## Important truth about “AI agents”
The GitHub-hosted workflow does **not** have a general free LLM API. By default, specialist roles are transparent heuristic checks, not independent language-model agents. A real LLM review is optional through Ollama, but GitHub-hosted runners cannot reach Ollama running on your home PC. To use Ollama, run the pipeline on the same machine/network as Ollama and set `agents.local_ollama_enabled` to `true`; install and pull the configured model first.

## Limitations
1. `yfinance` is an unofficial third-party data interface. Summary fields and news may be missing, delayed, changed, or incorrect.
2. The default universe is only a small watchlist, not a comprehensive market-wide scanner. Broaden it only after validating symbol coverage and runtime.
3. The technical `score` is the original rules-based score, not a probability, forecast, fair value, or buy signal.
4. `research_score` averages available technical, growth, quality and valuation heuristics. It is a triage aid, not a validated predictive model; missing fields are excluded, not assumed to be zero.
5. News headlines are not equivalent to official IR. Verify catalysts against company filings and official releases.
6. No trading, brokerage integration, position sizing, or automatic weight changes are included.
7. Backtests can be misleading due to look-ahead bias, survivorship bias, universe selection, overlapping observations, costs and slippage. Results do not guarantee profitability.
8. Free GitHub Actions has usage limits; scheduled executions can be delayed. This workflow is scheduled for 07:17 UTC (16:17 JST) Monday–Friday.

## Setup in GitHub
1. Download and extract this ZIP.
2. Copy **the contents** of `future-stock-radar-integrated` into the root of your existing `future-stock-radar` repository, preserving paths and replacing files when prompted.
3. Commit and push all files to `main`.
4. Open Actions and run `Daily Stock Radar` manually once.
5. Confirm every step is green. Check `data/latest_watchlist.csv`, `reports/latest_research_candidates.csv`, `reports/agent_review.md`, `reports/evaluation_summary.csv`, and `reports/improvement_review.md`.
6. Confirm the workflow has a `schedule` trigger. The schedule only runs when GitHub Actions is enabled and repository usage limits allow it.

## Local test
```bash
python -m pip install -r requirements.txt
python -m pytest -q
python radar.py
python evaluate.py
python improve.py
```

## Generated outputs
- `data/radar_YYYYMMDD.csv`: technical rankings.
- `data/latest_watchlist.csv`: current technical watchlist.
- `data/prediction_history.csv`: score snapshots used for evaluation.
- `reports/latest_top_candidates.csv`: technical top candidates.
- `reports/research_enrichment.csv`: best-effort financial summary and research scores.
- `reports/latest_research_candidates.csv`: top enriched candidates.
- `reports/agent_review.md`: role-based review, risk notes and headlines.
- `reports/evaluation_summary.csv`: forward-return observations.
- `reports/improvement_review.md`: evidence summary and decision gate.

## Safe improvement protocol
Do not change scoring weights just because a short period looks good. Require a broad-market benchmark, realistic costs/slippage, walk-forward validation, a separate out-of-sample period, drawdown/tail-risk analysis, and a record of the prior configuration. Automated reports can inform review but do not prove an edge.
