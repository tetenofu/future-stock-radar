# Automated improvement review

This is an evidence summary, not an automatic strategy change.
The system does not silently rewrite scoring weights.

- Evaluated observations: 48
- return_1d: n=17, mean=0.0043, median=0.0039, win rate=0.588, worst=-0.0277
- excess_return_1d: n=17, mean=-0.0017, median=-0.0021, win rate=0.471, worst=-0.0337

## Decision gate

Sample-size threshold reached for a preliminary review only.
Before changing weights, compare against market benchmarks, account for costs/slippage, check drawdowns, and use walk-forward/out-of-sample validation.

## Known limitations

- Excess returns compare with SPY for US tickers and 1306.T for Japanese tickers where benchmark data is available.
- Rows are not necessarily independent observations; the same ticker appears on multiple dates.
- Yahoo Finance data is a third-party source and can be incomplete.
- Survivorship bias and universe selection can materially inflate apparent performance.
- No profitability or predictive edge is established by this report.
