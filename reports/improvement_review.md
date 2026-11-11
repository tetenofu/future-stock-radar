# Automated improvement review

This is an evidence summary, not an automatic strategy change.
The system does not silently rewrite scoring weights.

- Evaluated observations: 231
- return_1d: n=200, mean=-0.0097, median=-0.0113, win rate=0.415, worst=-0.2146
- return_5d: n=107, mean=-0.0212, median=-0.0079, win rate=0.486, worst=-0.3837
- excess_return_1d: n=200, mean=-0.0068, median=-0.0075, win rate=0.440, worst=-0.1745
- excess_return_5d: n=107, mean=-0.0086, median=0.0087, win rate=0.514, worst=-0.3493

## Decision gate

Sample-size threshold reached for a preliminary review only.
Before changing weights, compare against market benchmarks, account for costs/slippage, check drawdowns, and use walk-forward/out-of-sample validation.

## Known limitations

- Excess returns compare with SPY for US tickers and 1306.T for Japanese tickers where benchmark data is available.
- Rows are not necessarily independent observations; the same ticker appears on multiple dates.
- Yahoo Finance data is a third-party source and can be incomplete.
- Survivorship bias and universe selection can materially inflate apparent performance.
- No profitability or predictive edge is established by this report.
