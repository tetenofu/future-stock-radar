from __future__ import annotations
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import numpy as np
import pandas as pd
try:
    import yfinance as yf
except ImportError:  # keeps heuristic helpers testable offline
    yf = None

ROOT = Path(__file__).resolve().parents[1]


def _number(info, *keys):
    for key in keys:
        value = info.get(key)
        try:
            value = float(value)
            if np.isfinite(value):
                return value
        except (TypeError, ValueError):
            continue
    return np.nan


def _score_growth(revenue_growth, earnings_growth):
    vals = []
    for x in (revenue_growth, earnings_growth):
        if np.isfinite(x):
            vals.append(100 if x >= .30 else 80 if x >= .15 else 60 if x >= .05 else 40 if x >= 0 else 15)
    return float(np.mean(vals)) if vals else np.nan


def _score_quality(margin, roe, fcf):
    vals = []
    if np.isfinite(margin): vals.append(100 if margin >= .25 else 80 if margin >= .15 else 60 if margin >= .08 else 35 if margin >= 0 else 10)
    if np.isfinite(roe): vals.append(100 if roe >= .20 else 80 if roe >= .12 else 60 if roe >= .06 else 35 if roe >= 0 else 10)
    if np.isfinite(fcf): vals.append(80 if fcf > 0 else 20)
    return float(np.mean(vals)) if vals else np.nan


def _score_valuation(pe, ps, pb):
    # A deliberately coarse relative-risk heuristic, not a fair-value model.
    vals = []
    if np.isfinite(pe) and pe > 0: vals.append(90 if pe <= 15 else 75 if pe <= 25 else 55 if pe <= 40 else 30 if pe <= 70 else 15)
    if np.isfinite(ps) and ps > 0: vals.append(90 if ps <= 2 else 75 if ps <= 5 else 55 if ps <= 10 else 30 if ps <= 20 else 15)
    if np.isfinite(pb) and pb > 0: vals.append(85 if pb <= 1.5 else 70 if pb <= 3 else 50 if pb <= 6 else 25)
    return float(np.mean(vals)) if vals else np.nan


def fetch_fundamentals(symbol):
    """Fetch best-effort Yahoo Finance summary data; missing fields remain missing."""
    if yf is None:
        return {"symbol": symbol, "fundamental_status": "unavailable: yfinance not installed"}
    try:
        info = yf.Ticker(symbol).get_info()
        if not isinstance(info, dict) or not info:
            return {"symbol": symbol, "fundamental_status": "unavailable"}
        revenue_growth = _number(info, "revenueGrowth")
        earnings_growth = _number(info, "earningsGrowth", "earningsQuarterlyGrowth")
        margin = _number(info, "operatingMargins", "profitMargins")
        roe = _number(info, "returnOnEquity")
        fcf = _number(info, "freeCashflow")
        pe = _number(info, "trailingPE", "forwardPE")
        ps = _number(info, "priceToSalesTrailing12Months")
        pb = _number(info, "priceToBook")
        debt_equity = _number(info, "debtToEquity")
        growth_score = _score_growth(revenue_growth, earnings_growth)
        quality_score = _score_quality(margin, roe, fcf)
        valuation_score = _score_valuation(pe, ps, pb)
        available = sum(np.isfinite(x) for x in [revenue_growth, earnings_growth, margin, roe, fcf, pe, ps, pb])
        return {
            "symbol": symbol,
            "company_name": info.get("shortName", info.get("longName", "")),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "market_cap": _number(info, "marketCap"),
            "revenue_growth": revenue_growth,
            "earnings_growth": earnings_growth,
            "operating_margin": margin,
            "return_on_equity": roe,
            "free_cash_flow": fcf,
            "trailing_pe": _number(info, "trailingPE"),
            "forward_pe": _number(info, "forwardPE"),
            "price_to_sales": ps,
            "price_to_book": pb,
            "debt_to_equity": debt_equity,
            "dividend_yield": _number(info, "dividendYield"),
            "fundamental_fields_available": available,
            "growth_score": growth_score,
            "quality_score": quality_score,
            "valuation_score": valuation_score,
            "fundamental_status": "partial" if available < 8 else "ok",
        }
    except Exception as exc:
        return {"symbol": symbol, "fundamental_status": f"unavailable: {type(exc).__name__}"}


def fetch_headlines(symbol, limit=5):
    if yf is None:
        return []
    try:
        news = yf.Ticker(symbol).news or []
        headlines = []
        for item in news[:limit]:
            content = item.get("content", item)
            title = content.get("title") or content.get("headline")
            if title:
                headlines.append(str(title).strip())
        return headlines
    except Exception:
        return []


