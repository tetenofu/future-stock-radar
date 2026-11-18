# Automated improvement review

This is an evidence summary, not an automatic strategy change.
The system does not silently rewrite scoring weights.

- Evaluated observations: 358
- return_1d: n=327, mean=-0.0177, median=-0.0184, win rate=0.324, worst=-0.2146
- return_5d: n=217, mean=-0.0124, median=-0.0189, win rate=0.456, worst=-0.3837
- excess_return_1d: n=327, mean=-0.0130, median=-0.0136, win rate=0.352, worst=-0.1745
- excess_return_5d: n=217, mean=-0.0086, median=-0.0089, win rate=0.456, worst=-0.3493

## Decision gate

Sample-size threshold reached for a preliminary review only.
Before changing weights, compare against market benchmarks, account for costs/slippage, check drawdowns, and use walk-forward/out-of-sample validation.

## Known limitations

- Excess returns compare with SPY for US tickers and 1306.T for Japanese tickers where benchmark data is available.
- Rows are not necessarily independent observations; the same ticker appears on multiple dates.
- Yahoo Finance data is a third-party source and can be incomplete.
- Survivorship bias and universe selection can materially inflate apparent performance.
- No profitability or predictive edge is established by this report.
