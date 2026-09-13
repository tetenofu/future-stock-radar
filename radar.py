import csv
import os
import re
import math
from datetime import datetime, timezone, timedelta

import feedparser
import yfinance as yf

JST = timezone(timedelta(hours=9))

# ============================================================
# Future Stock Radar v3
# News -> company -> fundamentals -> valuation -> shareholder return
# -> price/volume -> trap detection -> research priority
# Missing data is always "未取得"; never treated as zero.
# ============================================================

RSS_FEEDS = {
    "AIデータセンター": [
        "https://news.google.com/rss/search?q=AI+data+center&hl=en-US&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=AI+データセンター&hl=ja&gl=JP&ceid=JP:ja",
        "https://news.google.com/rss/search?q=データセンター+電力&hl=ja&gl=JP&ceid=JP:ja",
    ],
    "光通信": [
        "https://news.google.com/rss/search?q=co-packaged+optics&hl=en-US&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=silicon+photonics&hl=en-US&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=光通信+シリコンフォトニクス&hl=ja&gl=JP&ceid=JP:ja",
        "https://news.google.com/rss/search?q=IOWN+光通信&hl=ja&gl=JP&ceid=JP:ja",
    ],
    "冷却・熱管理": [
        "https://news.google.com/rss/search?q=liquid+cooling+data+center&hl=en-US&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=immersion+cooling&hl=en-US&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=データセンター+液冷&hl=ja&gl=JP&ceid=JP:ja",
        "https://news.google.com/rss/search?q=半導体+冷却+熱管理&hl=ja&gl=JP&ceid=JP:ja",
    ],
    "電力・蓄電": [
        "https://news.google.com/rss/search?q=data+center+power+grid&hl=en-US&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=energy+storage+data+center&hl=en-US&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=データセンター+電力+蓄電&hl=ja&gl=JP&ceid=JP:ja",
        "https://news.google.com/rss/search?q=蓄電池+送電網&hl=ja&gl=JP&ceid=JP:ja",
    ],
    "半導体": [
        "https://news.google.com/rss/search?q=advanced+packaging+semiconductor&hl=en-US&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=chiplet+HBM&hl=en-US&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=compound+semiconductor+GaN+SiC&hl=en-US&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=半導体+先端パッケージ+HBM&hl=ja&gl=JP&ceid=JP:ja",
        "https://news.google.com/rss/search?q=GaN+SiC+半導体&hl=ja&gl=JP&ceid=JP:ja",
    ],
    "宇宙": [
        "https://news.google.com/rss/search?q=space+data+center&hl=en-US&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=satellite+computing+optical+communication&hl=en-US&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=宇宙+データセンター&hl=ja&gl=JP&ceid=JP:ja",
        "https://news.google.com/rss/search?q=衛星+光通信&hl=ja&gl=JP&ceid=JP:ja",
    ],
    "宇宙熱管理": [
        "https://news.google.com/rss/search?q=spacecraft+thermal+management+radiator&hl=en-US&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=宇宙+熱管理+ラジエーター&hl=ja&gl=JP&ceid=JP:ja",
    ],
    "宇宙太陽光・発電": [
        "https://news.google.com/rss/search?q=space+solar+power&hl=en-US&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=宇宙太陽光+発電&hl=ja&gl=JP&ceid=JP:ja",
    ],
}

MATERIALS = {
    "大型受注": (["order", "orders", "purchase order", "follow-on order", "contract", "受注", "大型受注", "契約"], 30),
    "量産・生産開始": (["production", "mass production", "volume production", "manufacturing", "量産", "生産開始"], 25),
    "大企業との提携": (["partnership", "strategic partnership", "collaboration", "alliance", "提携", "協業", "共同開発"], 25),
    "戦略的投資": (["strategic investment", "invests", "funding", "出資", "戦略投資"], 22),
    "政府支援": (["government", "subsidy", "grant", "government funding", "政府", "補助金", "助成金"], 20),
    "特許・技術": (["patent", "patented", "intellectual property", "breakthrough", "new technology", "特許", "新技術", "技術革新"], 15),
    "研究開発": (["research", "development", "r&d", "demonstration", "prototype", "研究", "開発", "実証", "試作"], 12),
    "設備投資": (["capital expenditure", "capex", "factory expansion", "facility expansion", "new facility", "設備投資", "工場増設"], 18),
    "業績上方修正": (["raises outlook", "raised guidance", "higher revenue", "record revenue", "record sales", "上方修正", "最高益", "増収"], 30),
}