def _agent_assessments(row, headlines):
    assessments = []
    growth = row.get("growth_score", np.nan)
    quality = row.get("quality_score", np.nan)
    valuation = row.get("valuation_score", np.nan)
    technical = row.get("score", np.nan)
    assessments.append(("Growth analyst", "growth", growth, "Revenue/earnings growth fields from a third-party data feed; missing values are not treated as zero."))
    assessments.append(("Fundamental quality analyst", "quality", quality, "Margin, ROE and free-cash-flow heuristics; check audited filings before relying on them."))
    assessments.append(("Valuation analyst", "valuation", valuation, "Coarse valuation bands only; sector differences and forward estimates can distort comparisons."))
    assessments.append(("Technical analyst", "technical", technical, "Existing rules-based technical score; not a return probability."))
    valid = [x[2] for x in assessments if pd.notna(x[2])]
    research_score = float(np.mean(valid)) if valid else np.nan
    risks = []
    if pd.isna(growth): risks.append("Growth data missing")
    elif growth < 50: risks.append("Growth indicators are weak or mixed")
    if pd.isna(quality): risks.append("Quality data missing")
    elif quality < 50: risks.append("Profitability/cash-flow indicators are weak or mixed")
    if pd.isna(valuation): risks.append("Valuation data missing")
    elif valuation < 40: risks.append("Valuation heuristic flags elevated valuation risk")
    if pd.notna(technical) and technical < 40: risks.append("Technical trend score is weak")
    if not headlines: risks.append("No headline data returned; this is not evidence that no catalyst exists")
    return research_score, "; ".join(risks) if risks else "No automatic red flag from available fields; primary-source verification still required", headlines


def _ollama_review(symbol, payload, cfg):
    settings = cfg.get("agents", {})
    if not settings.get("local_ollama_enabled", False):
        return "disabled"
    url = settings.get("ollama_url", "http://127.0.0.1:11434/api/generate")
    model = settings.get("ollama_model", "llama3.2")
    prompt = (
        "You are a skeptical equity research reviewer. Use only supplied data. "
        "Do not invent facts. Separate evidence, uncertainty, and risks. Do not give a guaranteed buy signal. "
        "Return concise Japanese markdown with bullish case, bearish case, missing evidence, and invalidation conditions.\n\n"
        + json.dumps(payload, ensure_ascii=False, default=str)
    )
    body = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
    try:
        req = Request(url, data=body, headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
        return str(data.get("response", "")).strip() or "No response from local model"
    except (URLError, HTTPError, TimeoutError, ValueError) as exc:
        return f"Local model unavailable: {type(exc).__name__}"


def enrich_universe(ranked, cfg):
    if ranked is None or ranked.empty:
        return pd.DataFrame()
    fundamentals_cfg = cfg.get("fundamentals", {})
    news_cfg = cfg.get("news", {})
    max_symbols = int(fundamentals_cfg.get("max_symbols_per_run", 40))
    # Enrich the highest-ranked candidates to keep provider load and runtime modest.
    subset = ranked.head(max_symbols).copy()
    records = []
    max_llm = int(cfg.get("agents", {}).get("max_llm_symbols", 5))
    for _, base in subset.iterrows():
        symbol = str(base["symbol"])
        rec = base.to_dict()
        if fundamentals_cfg.get("enabled", True):
            rec.update(fetch_fundamentals(symbol))
            time.sleep(float(fundamentals_cfg.get("request_pause_seconds", 0.15)))
        headlines = fetch_headlines(symbol, int(news_cfg.get("max_headlines_per_symbol", 5))) if news_cfg.get("enabled", True) else []
        research_score, risk_notes, headlines = _agent_assessments(rec, headlines)
        rec["research_score"] = round(research_score, 2) if pd.notna(research_score) else np.nan
        rec["risk_notes"] = risk_notes
        rec["headline_count"] = len(headlines)
        rec["headlines"] = " | ".join(headlines)
        rec["local_llm_review"] = (
            _ollama_review(symbol, {k: rec.get(k) for k in ["symbol", "score", "growth_score", "quality_score", "valuation_score", "risk_notes", "headlines"]}, cfg)
            if len(records) < max_llm else "skipped: max_llm_symbols limit"
        )
        records.append(rec)
    return pd.DataFrame(records)


def write_agent_reviews(df, output, cfg):
    lines = ["# Daily multi-role research review", "", "> These are heuristic research roles, not independent professional opinions. Only the optional Ollama section uses a language model.", "", "## Highest research scores", ""]
    if df.empty:
        lines.append("No enriched candidates available.")
    else:
        sort_col = "research_score" if "research_score" in df else "score"
        for _, row in df.sort_values(sort_col, ascending=False).head(10).iterrows():
            lines += [f"### {row.get('symbol')} — research score {row.get('research_score', 'N/A')} / technical score {row.get('score', 'N/A')}", "", f"- Company: {row.get('company_name', '')}", f"- Sector / industry: {row.get('sector', '')} / {row.get('industry', '')}", f"- Growth score: {row.get('growth_score', 'N/A')}", f"- Quality score: {row.get('quality_score', 'N/A')}", f"- Valuation heuristic: {row.get('valuation_score', 'N/A')}", f"- Data status: {row.get('fundamental_status', 'unknown')}", f"- Risk notes: {row.get('risk_notes', '')}", f"- Headlines: {row.get('headlines', '') or 'No headlines returned'}", ""]
            llm = row.get("local_llm_review", "disabled")
            if llm and llm != "disabled": lines += ["**Optional local-model review**", "", str(llm), ""]
    lines += ["## Method and limitations", "", "- Research score is the mean of available growth, quality, valuation and technical scores; missing data is excluded rather than treated as zero.", "- This is a triage score, not a forecast, fair value, or buy recommendation.", "- Third-party summary data and headlines can be missing, delayed, or incorrect. Verify filings and IR releases from primary sources.", "- The system does not place orders, size positions, or automatically change scoring weights.", ""]
    Path(output).write_text("\n".join(lines), encoding="utf-8")
