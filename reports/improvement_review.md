# Automated improvement review

This is an evidence summary, not an automatic strategy change.
The system does not silently rewrite scoring weights.

- Evaluated observations: 296
- return_1d: n=265, mean=-0.0138, median=-0.0151, win rate=0.358, worst=-0.2146
- return_5d: n=169, mean=0.0046, median=0.0095, win rate=0.521, worst=-0.3837
- excess_return_1d: n=265, mean=-0.0108, median=-0.0103, win rate=0.374, worst=-0.1745
- excess_return_5d: n=169, mean=0.0042, median=0.0062, win rate=0.515, worst=-0.3493

## Decision gate

Sample-size threshold reached for a preliminary review only.
Before changing weights, compare against market benchmarks, account for costs/slippage, check drawdowns, and use walk-forward/out-of-sample validation.

## Known limitations

- Excess returns compare with SPY for US tickers and 1306.T for Japanese tickers where benchmark data is available.
- Rows are not necessarily independent observations; the same ticker appears on multiple dates.
- Yahoo Finance data is a third-party source and can be incomplete.
- Survivorship bias and universe selection can materially inflate apparent performance.
- No profitability or predictive edge is established by this report.