# High-confidence aliases. This is deliberately conservative; unknown companies remain "未特定".
COMPANY_ALIASES = {
    "NTT": "9432.T", "日本電信電話": "9432.T",
    "東京海上": "8766.T", "東京海上ホールディングス": "8766.T",
    "キオクシア": "285A.T", "Kioxia": "285A.T",
    "メディアリンクス": "6659.T", "Media Links": "6659.T",
    "海帆": "3133.T", "FIG": "4392.T", "Kopin": "KOPN",
    "京セラ": "6971.T", "Kyocera": "6971.T",
    "ソフトバンク": "9434.T", "SoftBank": "9434.T",
    "富士通": "6702.T", "Fujitsu": "6702.T",
    "NEC": "6701.T", "日立": "6501.T", "Hitachi": "6501.T",
    "三菱重工": "7011.T", "Mitsubishi Heavy Industries": "7011.T",
    "古野電気": "6814.T", "Furuno": "6814.T",
    "浜松ホトニクス": "6965.T", "Hamamatsu Photonics": "6965.T",
    "住友電工": "5802.T", "Sumitomo Electric": "5802.T",
    "フジクラ": "5803.T", "Fujikura": "5803.T",
    "アドバンテスト": "6857.T", "Advantest": "6857.T",
    "ディスコ": "6146.T", "Disco": "6146.T",
    "東京エレクトロン": "8035.T", "Tokyo Electron": "8035.T",
    "ソシオネクスト": "6526.T", "Socionext": "6526.T",
    "信越化学": "4063.T", "Shin-Etsu": "4063.T",
    "ローム": "6963.T", "ROHM": "6963.T",
    "レーザーテック": "6920.T", "Lasertec": "6920.T",
    "Aehr Test Systems": "AEHR", "Amkor Technology": "AMKR",
    "Thales": "HO.PA", "Kyocera": "6971.T",
}

TICKER_RE = re.compile(r"\b[A-Z]{1,5}(?:\.[A-Z]{1,3})?\b")
JP_CODE_RE = re.compile(r"(?<!\d)(\d{4})(?:\.T)?(?!\d)")


def normalize_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def detect_theme(text):
    t = text.lower()
    rules = {
        "AIデータセンター": ["ai data center", "data center", "データセンター", "hyperscale"],
        "光通信": ["co-packaged optics", "silicon photonics", "optical i/o", "optical interconnect", "光通信", "フォトニクス", "iown"],
        "冷却・熱管理": ["liquid cooling", "immersion cooling", "thermal management", "heat exchanger", "液冷", "熱管理", "ラジエーター"],
        "電力・蓄電": ["data center power", "energy storage", "fuel cell", "grid", "蓄電", "送電", "電力"],
        "半導体": ["advanced packaging", "chiplet", "hbm", "compound semiconductor", "gan", "sic", "半導体", "先端パッケージ"],
        "宇宙": ["space data center", "orbital data center", "satellite computing", "space optical communication", "宇宙", "衛星"],
        "宇宙熱管理": ["space radiator", "spacecraft thermal", "heat rejection", "宇宙熱", "宇宙機熱"],
        "宇宙太陽光・発電": ["space solar power", "space solar panel", "space energy", "宇宙太陽光"],
    }
    for theme, keys in rules.items():
        if any(k in t for k in keys):
            return theme
    return "その他"


def detect_material(text):
    t = text.lower()
    found, score = [], 0
    for material, (keys, pts) in MATERIALS.items():
        if any(k.lower() in t for k in keys):
            found.append(material)
            score += pts
    return (" / ".join(found) if found else "テーマ関連ニュース"), min(score, 100)


def company_candidates(text):
    found = []
    for alias, ticker in COMPANY_ALIASES.items():
        if alias.lower() in text.lower():
            found.append((alias, ticker, "alias"))
    for m in JP_CODE_RE.finditer(text):
        code = m.group(1) + ".T"
        if (None, code, "code") not in found:
            found.append((m.group(1), code, "code"))
    for m in TICKER_RE.finditer(text):
        token = m.group(0)
        if token in {"AI", "US", "CEO", "GPU", "HBM", "R&D", "USD", "NASA", "DOE", "ROE", "ROIC", "PBR", "PER", "CF"}:
            continue
        found.append((token, token, "ticker"))
    # preserve order, remove duplicate ticker
    out, seen = [], set()
    for name, ticker, source in found:
        if ticker in seen:
            continue
        seen.add(ticker)
        out.append((name, ticker, source))
    return out[:5]


