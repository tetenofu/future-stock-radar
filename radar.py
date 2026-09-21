from __future__ import annotations

import csv
import json
import math
import re
import time
import traceback
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import feedparser
import pandas as pd
import requests
import yfinance as yf
from bs4 import BeautifulSoup
from dateutil import parser as dtparser

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
JST = ZoneInfo(CONFIG["timezone"])
TODAY = datetime.now(JST).date().isoformat()
UA = "future-stock-radar/4.0 (+https://github.com/)"


def na(v):
    return v is None or (isinstance(v, float) and math.isnan(v)) or str(v).strip() in {"", "NA", "N/A", "None", "nan"}


def num(v):
    if na(v):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(",", "").replace("%", "").strip()
    try:
        return float(s)
    except Exception:
        return None


def pct(a, b):
    a, b = num(a), num(b)
    if a is None or b is None or b <= 0:
        return None
    return (a / b - 1.0) * 100.0


def safe_ratio(a, b):
    a, b = num(a), num(b)
    if a is None or b is None or b == 0:
        return None
    return a / b


def fetch(url, timeout=20):
    r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
    r.raise_for_status()
    return r


@dataclass
class Company:
    name: str
    ticker: str
    market: str
    aliases: tuple[str, ...] = ()
    currency: str = ""


MASTER = [
    Company("NVIDIA Corporation", "NVDA", "US", ("NVIDIA", "Nvidia"), "USD"),
    Company("Advanced Micro Devices, Inc.", "AMD", "US", ("AMD", "Advanced Micro Devices"), "USD"),
    Company("Broadcom Inc.", "AVGO", "US", ("Broadcom",), "USD"),
    Company("Marvell Technology, Inc.", "MRVL", "US", ("Marvell",), "USD"),
    Company("Coherent Corp.", "COHR", "US", ("Coherent",), "USD"),
    Company("Lumentum Holdings Inc.", "LITE", "US", ("Lumentum",), "USD"),
    Company("Applied Materials, Inc.", "AMAT", "US", ("Applied Materials",), "USD"),
    Company("Amkor Technology, Inc.", "AMKR", "US", ("Amkor",), "USD"),
    Company("Cisco Systems, Inc.", "CSCO", "US", ("Cisco",), "USD"),
    Company("Intel Corporation", "INTC", "US", ("Intel",), "USD"),
    Company("Equinix, Inc.", "EQIX", "US", ("Equinix",), "USD"),
    Company("Aehr Test Systems", "AEHR", "US", ("Aehr", "Aehr Test Systems"), "USD"),
    Company("Corning Incorporated", "GLW", "US", ("Corning",), "USD"),
    Company("キオクシアホールディングス", "285A", "JP", ("キオクシア", "Kioxia"), "JPY"),
    Company("アドバンテスト", "6857", "JP", ("アドバンテスト", "Advantest"), "JPY"),
    Company("京セラ", "6971", "JP", ("京セラ", "Kyocera"), "JPY"),
    Company("NTT", "9432", "JP", ("NTT", "日本電信電話"), "JPY"),
    Company("NEC", "6701", "JP", ("NEC", "日本電気"), "JPY"),
    Company("三菱重工業", "7011", "JP", ("三菱重工", "Mitsubishi Heavy Industries"), "JPY"),
    Company("FIG", "4392", "JP", ("FIG",), "JPY"),
    Company("海帆", "3133", "JP", ("海帆",), "JPY"),
    Company("きくてっく", "3444", "JP", ("きくてっく", "菊池製作所"), "JPY"),
]

BY_ALIAS = {a.lower(): c for c in MASTER for a in c.aliases}


def resolve_entity(title: str, summary: str):
    text = f"{title} {summary}"
    hits = []
    for c in MASTER:
        aliases = sorted(c.aliases, key=len, reverse=True)
        for alias in aliases:
            if re.search(rf"(?<![\w]){re.escape(alias)}(?![\w])", text, re.I):
                hits.append(c)
                break

    if not hits:
        return None, 0.0, "未特定"

    # A company name appearing only in a generic market article is not enough.
    actor_words = r"(受注|発注|提携|協業|契約|投資|出資|買収|量産|生産|供給|採用|開発|特許|製造|工場|capacity|partnership|agreement|investment|order|production|supply|develop|manufactur|acqui)"
    actor = bool(re.search(actor_words, text, re.I))

    if len(hits) == 1 and actor:
        return hits[0], 0.92, "直接候補"
    if len(hits) == 1:
        return hits[0], 0.74, "関与候補"
    return None, 0.45, "複数候補・要確認"


