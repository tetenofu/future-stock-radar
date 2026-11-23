# Automated improvement review

This is an evidence summary, not an automatic strategy change.
The system does not silently rewrite scoring weights.

- Evaluated observations: 451
- return_1d: n=420, mean=-0.0211, median=-0.0191, win rate=0.319, worst=-0.2146
- return_5d: n=296, mean=-0.0457, median=-0.0453, win rate=0.341, worst=-0.3837
- excess_return_1d: n=420, mean=-0.0157, median=-0.0150, win rate=0.340, worst=-0.1745
- excess_return_5d: n=296, mean=-0.0290, median=-0.0294, win rate=0.399, worst=-0.3493

## Decision gate

Sample-size threshold reached for a preliminary review only.
Before changing weights, compare against market benchmarks, account for costs/slippage, check drawdowns, and use walk-forward/out-of-sample validation.

## Known limitations

- Excess returns compare with SPY for US tickers and 1306.T for Japanese tickers where benchmark data is available.
- Rows are not necessarily independent observations; the same ticker appears on multiple dates.
- Yahoo Finance data is a third-party source and can be incomplete.
- Survivorship bias and universe selection can materially inflate apparent performance.
- No profitability or predictive edge is established by this report.