def safe_num(x):
    try:
        if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
            return None
        return float(x)
    except Exception:
        return None


def pct(a, b):
    a, b = safe_num(a), safe_num(b)
    if a is None or b in (None, 0):
        return None
    return (a / b - 1) * 100


def fmt_num(x):
    if x is None:
        return "未取得"
    if abs(x) >= 1e12:
        return f"{x/1e12:.2f}兆"
    if abs(x) >= 1e8:
        return f"{x/1e8:.1f}億"
    if abs(x) >= 1e4:
        return f"{x/1e4:.1f}万"
    return f"{x:.2f}"


def get_series_values(financials, row_names, periods=5):
    if financials is None or getattr(financials, "empty", True):
        return []
    for row in row_names:
        if row in financials.index:
            vals = []
            for col in financials.columns[:periods]:
                v = safe_num(financials.loc[row, col])
                if v is not None:
                    vals.append(v)
            if vals:
                return vals
    return []


def calculate_financial_quality(ticker):
    result = {
        "ティッカー": ticker,
        "企業名": "未取得", "時価総額": None, "株価": None,
        "売上": None, "売上成長率": None, "営業利益": None,
        "営業利益成長率": None, "EPS": None, "EPS成長率": None,
        "営業CF": None, "ROE": None, "ROIC": None, "利益率": None,
        "PER": None, "PBR": None, "PSR": None,
        "配当利回り": None, "配当性向": None, "自己株買い": "未取得",
        "利益品質": "未判定", "バリュートラップ": "未判定",
        "配当性向引き上げ余地": "未判定", "株主還元姿勢": "未判定",
        "価格帯": "未取得", "しこり判定": "未判定",
        "財務データ取得": "未取得",
    }
    try:
        tk = yf.Ticker(ticker)
        info = tk.info or {}
        result["企業名"] = info.get("longName") or info.get("shortName") or "未取得"
        result["時価総額"] = safe_num(info.get("marketCap"))
        result["株価"] = safe_num(info.get("currentPrice") or info.get("regularMarketPrice"))
        result["PER"] = safe_num(info.get("trailingPE"))
        result["PBR"] = safe_num(info.get("priceToBook"))
        result["PSR"] = safe_num(info.get("priceToSalesTrailing12Months"))
        result["ROE"] = safe_num(info.get("returnOnEquity"))
        if result["ROE"] is not None and abs(result["ROE"]) < 2:
            result["ROE"] *= 100
        result["ROIC"] = safe_num(info.get("returnOnInvestedCapital"))
        if result["ROIC"] is not None and abs(result["ROIC"]) < 2:
            result["ROIC"] *= 100
        result["利益率"] = safe_num(info.get("profitMargins"))
        if result["利益率"] is not None and abs(result["利益率"]) < 2:
            result["利益率"] *= 100
        result["配当利回り"] = safe_num(info.get("dividendYield"))
        if result["配当利回り"] is not None and result["配当利回り"] < 1:
            result["配当利回り"] *= 100
        result["配当性向"] = safe_num(info.get("payoutRatio"))
        if result["配当性向"] is not None and result["配当性向"] < 2:
            result["配当性向"] *= 100

        inc = tk.financials
        cf = tk.cashflow
        bs = tk.balance_sheet
        revenues = get_series_values(inc, ["Total Revenue", "Operating Revenue"])
        op = get_series_values(inc, ["Operating Income"])
        net = get_series_values(inc, ["Net Income", "Net Income Common Stockholders"])
        cfs = get_series_values(cf, ["Operating Cash Flow", "Total Cash From Operating Activities"])
        if revenues:
            result["売上"] = revenues[0]
            if len(revenues) > 1:
                result["売上成長率"] = pct(revenues[0], revenues[1])
        if op:
            result["営業利益"] = op[0]
            if len(op) > 1:
                result["営業利益成長率"] = pct(op[0], op[1])
        if cfs:
            result["営業CF"] = cfs[0]
        if net and revenues and revenues[0] != 0:
            result["利益率"] = net[0] / revenues[0] * 100
        if net and len(net) > 1:
            result["EPS成長率"] = pct(net[0], net[1])
        if result["EPS成長率"] is None:
            result["EPS成長率"] = safe_num(info.get("earningsGrowth"))
            if result["EPS成長率"] is not None and abs(result["EPS成長率"]) < 2:
                result["EPS成長率"] *= 100
        result["EPS"] = safe_num(info.get("trailingEps"))
        result["財務データ取得"] = "取得"

        # Earnings quality: recurring/operating cash support, not special-profit inference.
        if result["営業CF"] is not None and result["営業利益"] is not None:
            if result["営業CF"] > 0 and result["営業利益"] > 0:
                result["利益品質"] = "良好"
            elif result["営業CF"] < 0 < result["営業利益"]:
                result["利益品質"] = "警戒"
            else:
                result["利益品質"] = "要確認"
        else:
            result["利益品質"] = "未判定"

        # Value trap: cheap valuation alone never adds points.
        cheap = (result["PER"] is not None and result["PER"] > 0 and result["PER"] <= 12) or (result["PBR"] is not None and result["PBR"] <= 1.0)
        deteriorating = sum(x is not None and x < -5 for x in [result["売上成長率"], result["営業利益成長率"], result["EPS成長率"]])
        weak_returns = (result["ROE"] is not None and result["ROE"] < 5)
        if cheap and (deteriorating >= 2 or weak_returns or result["利益品質"] == "警戒"):
            result["バリュートラップ"] = "警戒"
        elif cheap:
            result["バリュートラップ"] = "低バリュエーションだが要精査"
        else:
            result["バリュートラップ"] = "低バリュートラップ条件なし"

        # Shareholder return heuristics; policy text is added later when IR is available.
        if result["配当性向"] is not None:
            if result["配当性向"] < 25 and result["EPS成長率"] is not None and result["EPS成長率"] > 10:
                result["配当性向引き上げ余地"] = "高"
            elif result["配当性向"] < 40:
                result["配当性向引き上げ余地"] = "中"
            else:
                result["配当性向引き上げ余地"] = "低"
        if result["ROE"] is not None and result["ROE"] >= 10 and result["配当性向"] is not None and result["配当性向"] < 25:
            result["株主還元姿勢"] = "利益成長に対して還元余地あり"
        elif result["配当性向"] is not None and result["配当性向"] >= 40:
            result["株主還元姿勢"] = "還元水準は比較的高い"
        else:
            result["株主還元姿勢"] = "要IR確認"

        # Price/volume concentration (approximate, not individual acquisition prices).
        hist = tk.history(period="2y", auto_adjust=False)
        if hist is not None and not hist.empty and "Close" in hist and "Volume" in hist:
            px = hist["Close"].astype(float)
            vol = hist["Volume"].astype(float)
            current = result["株価"] or float(px.iloc[-1])
            bins = max(20, min(60, int(len(px) / 8)))
            lo, hi = float(px.min()), float(px.max())
            if hi > lo:
                step = (hi - lo) / bins
                buckets = {}
                for p, v in zip(px, vol):
                    b = int((float(p) - lo) / step)
                    b = min(b, bins - 1)
                    buckets[b] = buckets.get(b, 0) + float(v)
                top = sorted(buckets.items(), key=lambda x: x[1], reverse=True)[:3]
                zones = []
                for b, _ in top:
                    a = lo + b * step
                    z = a + step
                    zones.append(f"{a:.0f}～{z:.0f}円")
                result["価格帯"] = " / ".join(zones)
                nearest = min(top, key=lambda x: abs((lo + (x[0] + .5) * step) - current))
                center = lo + (nearest[0] + .5) * step
                if center > current * 1.08:
                    result["しこり判定"] = "上値しこり警戒"
                elif center < current * .92:
                    result["しこり判定"] = "下値支持候補"
                else:
                    result["しこり判定"] = "主要価格帯付近"
    except Exception as e:
        result["財務データ取得"] = f"取得エラー: {type(e).__name__}"
    return result