def theme_of(title: str, summary: str):
    t = f"{title} {summary}".lower()
    rules = [
        ("光通信", [r"optical", r"silicon photonics", r"co-packaged optics", r"\bcpo\b", r"光通信", r"光接続", r"photonic"]),
        ("AIデータセンター", [r"ai data cent", r"ai factory", r"gpu cluster", r"ai infrastructure", r"データセンター"]),
        ("半導体", [r"semiconductor", r"chip", r"wafer", r"半導体", r"silicon"]),
        ("電力・蓄電", [r"power", r"battery", r"grid", r"電力", r"蓄電"]),
        ("冷却・熱管理", [r"cooling", r"thermal", r"liquid cooling", r"冷却", r"熱管理"]),
    ]
    hits = []
    for name, pats in rules:
        if any(re.search(p, t) for p in pats):
            hits.append(name)
    return hits[0] if hits else "未分類"


def material_type(title: str, summary: str):
    t = f"{title} {summary}"
    rules = [
        ("大型受注", r"large order|major order|order worth|受注|注文"),
        ("大企業との提携", r"strategic partnership|partnership|collaboration|agreement|提携|協業|契約"),
        ("戦略的投資", r"strategic investment|invests? \$|invested|出資|投資"),
        ("量産・生産開始", r"mass production|volume production|production begins|量産|生産開始"),
        ("設備投資", r"capacity expansion|new fab|manufacturing plant|factory|設備投資|工場"),
        ("業績上方修正", r"raises guidance|raised outlook|upward revision|上方修正"),
        ("特許・技術", r"patent|technology|photonic|特許|技術"),
        ("研究開発", r"research and development|r&d|研究開発"),
    ]
    return [name for name, pat in rules if re.search(pat, t, re.I)]


def google_news(company_query="AI data center optical interconnect"):
    url = "https://news.google.com/rss/search"
    params = {"q": company_query, "hl": "en-US", "gl": "US", "ceid": "US:en"}
    r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    feed = feedparser.parse(r.content)
    out = []
    for e in feed.entries[:CONFIG["max_news_items"]]:
        title = e.get("title", "")
        summary = BeautifulSoup(e.get("summary", ""), "html.parser").get_text(" ", strip=True)
        published = e.get("published", "")
        try:
            dt = dtparser.parse(published).astimezone(JST).isoformat()
        except Exception:
            dt = ""
        out.append({"title": title, "summary": summary, "published": dt, "url": e.get("link", "")})
    return out


def yahoo_chart(ticker, period="6mo", interval="1d"):
    # Public chart endpoint. Explicit range keeps enough history for 1D/5D/20D event reactions.
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"range": period, "interval": interval, "events": "history", "includeAdjustedClose": "true"}
    try:
        r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=20)
        r.raise_for_status()
        j = r.json()["chart"]["result"][0]
        meta = j.get("meta", {})
        timestamps = j.get("timestamp") or []
        closes = (j.get("indicators", {}).get("quote", [{}])[0].get("close") or [])
        rows = []
        for ts, close in zip(timestamps, closes):
            if close is not None:
                rows.append((datetime.fromtimestamp(ts, timezone.utc).date(), float(close)))
        return meta, rows
    except Exception:
        return None


def price_reaction(ticker, event_date):
    if not event_date or len(event_date) < 10:
        return {}
    c = get_chart(ticker)
    if not c:
        return {}
    _, rows = c
    if not rows:
        return {}
    d = datetime.fromisoformat(event_date[:10]).date()
    before = [x for x in rows if x[0] <= d]
    if not before:
        return {}
    base = before[-1][1]
    result = {}
    for days, label in [(1, "1D"), (5, "5D"), (20, "20D")]:
        future = [x for x in rows if x[0] > d]
        if len(future) >= days:
            result[label] = pct(future[days-1][1], base)
    return result


