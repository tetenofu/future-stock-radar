# Automated improvement review

This is an evidence summary, not an automatic strategy change.
The system does not silently rewrite scoring weights.

- Evaluated observations: 169
- return_1d: n=138, mean=-0.0242, median=-0.0262, win rate=0.297, worst=-0.2146
- return_5d: n=34, mean=0.0139, median=0.0172, win rate=0.559, worst=-0.1567
- excess_return_1d: n=138, mean=-0.0138, median=-0.0126, win rate=0.391, worst=-0.1745
- excess_return_5d: n=34, mean=0.0288, median=0.0297, win rate=0.647, worst=-0.1538

## Decision gate

Sample-size threshold reached for a preliminary review only.
Before changing weights, compare against market benchmarks, account for costs/slippage, check drawdowns, and use walk-forward/out-of-sample validation.

## Known limitations

- Excess returns compare with SPY for US tickers and 1306.T for Japanese tickers where benchmark data is available.
- Rows are not necessarily independent observations; the same ticker appears on multiple dates.
- Yahoo Finance data is a third-party source and can be incomplete.
- Survivorship bias and universe selection can materially inflate apparent performance.
- No profitability or predictive edge is established by this report.