def score_candidate(material_score, theme, fundamentals, company_confirmed):
    score = 0
    reasons = []
    risks = []
    score += min(material_score, 35)
    if theme != "その他":
        score += 10
        reasons.append("成長テーマとの関連")
    if company_confirmed:
        score += 10
        reasons.append("企業を特定")

    for key, pts, label in [
        ("売上成長率", 8, "売上成長"),
        ("営業利益成長率", 8, "営業利益成長"),
        ("EPS成長率", 10, "EPS成長"),
        ("ROE", 5, "ROE"),
        ("ROIC", 5, "ROIC"),
    ]:
        v = fundamentals.get(key)
        if v is not None and v > 10:
            score += pts
            reasons.append(f"{label}が強い")
        elif v is not None and v < -5:
            score -= min(pts, 5)
            risks.append(f"{label}悪化")

    if fundamentals.get("営業CF") is not None and fundamentals["営業CF"] > 0:
        score += 5
        reasons.append("営業CFプラス")
    elif fundamentals.get("営業CF") is not None and fundamentals["営業CF"] < 0:
        score -= 5
        risks.append("営業CFマイナス")

    if fundamentals.get("利益品質") == "良好":
        score += 5
        reasons.append("利益の質が良好")
    elif fundamentals.get("利益品質") == "警戒":
        score -= 8
        risks.append("会計利益と営業CFの乖離")

    if fundamentals.get("バリュートラップ") == "警戒":
        score -= 20
        risks.append("バリュートラップ警戒")

    if fundamentals.get("配当性向引き上げ余地") == "高":
        score += 5
        reasons.append("配当性向引き上げ余地が高い")
    if fundamentals.get("株主還元姿勢") == "利益成長に対して還元余地あり":
        score += 3
        reasons.append("株主還元余地")
    if fundamentals.get("しこり判定") == "上値しこり警戒":
        risks.append("上値しこり")
    elif fundamentals.get("しこり判定") == "下値支持候補":
        score += 3
        reasons.append("下値支持候補")

    return max(0, min(100, score)), reasons, risks