def valuation_check(price, eps, per):
    calc = safe_ratio(price, eps)
    if calc is None or per is None:
        return "CHECK_REQUIRED"
    err = abs(calc - per) / max(abs(per), 1e-9)
    return "OK" if err <= CONFIG["valuation_consistency_tolerance"] else "⚠基準不一致"


def growth_class(current, previous):
    c, p = num(current), num(previous)
    if c is None or p is None:
        return "NA"
    if p <= 0 < c:
        return "赤字→黒字転換"
    if c < 0 <= p:
        return "黒字→赤字転落"
    if abs(p) < 1e-9:
        return "分母極小・NA"
    return "通常成長率"


def business_progress_score(materials, entity_conf, theme):
    score = 0
    weights = {
        "大型受注": 30, "大企業との提携": 24, "戦略的投資": 22,
        "量産・生産開始": 28, "設備投資": 18, "業績上方修正": 30,
        "特許・技術": 12, "研究開発": 10
    }
    for m in set(materials):
        score += weights.get(m, 0)
    if entity_conf >= 0.9:
        score += 12
    elif entity_conf >= 0.72:
        score += 6
    if theme != "未分類":
        score += 4
    return min(score, 100)


def data_quality(fields):
    checks = []
    for x in fields:
        checks.append(x not in (None, "", "NA", "N/A"))
    return round(sum(checks) / len(checks) * 100, 1) if checks else 0.0


def implied_gap(progress, price_1d, price_5d, valuation_ok, data_q):
    # Positive means business evidence is strong relative to immediate price reaction.
    reaction = 0
    if price_1d is not None:
        reaction += max(min(price_1d, 20), -20) * 1.0
    if price_5d is not None:
        reaction += max(min(price_5d, 30), -30) * 0.5
    gap = progress - max(reaction, 0) * 1.5
    if valuation_ok != "OK":
        gap *= 0.75
    gap *= max(data_q / 100, 0.35)
    return round(max(0, min(100, gap)), 1)


def yahoo_ticker(ticker: str, market: str):
    return ticker if market == "US" else f"{ticker}.T"


def _statement_value(df, names, col):
    if df is None or df.empty or col not in df.columns:
        return None
    for name in names:
        if name in df.index:
            v = df.loc[name, col]
            if pd.notna(v):
                return float(v)
    return None


