# Automated improvement review

This is an evidence summary, not an automatic strategy change.
The system does not silently rewrite scoring weights.

- Evaluated observations: 138
- return_1d: n=107, mean=-0.0283, median=-0.0242, win rate=0.271, worst=-0.1706
- excess_return_1d: n=107, mean=-0.0277, median=-0.0243, win rate=0.299, worst=-0.1745

## Decision gate

Sample-size threshold reached for a preliminary review only.
Before changing weights, compare against market benchmarks, account for costs/slippage, check drawdowns, and use walk-forward/out-of-sample validation.

## Known limitations

- Excess returns compare with SPY for US tickers and 1306.T for Japanese tickers where benchmark data is available.
- Rows are not necessarily independent observations; the same ticker appears on multiple dates.
- Yahoo Finance data is a third-party source and can be incomplete.
- Survivorship bias and universe selection can materially inflate apparent performance.
- No profitability or predictive edge is established by this report.