def importance(score):
    if score >= 75: return "🔥 最優先調査"
    if score >= 60: return "🟠 優先調査"
    if score >= 45: return "🟡 注目"
    return "⚪ 監視"


def collect_news():
    results = []
    for theme, feeds in RSS_FEEDS.items():
        for url in feeds:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:25]:
                    title = normalize_text(entry.get("title", ""))
                    link = entry.get("link", "")
                    published = entry.get("published", "")
                    if not title:
                        continue
                    text = f"{title} {published}"
                    material, material_score = detect_material(text)
                    detected_theme = detect_theme(text)
                    candidates = company_candidates(title)
                    # Only enrich a small number per article to keep GitHub Actions free/fast.
                    if not candidates:
                        results.append({
                            "取得日": datetime.now(JST).strftime("%Y-%m-%d"),
                            "テーマ": detected_theme, "企業": "未特定", "証券コード": "未特定",
                            "材料": material, "重要度": importance(material_score), "総合スコア": material_score,
                            "理由": "企業未特定。ニュースの材料を監視", "リスク": "企業特定後に要再評価",
                            "PER": "未取得", "PBR": "未取得", "EPS成長率": "未取得", "売上成長率": "未取得",
                            "営業利益成長率": "未取得", "営業CF": "未取得", "ROE": "未取得", "ROIC": "未取得",
                            "時価総額": "未取得", "利益品質": "未判定", "バリュートラップ": "未判定",
                            "配当性向引き上げ余地": "未判定", "株主還元姿勢": "未判定", "価格帯": "未取得",
                            "しこり判定": "未判定", "タイトル": title, "原文タイトル": title,
                            "公開日時": published, "URL": link,
                        })
                        continue
                    for name, ticker, source in candidates[:2]:
                        f = calculate_financial_quality(ticker)
                        score, reasons, risks = score_candidate(material_score, detected_theme, f, True)
                        results.append({
                            "取得日": datetime.now(JST).strftime("%Y-%m-%d"),
                            "テーマ": detected_theme,
                            "企業": f.get("企業名") if f.get("企業名") != "未取得" else name,
                            "証券コード": ticker,
                            "材料": material,
                            "重要度": importance(score),
                            "総合スコア": score,
                            "理由": " / ".join(reasons) if reasons else "要追加調査",
                            "リスク": " / ".join(risks) if risks else "主要な警戒条件は未検出",
                            "PER": f.get("PER") if f.get("PER") is not None else "未取得",
                            "PBR": f.get("PBR") if f.get("PBR") is not None else "未取得",
                            "EPS成長率": f.get("EPS成長率") if f.get("EPS成長率") is not None else "未取得",
                            "売上成長率": f.get("売上成長率") if f.get("売上成長率") is not None else "未取得",
                            "営業利益成長率": f.get("営業利益成長率") if f.get("営業利益成長率") is not None else "未取得",
                            "営業CF": fmt_num(f.get("営業CF")),
                            "ROE": f.get("ROE") if f.get("ROE") is not None else "未取得",
                            "ROIC": f.get("ROIC") if f.get("ROIC") is not None else "未取得",
                            "時価総額": fmt_num(f.get("時価総額")),
                            "利益品質": f.get("利益品質"),
                            "バリュートラップ": f.get("バリュートラップ"),
                            "配当性向引き上げ余地": f.get("配当性向引き上げ余地"),
                            "株主還元姿勢": f.get("株主還元姿勢"),
                            "価格帯": f.get("価格帯"),
                            "しこり判定": f.get("しこり判定"),
                            "タイトル": title, "原文タイトル": title, "公開日時": published, "URL": link,
                        })
            except Exception as e:
                print(f"RSS取得エラー: {url} / {e}")
    return results