def financial_snapshot(company: Company):
    """
    Financial layer:
    - Uses one explicit annual fiscal period for revenue/operating income/net income/EPS.
    - Price is current/latest market price, but every ratio is labeled by its earnings/book/revenue basis.
    - Missing values remain None.
    """
    symbol = yahoo_ticker(company.ticker, company.market)
    try:
        tk = yf.Ticker(symbol)
        fi = getattr(tk, "fast_info", {}) or {}
        hist = tk.history(period="5d", auto_adjust=False)
        price = float(hist["Close"].dropna().iloc[-1]) if not hist.empty else None

        income = tk.income_stmt
        balance = tk.balance_sheet
        cash = tk.cashflow

        if income is None or income.empty:
            return {"取得元": "Yahoo Finance/yfinance", "整合性チェック": "DATA_UNAVAILABLE"}

        cols = list(income.columns)
        latest = cols[0] if cols else None
        previous = cols[1] if len(cols) > 1 else None

        revenue = _statement_value(income, ["Total Revenue", "Operating Revenue"], latest)
        revenue_prev = _statement_value(income, ["Total Revenue", "Operating Revenue"], previous)

        op_profit = _statement_value(income, ["Operating Income", "Operating Income Loss"], latest)
        op_profit_prev = _statement_value(income, ["Operating Income", "Operating Income Loss"], previous)

        net_income = _statement_value(income, ["Net Income", "Net Income Common Stockholders"], latest)
        net_income_prev = _statement_value(income, ["Net Income", "Net Income Common Stockholders"], previous)

        eps = _statement_value(income, ["Diluted EPS", "Basic EPS"], latest)
        if eps is None and net_income is not None:
            shares = _statement_value(income, ["Diluted Average Shares", "Basic Average Shares"], latest)
            eps = safe_ratio(net_income, shares)

        # Latest balance-sheet book value and cash/debt.
        equity = _statement_value(balance, ["Stockholders Equity", "Common Stock Equity"], latest)
        assets = _statement_value(balance, ["Total Assets"], latest)
        cash_eq = _statement_value(balance, ["Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents"], latest)
        debt = _statement_value(balance, ["Total Debt"], latest)
        shares_out = _statement_value(balance, ["Ordinary Shares Number", "Share Issued"], latest)

        # Cash flow.
        cfo = _statement_value(cash, ["Operating Cash Flow", "Total Cash From Operating Activities"], latest)
        capex = _statement_value(cash, ["Capital Expenditure", "Capital Expenditure Reported"], latest)
        fcf = None
        if cfo is not None and capex is not None:
            fcf = cfo + capex if capex < 0 else cfo - capex

        market_cap = None
        try:
            market_cap = float(fi.get("marketCap")) if fi.get("marketCap") is not None else None
        except Exception:
            pass
        if market_cap is None and price is not None and shares_out is not None:
            market_cap = price * shares_out

        bps = safe_ratio(equity, shares_out)
        per = safe_ratio(price, eps)
        psr = safe_ratio(market_cap, revenue)
        pbr = safe_ratio(price, bps)

        ebitda = _statement_value(income, ["EBITDA", "Normalized EBITDA"], latest)
        if ebitda is None and op_profit is not None:
            da = _statement_value(cash, ["Depreciation And Amortization", "Depreciation"], latest)
            if da is not None:
                ebitda = op_profit + abs(da)

        ev = None
        if market_cap is not None:
            ev = market_cap + (debt or 0) - (cash_eq or 0)
        ev_ebitda = safe_ratio(ev, ebitda)

        # ROE = net income / average equity where possible.
        equity_prev = _statement_value(balance, ["Stockholders Equity", "Common Stock Equity"], previous)
        avg_equity = None
        if equity is not None and equity_prev is not None:
            avg_equity = (equity + equity_prev) / 2
        roe = safe_ratio(net_income, avg_equity or equity)

        # ROIC = NOPAT / invested capital.
        pretax = _statement_value(income, ["Pretax Income"], latest)
        tax = _statement_value(income, ["Tax Provision", "Tax Provision Benefit"], latest)
        tax_rate = None
        if pretax is not None and pretax > 0 and tax is not None:
            tax_rate = max(0.0, min(0.35, tax / pretax))
        if tax_rate is None:
            tax_rate = 0.25
        nopat = op_profit * (1 - tax_rate) if op_profit is not None else None
        invested_capital = None
        if equity is not None:
            invested_capital = equity + (debt or 0) - (cash_eq or 0)
        roic = safe_ratio(nopat, invested_capital)

        # Dividend: use trailing cash dividends from Yahoo history.
        dividend_yield = None
        payout = None
        try:
            divs = tk.dividends
            if divs is not None and not divs.empty and price:
                one_year_ago = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=366)
                idx = divs.index
                if getattr(idx, "tz", None) is None:
                    idx = idx.tz_localize("UTC")
                annual_div = float(divs.loc[idx >= one_year_ago].sum())
                dividend_yield = annual_div / price * 100
                payout = safe_ratio(annual_div, eps) * 100 if eps and eps > 0 else None
        except Exception:
            pass

        # Profit-quality flags: detect explicit one-off / non-operating items.
        oneoff_terms = [
            "Gain On Sale Of Security", "Gain On Sale Of Assets",
            "Gain On Sale Of Business", "Other Non Operating Income Expenses",
            "Special Income Charges", "Restructuring And Mergern Acquisition",
            "Impairment", "Write Off", "Extraordinary Items"
        ]
        oneoff = []
        for term in oneoff_terms:
            v = _statement_value(income, [term], latest)
            if v is not None and abs(v) > max(abs(net_income or 0) * 0.05, 1):
                oneoff.append(term)

        if net_income is None:
            quality = "未判定"
        elif net_income <= 0:
            quality = "赤字・要注意"
        elif oneoff:
            quality = "一時要因あり・要確認"
        elif cfo is not None and cfo < 0:
            quality = "利益と営業CFの乖離・要確認"
        elif fcf is not None and fcf < 0:
            quality = "FCFマイナス・要確認"
        else:
            quality = "暫定良好"

        # Growth: never turn sign changes / tiny bases into giant percentages.
        eps_prev = _statement_value(income, ["Diluted EPS", "Basic EPS"], previous)
        if eps_prev is None and net_income_prev is not None:
            shares_prev = _statement_value(income, ["Diluted Average Shares", "Basic Average Shares"], previous)
            eps_prev = safe_ratio(net_income_prev, shares_prev)
        eps_growth = pct(eps, eps_prev)
        rev_growth = pct(revenue, revenue_prev)
        op_growth = pct(op_profit, op_profit_prev)

        checks = []
        if per is not None and eps is not None and price is not None:
            checks.append(abs(per - price / eps) / max(abs(per), 1e-9) <= CONFIG["valuation_consistency_tolerance"])
        if psr is not None and market_cap is not None and revenue:
            checks.append(abs(psr - market_cap / revenue) / max(abs(psr), 1e-9) <= CONFIG["valuation_consistency_tolerance"])
        if pbr is not None and price is not None and bps:
            checks.append(abs(pbr - price / bps) / max(abs(pbr), 1e-9) <= CONFIG["valuation_consistency_tolerance"])
        integrity = "OK" if checks and all(checks) else ("⚠要確認" if checks else "DATA_UNAVAILABLE")

        op_margin = safe_ratio(op_profit, revenue) * 100 if revenue else None
        net_margin = safe_ratio(net_income, revenue) * 100 if revenue else None
        debt_to_equity = safe_ratio(debt, equity) * 100 if equity else None
        net_cash = (cash_eq - debt) if cash_eq is not None and debt is not None else None

        return {
            "財務取得状態": "OK",
            "株価": price, "時価総額": market_cap, "PER": per, "PBR": pbr, "PSR": psr, "EV/EBITDA": ev_ebitda,
            "EPS": eps, "EPS前期": eps_prev, "EPS成長率": eps_growth, "EPS成長判定": growth_class(eps, eps_prev),
            "売上": revenue, "売上前期": revenue_prev, "売上成長率": rev_growth,
            "営業利益": op_profit, "営業利益前期": op_profit_prev, "営業利益成長率": op_growth, "営業利益率": op_margin,
            "純利益": net_income, "純利益前期": net_income_prev, "純利益率": net_margin, "BPS": bps,
            "株主資本": equity, "総資産": assets, "現金等": cash_eq, "有利子負債": debt,
            "ネットキャッシュ": net_cash, "負債/株主資本": debt_to_equity,
            "ROE": (roe * 100 if roe is not None else None), "ROIC": (roic * 100 if roic is not None else None),
            "営業CF": cfo, "FCF": fcf, "配当利回り": dividend_yield, "配当性向": payout,
            "一時要因": " / ".join(oneoff) if oneoff else "検出なし", "利益品質": quality,
            "バリュエーション整合性": integrity, "データ基準日": datetime.now(JST).date().isoformat(),
            "決算期": str(latest.date()) if hasattr(latest, "date") else str(latest),
            "指標基準": "直近年次決算ベース（株価のみ最新）", "取得元": "Yahoo Finance/yfinance", "整合性チェック": integrity,
        }
    except Exception as e:
        return {
            "財務取得状態": "DATA_UNAVAILABLE",
            "取得元": "Yahoo Finance/yfinance",
            "整合性チェック": f"DATA_UNAVAILABLE:{type(e).__name__}"
        }