def remove_duplicates(rows):
    seen = set(); out = []
    for r in rows:
        key = (r["証券コード"], r["タイトル"].lower())
        if key in seen: continue
        seen.add(key); out.append(r)
    return out


def save_csv(rows):
    os.makedirs("data", exist_ok=True)
    today = datetime.now(JST).strftime("%Y-%m-%d")
    path = f"data/radar_{today}.csv"
    fields = list(rows[0].keys()) if rows else ["取得日"]
    rows.sort(key=lambda x: float(x["総合スコア"]) if str(x["総合スコア"]).replace('.','',1).isdigit() else -1, reverse=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(rows)
    return path


def save_top(rows):
    os.makedirs("data", exist_ok=True)
    today = datetime.now(JST).strftime("%Y-%m-%d")
    path = f"data/top_candidates_{today}.md"
    ranked = [r for r in rows if r.get("証券コード") != "未特定"][:20]
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# Future Stock Radar v3 — {today}\n\n")
        f.write("> 調査優先度であり、売買推奨ではありません。未取得データは推測していません。\n\n")
        for i, r in enumerate(ranked, 1):
            f.write(f"## {i}位 {r['企業']}（{r['証券コード']}） — {r['総合スコア']}/100\n")
            f.write(f"- テーマ：{r['テーマ']}\n- 材料：{r['材料']}\n- 判定：{r['重要度']}\n")
            f.write(f"- PER：{r['PER']} / PBR：{r['PBR']}\n")
            f.write(f"- 売上成長率：{r['売上成長率']} / 営業利益成長率：{r['営業利益成長率']} / EPS成長率：{r['EPS成長率']}\n")
            f.write(f"- 営業CF：{r['営業CF']} / ROE：{r['ROE']} / ROIC：{r['ROIC']}\n")
            f.write(f"- 時価総額：{r['時価総額']}\n- 利益品質：{r['利益品質']}\n- バリュートラップ：{r['バリュートラップ']}\n")
            f.write(f"- 配当性向引き上げ余地：{r['配当性向引き上げ余地']}\n- 株主還元姿勢：{r['株主還元姿勢']}\n")
            f.write(f"- 価格帯：{r['価格帯']} / しこり判定：{r['しこり判定']}\n")
            f.write(f"- 理由：{r['理由']}\n- リスク：{r['リスク']}\n")
            f.write(f"- 原文：{r['原文タイトル']}\n- URL：{r['URL']}\n\n")
    return path


def main():
    print("=" * 70)
    print("Future Stock Radar v3 — Tenbagger Early Research Radar")
    print("=" * 70)
    rows = remove_duplicates(collect_news())
    csv_path = save_csv(rows)
    top_path = save_top(rows)
    print(f"取得・評価件数: {len(rows)}")
    print(f"CSV: {csv_path}")
    print(f"TOP: {top_path}")
    for r in rows[:10]:
        print(f"[{r['総合スコア']:>3}] {r['企業']} {r['証券コード']} | {r['テーマ']} | {r['重要度']}")

if __name__ == "__main__":
    main()