_FIN_CACHE = {}
_CHART_CACHE = {}
def get_financial_snapshot(company):
    key = company.ticker if company else ""
    if not key:
        return {}
    if key not in _FIN_CACHE:
        _FIN_CACHE[key] = financial_snapshot(company)
    return _FIN_CACHE[key]

def get_chart(ticker):
    if ticker not in _CHART_CACHE:
        _CHART_CACHE[ticker] = yahoo_chart(ticker, period=CONFIG.get("chart_period", "6mo"), interval="1d")
    return _CHART_CACHE[ticker]

def market_cap_bucket(company, market_cap):
    if market_cap is None or company is None:
        return "NA"
    limit = CONFIG["small_cap_jpy"] if company.market == "JP" else CONFIG["small_cap_usd"]
    if market_cap < limit:
        return "小型〜中小型"
    if market_cap < limit * 5:
        return "中型"
    return "大型"

def main():
    # Broad queries intentionally overlap so the entity resolver can compare evidence.
    queries = [
        "AI data center optical interconnect semiconductor",
        "silicon photonics CPO AI infrastructure",
        "GPU optical interconnect order partnership production",
        "半導体 AI データセンター 光通信 受注 提携",
    ]
    seen = set()
    news = []
    for q in queries:
        try:
            items = google_news(q)
        except Exception:
            items = []
        for x in items:
            key = (x["title"], x["url"])
            if key not in seen:
                seen.add(key)
                news.append(x)

    rows = []
    for item in news:
        company, conf, involvement = resolve_entity(item["title"], item["summary"])
        mats = material_type(item["title"], item["summary"])
        theme = theme_of(item["title"], item["summary"])
        progress = business_progress_score(mats, conf, theme)

        ticker = company.ticker if company and conf >= CONFIG["min_entity_confidence"] else ""
        price_1d = price_5d = price_20d = None
        if ticker:
            reactions = price_reaction(ticker, item["published"])
            price_1d, price_5d, price_20d = reactions.get("1D"), reactions.get("5D"), reactions.get("20D")

        fin = get_financial_snapshot(company) if company and conf >= CONFIG["min_entity_confidence"] else {}
        fields = [ticker, price_1d, price_5d, price_20d, fin.get("株価"), fin.get("時価総額"),
                  fin.get("PER"), fin.get("PBR"), fin.get("PSR"), fin.get("EV/EBITDA"), fin.get("EPS"),
                  fin.get("売上成長率"), fin.get("営業利益成長率"), fin.get("ROE"), fin.get("ROIC"),
                  fin.get("営業CF"), fin.get("FCF"), fin.get("配当利回り"), fin.get("配当性向")]
        dq = data_quality(fields)
        valuation_status = fin.get("バリュエーション整合性", "CHECK_REQUIRED")
        gap = implied_gap(progress, price_1d, price_5d, valuation_status, dq)
        if ticker and fin.get("財務取得状態") != "OK":
            gap = min(gap, CONFIG["candidate_score_cap_without_financials"])
        rows.append({
            "取得日": TODAY,
            "企業": company.name if company and conf >= CONFIG["min_entity_confidence"] else "未特定",
            "市場": company.market if company and ticker else "",
            "証券コード・ティッカー": ticker,
            "企業規模区分": market_cap_bucket(company, fin.get("時価総額")) if ticker else "NA",
            "企業関与": involvement,
            "企業関与信頼度": round(conf, 2),
            "テーマ": theme,
            "材料": " / ".join(mats) if mats else "テーマ関連",
            "事業進展スコア": progress,
            "株価反応1日": price_1d,
            "株価反応5日": price_5d,
            "株価反応20日": price_20d,
            "未織り込みギャップ": gap,
            "株価": fin.get("株価"),
            "時価総額": fin.get("時価総額"),
            "PER": fin.get("PER"),
            "PBR": fin.get("PBR"),
            "PSR": fin.get("PSR"),
            "EV/EBITDA": fin.get("EV/EBITDA"),
            "EPS": fin.get("EPS"),
            "EPS前期": fin.get("EPS前期"),
            "EPS成長率": fin.get("EPS成長率"),
            "EPS成長判定": fin.get("EPS成長判定", "NA"),
            "売上": fin.get("売上"),
            "売上前期": fin.get("売上前期"),
            "売上成長率": fin.get("売上成長率"),
            "営業利益": fin.get("営業利益"),
            "営業利益前期": fin.get("営業利益前期"),
            "営業利益成長率": fin.get("営業利益成長率"),
            "営業利益率": fin.get("営業利益率"),
            "純利益": fin.get("純利益"),
            "純利益前期": fin.get("純利益前期"),
            "純利益率": fin.get("純利益率"),
            "BPS": fin.get("BPS"),
            "ROE": fin.get("ROE"),
            "ROIC": fin.get("ROIC"),
            "営業CF": fin.get("営業CF"),
            "FCF": fin.get("FCF"),
            "現金等": fin.get("現金等"),
            "有利子負債": fin.get("有利子負債"),
            "ネットキャッシュ": fin.get("ネットキャッシュ"),
            "負債/株主資本": fin.get("負債/株主資本"),
            "一時要因": fin.get("一時要因", "NA"),
            "配当利回り": fin.get("配当利回り"),
            "配当性向": fin.get("配当性向"),
            "利益品質": fin.get("利益品質", "未判定"),
            "バリュエーション整合性": fin.get("バリュエーション整合性", "CHECK_REQUIRED"),
            "データ品質": dq,
            "財務取得状態": fin.get("財務取得状態", "DATA_UNAVAILABLE" if ticker else "未取得"),
            "データ基準日": fin.get("データ基準日", ""),
            "決算期": fin.get("決算期", ""),
            "指標基準": fin.get("指標基準", ""),
            "取得元": "; ".join(x for x in ["Google News RSS", fin.get("取得元", "Yahoo chart")] if x),
            "整合性チェック": fin.get("整合性チェック", "財務データ未取得"),
            "リスク": ("利益品質:" + str(fin.get("利益品質")) if fin.get("利益品質") not in (None, "暫定良好", "未判定") else ("財務データ未取得" if ticker else "企業未特定")),
            "タイトル": item["title"],
            "公開日時": item["published"],
            "URL": item["url"],
        })

    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame([{"取得日": TODAY, "企業": "データなし"}])

    # No ranking by raw news volume. Sort by the research signal only.
    sort_cols = [c for c in ["未織り込みギャップ", "事業進展スコア", "企業関与信頼度"] if c in df]
    if sort_cols:
        df = df.sort_values(sort_cols, ascending=False)

    out = DATA / f"radar_{TODAY}.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")

    candidates = (
        df[(df["企業"] != "未特定") & (df["企業関与信頼度"] >= CONFIG["min_entity_confidence"])]
        .groupby(["企業", "証券コード・ティッカー"], as_index=False)
        .agg(
            未織り込みギャップ=("未織り込みギャップ", "max"),
            事業進展スコア=("事業進展スコア", "max"),
            材料件数=("材料", "count"),
            データ品質=("データ品質", "max"),
            テーマ=("テーマ", lambda x: " / ".join(sorted(set(x)))),
        )
        .sort_values(["未織り込みギャップ", "事業進展スコア"], ascending=False)
        .head(int(CONFIG.get("max_candidates", 30)))
    )

    # One representative row per company: strongest signal, while retaining full detail.
    candidates = df[(df["企業"] != "未特定") & (df["企業関与信頼度"] >= CONFIG["min_entity_confidence"])].copy()
    if not candidates.empty:
        candidates = candidates.sort_values(["未織り込みギャップ", "事業進展スコア", "データ品質"], ascending=False)
        rep = candidates.drop_duplicates(["企業", "証券コード・ティッカー"], keep="first").head(int(CONFIG.get("max_candidates", 30)))
    else:
        rep = candidates

    md = [
        f"# Future Stock Radar v4.1 — {TODAY}",
        "",
        "> 調査優先度を示す研究用レーダーです。売買推奨・将来リターン保証ではありません。",
        "",
        "## v4.1 ブラッシュアップ内容",
        "- v4の既存項目を削らず、候補レポート側にも詳細財務を展開。",
        "- 株価履歴の取得期間を明示し、1D/5D/20D反応を実測。",
        "- 配当履歴をSeriesとして正しく集計し、配当利回り・配当性向を復元。",
        "- 同一企業の財務データをニュースごとに再取得せずキャッシュ。",
        "- 財務データ未取得の候補は未織り込みギャップを上限値で抑制。",
        "- 一時要因、営業利益率、純利益、BPS、現金、有利子負債、ネットキャッシュ等を追加。",
        "",
        "## 読み方",
        "- 未織り込みギャップは、事業進展と直近株価反応の差をみる内部研究指標であり、将来リターン予測ではありません。",
        "- 株価反応は材料公開日を基準にした翌1/5/20取引日の変化率です。",
        "- 欠損値は推測で補完せずNAとします。",
        "",
        "## 調査候補",
    ]
    def fmt(v, digits=2):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return "NA"
        if isinstance(v, (int, float)):
            return f"{v:,.{digits}f}"
        return str(v)
    def pctfmt(v):
        return "NA" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:.2f}%"

    for i, (_, r) in enumerate(rep.iterrows(), 1):
        md += [
            f"### {i}. {r['企業']}（{r['証券コード・ティッカー']}）",
            f"- 未織り込みギャップ：{fmt(r['未織り込みギャップ'], 1)} / 事業進展：{fmt(r['事業進展スコア'], 0)} / データ品質：{pctfmt(r['データ品質'])}",
            f"- 材料：{r['材料']}",
            f"- テーマ：{r['テーマ']} / 企業関与信頼度：{fmt(r['企業関与信頼度'])}",
            "",
            "**株価・バリュエーション**",
            f"- 株価：{fmt(r['株価'])} / 時価総額：{fmt(r['時価総額'])} / 規模区分：{r['企業規模区分']}",
            f"- PER：{fmt(r['PER'])} / PBR：{fmt(r['PBR'])} / PSR：{fmt(r['PSR'])} / EV/EBITDA：{fmt(r['EV/EBITDA'])}",
            f"- 株価反応：1D {pctfmt(r['株価反応1日'])} / 5D {pctfmt(r['株価反応5日'])} / 20D {pctfmt(r['株価反応20日'])}",
            f"- バリュエーション整合性：{r['バリュエーション整合性']}",
            "",
            "**成長・収益性・キャッシュフロー**",
            f"- EPS：{fmt(r['EPS'])} / 前期：{fmt(r['EPS前期'])} / 成長率：{pctfmt(r['EPS成長率'])} / 判定：{r['EPS成長判定']}",
            f"- 売上：{fmt(r['売上'])} / 前期：{fmt(r['売上前期'])} / 成長率：{pctfmt(r['売上成長率'])}",
            f"- 営業利益：{fmt(r['営業利益'])} / 成長率：{pctfmt(r['営業利益成長率'])} / 営業利益率：{pctfmt(r['営業利益率'])}",
            f"- 純利益：{fmt(r['純利益'])} / 純利益率：{pctfmt(r['純利益率'])}",
            f"- ROE：{pctfmt(r['ROE'])} / ROIC：{pctfmt(r['ROIC'])}",
            f"- 営業CF：{fmt(r['営業CF'])} / FCF：{fmt(r['FCF'])}",
            "",
            "**財務安全性・利益品質**",
            f"- BPS：{fmt(r['BPS'])}",
            f"- 現金等：{fmt(r['現金等'])} / 有利子負債：{fmt(r['有利子負債'])} / ネットキャッシュ：{fmt(r['ネットキャッシュ'])}",
            f"- 負債/株主資本：{pctfmt(r['負債/株主資本'])}",
            f"- 一時要因：{r['一時要因']} / 利益品質：{r['利益品質']}",
            f"- 配当利回り：{pctfmt(r['配当利回り'])} / 配当性向：{pctfmt(r['配当性向'])}",
            "",
            "**データ基準**",
            f"- 財務取得状態：{r['財務取得状態']}",
            f"- データ基準日：{r['データ基準日']} / 決算期：{r['決算期']}",
            f"- 指標基準：{r['指標基準']}",
            f"- 取得元：{r['取得元']} / 整合性：{r['整合性チェック']}",
            f"- リスク表示：{r['リスク']}",
            f"- 代表材料：{r['タイトル']}",
            f"- 公開日時：{r['公開日時']}",
            f"- 出典：{r['URL']}",
            "",
        ]

    (DATA / f"top_candidates_{TODAY}.md").write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        (DATA / f"run_error_{TODAY}.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise
