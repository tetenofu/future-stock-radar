import csv
import os
import re
import math
from collections import defaultdict
from datetime import datetime, timezone, timedelta

import feedparser
import yfinance as yf

JST = timezone(timedelta(hours=9))
TODAY = datetime.now(JST).strftime('%Y-%m-%d')

RSS_FEEDS = {
    'AIデータセンター': [
        'https://news.google.com/rss/search?q=AI+data+center&hl=en-US&gl=US&ceid=US:en',
        'https://news.google.com/rss/search?q=AI+データセンター&hl=ja&gl=JP&ceid=JP:ja',
        'https://news.google.com/rss/search?q=データセンター+電力&hl=ja&gl=JP&ceid=JP:ja',
    ],
    '光通信': [
        'https://news.google.com/rss/search?q=co-packaged+optics&hl=en-US&gl=US&ceid=US:en',
        'https://news.google.com/rss/search?q=silicon+photonics&hl=en-US&gl=US&ceid=US:en',
        'https://news.google.com/rss/search?q=光通信+シリコンフォトニクス&hl=ja&gl=JP&ceid=JP:ja',
        'https://news.google.com/rss/search?q=IOWN+光通信&hl=ja&gl=JP&ceid=JP:ja',
    ],
    '冷却・熱管理': [
        'https://news.google.com/rss/search?q=liquid+cooling+data+center&hl=en-US&gl=US&ceid=US:en',
        'https://news.google.com/rss/search?q=immersion+cooling&hl=en-US&gl=US&ceid=US:en',
        'https://news.google.com/rss/search?q=データセンター+液冷&hl=ja&gl=JP&ceid=JP:ja',
        'https://news.google.com/rss/search?q=半導体+冷却+熱管理&hl=ja&gl=JP&ceid=JP:ja',
    ],
    '電力・蓄電': [
        'https://news.google.com/rss/search?q=data+center+power+grid&hl=en-US&gl=US&ceid=US:en',
        'https://news.google.com/rss/search?q=energy+storage+data+center&hl=en-US&gl=US&ceid=US:en',
        'https://news.google.com/rss/search?q=データセンター+電力+蓄電&hl=ja&gl=JP&ceid=JP:ja',
        'https://news.google.com/rss/search?q=蓄電池+送電網&hl=ja&gl=JP&ceid=JP:ja',
    ],
    '半導体': [
        'https://news.google.com/rss/search?q=advanced+packaging+semiconductor&hl=en-US&gl=US&ceid=US:en',
        'https://news.google.com/rss/search?q=chiplet+HBM&hl=en-US&gl=US&ceid=US:en',
        'https://news.google.com/rss/search?q=compound+semiconductor+GaN+SiC&hl=en-US&gl=US&ceid=US:en',
        'https://news.google.com/rss/search?q=半導体+先端パッケージ+HBM&hl=ja&gl=JP&ceid=JP:ja',
        'https://news.google.com/rss/search?q=GaN+SiC+半導体&hl=ja&gl=JP&ceid=JP:ja',
    ],
    '宇宙': [
        'https://news.google.com/rss/search?q=space+data+center&hl=en-US&gl=US&ceid=US:en',
        'https://news.google.com/rss/search?q=satellite+computing+optical+communication&hl=en-US&gl=US&ceid=US:en',
        'https://news.google.com/rss/search?q=宇宙+データセンター&hl=ja&gl=JP&ceid=JP:ja',
        'https://news.google.com/rss/search?q=衛星+光通信&hl=ja&gl=JP&ceid=JP:ja',
    ],
    '宇宙熱管理': [
        'https://news.google.com/rss/search?q=spacecraft+thermal+management+radiator&hl=en-US&gl=US&ceid=US:en',
        'https://news.google.com/rss/search?q=宇宙+熱管理+ラジエーター&hl=ja&gl=JP&ceid=JP:ja',
    ],
    '宇宙太陽光・発電': [
        'https://news.google.com/rss/search?q=space+solar+power&hl=en-US&gl=US&ceid=US:en',
        'https://news.google.com/rss/search?q=宇宙太陽光+発電&hl=ja&gl=JP&ceid=JP:ja',
    ],
}

MATERIALS = {
    '大型受注': (['order', 'orders', 'purchase order', 'follow-on order', 'contract', '受注', '大型受注', '契約'], 30),
    '量産・生産開始': (['production', 'mass production', 'volume production', 'manufacturing', '量産', '生産開始'], 25),
    '大企業との提携': (['partnership', 'strategic partnership', 'collaboration', 'alliance', '提携', '協業', '共同開発'], 25),
    '戦略的投資': (['strategic investment', 'invests', 'funding', '出資', '戦略投資'], 22),
    '政府支援': (['government', 'subsidy', 'grant', 'government funding', '政府', '補助金', '助成金'], 20),
    '特許・技術': (['patent', 'patented', 'intellectual property', 'breakthrough', 'new technology', '特許', '新技術', '技術革新'], 15),
    '研究開発': (['research', 'development', 'r&d', 'demonstration', 'prototype', '研究', '開発', '実証', '試作'], 12),
    '設備投資': (['capital expenditure', 'capex', 'factory expansion', 'facility expansion', 'new facility', '設備投資', '工場増設'], 18),
    '業績上方修正': (['raises outlook', 'raised guidance', 'higher revenue', 'record revenue', 'record sales', '上方修正', '最高益', '増収'], 30),
}

# Conservative aliases. Unknown companies are left unclassified rather than guessed.
COMPANY_ALIASES = {
    'NTT': '9432.T', '日本電信電話': '9432.T',
    '東京海上': '8766.T', '東京海上ホールディングス': '8766.T',
    'キオクシア': '285A.T', 'Kioxia': '285A.T',
    'メディアリンクス': '6659.T', 'Media Links': '6659.T',
    '海帆': '3133.T', 'Kopin': 'KOPN',
    '京セラ': '6971.T', 'Kyocera': '6971.T',
    'ソフトバンク': '9434.T', 'SoftBank Corp.': '9434.T',
    '富士通': '6702.T', 'Fujitsu': '6702.T',
    'NEC': '6701.T', '日本電気': '6701.T',
    '日立': '6501.T', 'Hitachi': '6501.T',
    '三菱重工': '7011.T', 'Mitsubishi Heavy Industries': '7011.T',
    '古野電気': '6814.T', 'Furuno': '6814.T',
    '浜松ホトニクス': '6965.T', 'Hamamatsu Photonics': '6965.T',
    '住友電工': '5802.T', 'Sumitomo Electric': '5802.T',
    'フジクラ': '5803.T', 'Fujikura': '5803.T',
    'アドバンテスト': '6857.T', 'Advantest': '6857.T',
    'ディスコ': '6146.T', 'Disco': '6146.T',
    '東京エレクトロン': '8035.T', 'Tokyo Electron': '8035.T',
    'ソシオネクスト': '6526.T', 'Socionext': '6526.T',
    '信越化学': '4063.T', 'Shin-Etsu': '4063.T',
    'ローム': '6963.T', 'ROHM': '6963.T',
    'レーザーテック': '6920.T', 'Lasertec': '6920.T',
    'Aehr Test Systems': 'AEHR', 'Amkor Technology': 'AMKR',
    'Advanced Micro Devices': 'AMD', 'AMD': 'AMD',
    'NVIDIA': 'NVDA', 'Nvidia': 'NVDA',
    'Broadcom': 'AVGO', 'Marvell': 'MRVL',
    'Micron': 'MU', 'Micron Technology': 'MU',
    'Intel': 'INTC', 'Applied Materials': 'AMAT',
    'Lam Research': 'LRCX', 'Coherent': 'COHR',
    'Lumentum': 'LITE', 'Corning': 'GLW',
    'Vertiv': 'VRT', 'Super Micro Computer': 'SMCI',
    'Arista Networks': 'ANET', 'Cisco': 'CSCO',
    'Equinix': 'EQIX', 'Digital Realty': 'DLR',
    'Excelerate Energy': 'EE', 'Thales': 'HO.PA',
    'MBRYONICS': None,
}

IGNORE_TICKERS = {
    'AI','US','CEO','GPU','HBM','R&D','USD','NASA','DOE','ROE','ROIC','PBR','PER','CF',
    'EPS','EV','EBITDA','IPO','IR','SEC','EU','UK','U.S','USA','THE','AND','FOR','NEW','INC','LTD',
}
TICKER_RE = re.compile(r'(?<![A-Z])\$?([A-Z]{2,5})(?:\.([A-Z]{1,3}))?(?![A-Z])')
JP_EXPLICIT_CODE_RE = re.compile(r'(?<!\d)(\d{4})\.T(?!\d)', re.I)
JP_MARKED_CODE_RE = re.compile(r'(?:証券コード|銘柄コード|コード|ticker|code)\s*[:：#]?\s*(\d{4})(?!\d)', re.I)
NON_EQUITY_WORDS = ('etf','etn','fund','trust','index','futures','future','leveraged','inverse','bear','bull','note','notes','commodity','bond','reit')


def normalize_text(text):
    return re.sub(r'\s+', ' ', text or '').strip()


def detect_theme(text):
    t = text.lower()
    rules = {
        'AIデータセンター': ['ai data center', 'data center', 'データセンター', 'hyperscale'],
        '光通信': ['co-packaged optics', 'silicon photonics', 'optical i/o', 'optical interconnect', '光通信', 'フォトニクス', 'iown'],
        '冷却・熱管理': ['liquid cooling', 'immersion cooling', 'thermal management', 'heat exchanger', '液冷', '熱管理', 'ラジエーター'],
        '電力・蓄電': ['data center power', 'energy storage', 'fuel cell', 'grid', '蓄電', '送電', '電力'],
        '半導体': ['advanced packaging', 'chiplet', 'hbm', 'compound semiconductor', 'gan', 'sic', '半導体', '先端パッケージ'],
        '宇宙': ['space data center', 'orbital data center', 'satellite computing', 'space optical communication', '宇宙', '衛星'],
        '宇宙熱管理': ['space radiator', 'spacecraft thermal', 'heat rejection', '宇宙熱', '宇宙機熱'],
        '宇宙太陽光・発電': ['space solar power', 'space solar panel', 'space energy', '宇宙太陽光'],
    }
    for theme, keys in rules.items():
        if any(k in t for k in keys):
            return theme
    return 'その他'


def detect_material(text):
    t = text.lower()
    found, score = [], 0
    for material, (keys, pts) in MATERIALS.items():
        if any(k.lower() in t for k in keys):
            found.append(material)
            score += pts
    return (' / '.join(found) if found else 'テーマ関連ニュース'), min(score, 100)


def company_candidates(text):
    lower = text.lower()
    found = []
    for alias, ticker in COMPANY_ALIASES.items():
        if not ticker:
            continue
        # Company aliases are matched as explicit names; avoid loose generic acronyms.
        if alias.lower() in lower:
            found.append((alias, ticker, 'alias'))

    # Japanese stock codes are accepted ONLY when explicitly written as 1234.T
    # or accompanied by a clear code marker. Bare 4-digit numbers are never tickers.
    for m in JP_EXPLICIT_CODE_RE.finditer(text):
        found.append((m.group(1), m.group(1) + '.T', 'explicit_code'))
    for m in JP_MARKED_CODE_RE.finditer(text):
        found.append((m.group(1), m.group(1) + '.T', 'marked_code'))

    known_tickers = {t for t in COMPANY_ALIASES.values() if t}
    known_plain = {t.split('.')[0] for t in known_tickers}
    for m in TICKER_RE.finditer(text):
        token = m.group(1)
        if token in IGNORE_TICKERS:
            continue
        if token in known_plain:
            found.append((token, token, 'ticker'))

    out, seen = [], set()
    for name, ticker, source in found:
        if ticker in seen:
            continue
        seen.add(ticker)
        out.append((name, ticker, source))
    return out[:5]


def safe_num(x):
    try:
        if x is None:
            return None
        v = float(x)
        return None if math.isnan(v) or math.isinf(v) else v
    except Exception:
        return None


def pct(new, old):
    new, old = safe_num(new), safe_num(old)
    if new is None or old in (None, 0):
        return None
    return (new / old - 1) * 100


def normalize_ratio(value, percent=True):
    v = safe_num(value)
    if v is None:
        return None
    if percent and abs(v) <= 2:
        return v * 100
    return v


def fmt_num(x):
    if x is None:
        return '未取得'
    x = float(x)
    sign = '-' if x < 0 else ''
    a = abs(x)
    if a >= 1e12: return f'{sign}{a/1e12:.2f}兆'
    if a >= 1e8: return f'{sign}{a/1e8:.1f}億'
    if a >= 1e4: return f'{sign}{a/1e4:.1f}万'
    return f'{x:.2f}'


def get_series_values(frame, row_names, periods=5):
    if frame is None or getattr(frame, 'empty', True):
        return []
    for row in row_names:
        if row in frame.index:
            pairs = []
            for col in frame.columns:
                v = safe_num(frame.loc[row, col])
                if v is not None:
                    try:
                        pairs.append((col, v))
                    except Exception:
                        pairs.append((str(col), v))
            pairs.sort(key=lambda x: str(x[0]), reverse=True)
            vals = [v for _, v in pairs[:periods]]
            if vals:
                return vals
    return []


def volume_profile(hist, current, currency):
    if hist is None or hist.empty or 'Close' not in hist or 'Volume' not in hist:
        return '未取得', '未判定'
    try:
        px = hist['Close'].astype(float)
        vol = hist['Volume'].astype(float)
        mask = (px > 0) & (vol >= 0)
        px, vol = px[mask], vol[mask]
        if len(px) < 60:
            return '未取得', '未判定'
        current = safe_num(current) or float(px.iloc[-1])
        lo, hi = float(px.min()), float(px.max())
        if hi <= lo or current <= 0:
            return '未取得', '未判定'
        # 30 price bins; aggregate volume at price, not individual acquisition prices.
        bins = min(50, max(24, int(len(px) / 10)))
        step = (hi - lo) / bins
        buckets = defaultdict(float)
        for p, v in zip(px, vol):
            idx = min(bins - 1, max(0, int((float(p) - lo) / step)))
            buckets[idx] += float(v)
        total = sum(buckets.values()) or 1
        top = sorted(buckets.items(), key=lambda x: x[1], reverse=True)[:5]
        zones = []
        for idx, v in top[:3]:
            a, b = lo + idx * step, lo + (idx + 1) * step
            share = v / total * 100
            zones.append((a, b, share))
        def money(v):
            return f'{v:.0f}{currency}' if currency == '円' else f'${v:.2f}'
        zone_text = ' / '.join(f'{money(a)}～{money(b)}（出来高比{share:.1f}%）' for a,b,share in zones)
        above = [z for z in zones if z[0] > current * 1.05]
        below = [z for z in zones if z[1] < current * 0.95]
        if above:
            nearest = min(above, key=lambda z: z[0] - current)
            verdict = '上値しこり警戒'
            if current > nearest[1]:
                verdict = 'しこり吸収・上抜け候補'
        elif below:
            verdict = '下値支持候補'
        else:
            verdict = '主要価格帯付近'
        return zone_text, verdict
    except Exception:
        return '未取得', '未判定'


def calculate_financial_quality(ticker, cache):
    if ticker in cache:
        return cache[ticker]
    r = {
        'ティッカー': ticker, '企業名': '未取得', '市場': '未取得', '通貨': '円' if ticker.endswith('.T') else '$',
        '時価総額': None, '株価': None, '売上': None, '売上成長率': None,
        '営業利益': None, '営業利益成長率': None, 'EPS': None, 'EPS成長率': None,
        '営業CF': None, 'ROE': None, 'ROIC': None, '利益率': None,
        'PER': None, 'PBR': None, 'PSR': None, '配当利回り': None, '配当性向': None,
        '自己株買い': '未取得', '利益品質': '未判定', 'バリュートラップ': '未判定',
        '配当性向引き上げ余地': '未判定', '株主還元姿勢': '未判定',
        '価格帯': '未取得', 'しこり判定': '未判定', '財務データ取得': '未取得', '実在確認': '未確認', '候補種別': '未判定', '企業関与': '要確認',
    }
    try:
        tk = yf.Ticker(ticker)
        info = tk.info or {}
        r['企業名'] = info.get('longName') or info.get('shortName') or '未取得'
        quote_type = str(info.get('quoteType') or '').upper()
        security_name = str(r['企業名'] or '').lower()
        exchange_name = str(info.get('exchange') or '').lower()
        is_equity = quote_type == 'EQUITY'
        is_non_equity_name = any(w in security_name for w in NON_EQUITY_WORDS)
        if is_equity and not is_non_equity_name:
            r['実在確認'] = '確認済'
            r['候補種別'] = '事業会社'
        else:
            r['実在確認'] = '除外'
            r['候補種別'] = '非株式・投資商品'
            raise ValueError(f'非株式商品または株式確認不可: quoteType={quote_type}, name={r["企業名"]}, exchange={exchange_name}')
        r['市場'] = info.get('exchange') or info.get('fullExchangeName') or '未取得'
        r['通貨'] = info.get('currency') or r['通貨']
        if r['通貨'] == 'JPY': r['通貨'] = '円'
        elif r['通貨'] == 'USD': r['通貨'] = '$'
        r['時価総額'] = safe_num(info.get('marketCap'))
        r['株価'] = safe_num(info.get('currentPrice') or info.get('regularMarketPrice'))
        r['PER'] = safe_num(info.get('trailingPE'))
        r['PBR'] = safe_num(info.get('priceToBook'))
        r['PSR'] = safe_num(info.get('priceToSalesTrailing12Months'))
        r['ROE'] = normalize_ratio(info.get('returnOnEquity'))
        r['ROIC'] = normalize_ratio(info.get('returnOnInvestedCapital'))
        r['利益率'] = normalize_ratio(info.get('profitMargins'))
        r['配当利回り'] = normalize_ratio(info.get('dividendYield'))
        r['配当性向'] = normalize_ratio(info.get('payoutRatio'))

        inc, cf = tk.financials, tk.cashflow
        revenues = get_series_values(inc, ['Total Revenue', 'Operating Revenue'])
        op = get_series_values(inc, ['Operating Income'])
        net = get_series_values(inc, ['Net Income', 'Net Income Common Stockholders'])
        eps = get_series_values(inc, ['Diluted EPS', 'Basic EPS', 'Normalized Diluted EPS'])
        cfs = get_series_values(cf, ['Operating Cash Flow', 'Total Cash From Operating Activities'])
        special = get_series_values(inc, ['Special Income Charges', 'Gain On Sale Of Security', 'Other Non Operating Income Expenses'])
        if revenues:
            r['売上'] = revenues[0]; r['売上成長率'] = pct(revenues[0], revenues[1]) if len(revenues)>1 else None
        if op:
            r['営業利益'] = op[0]; r['営業利益成長率'] = pct(op[0], op[1]) if len(op)>1 else None
        if cfs: r['営業CF'] = cfs[0]
        if eps:
            r['EPS'] = eps[0]; r['EPS成長率'] = pct(eps[0], eps[1]) if len(eps)>1 else None
        if r['EPS'] is None: r['EPS'] = safe_num(info.get('trailingEps'))
        if r['EPS成長率'] is None:
            r['EPS成長率'] = normalize_ratio(info.get('earningsGrowth'))
        if net and revenues and revenues[0] != 0 and r['利益率'] is None:
            r['利益率'] = net[0] / revenues[0] * 100

        # Conservative recurring-earnings quality heuristic.
        if r['営業CF'] is not None and r['営業利益'] is not None:
            if r['営業CF'] > 0 and r['営業利益'] > 0:
                r['利益品質'] = '良好'
            elif r['営業利益'] > 0 and r['営業CF'] < 0:
                r['利益品質'] = '警戒'
            elif r['営業CF'] < 0 and r['営業利益'] < 0:
                r['利益品質'] = '赤字・要注意'
            else:
                r['利益品質'] = '要確認'
        # Special-item flag only when a recognizable special-income row is materially large.
        if special and net and net[0] != 0:
            sp = abs(special[0])
            if sp > abs(net[0]) * 0.25:
                r['利益品質'] = '特別損益影響を要確認'

        cheap = ((r['PER'] is not None and 0 < r['PER'] <= 12) or (r['PBR'] is not None and 0 < r['PBR'] <= 1.0))
        growths = [r['売上成長率'], r['営業利益成長率'], r['EPS成長率']]
        deteriorating = sum(v is not None and v < -5 for v in growths)
        weak_returns = r['ROE'] is not None and r['ROE'] < 5
        if cheap and (deteriorating >= 2 or weak_returns or r['利益品質'] in ('警戒','赤字・要注意','特別損益影響を要確認')):
            r['バリュートラップ'] = '警戒'
        elif cheap:
            r['バリュートラップ'] = '低バリュエーションだが要精査'
        else:
            r['バリュートラップ'] = '低バリュートラップ条件なし'

        if r['配当性向'] is not None:
            if r['配当性向'] < 25 and r['EPS成長率'] is not None and r['EPS成長率'] > 10:
                r['配当性向引き上げ余地'] = '高'
            elif r['配当性向'] < 40:
                r['配当性向引き上げ余地'] = '中'
            else:
                r['配当性向引き上げ余地'] = '低'
        if r['ROE'] is not None and r['ROE'] >= 10 and r['配当性向'] is not None and r['配当性向'] < 25:
            r['株主還元姿勢'] = '利益成長に対して還元余地あり'
        elif r['配当性向'] is not None and r['配当性向'] >= 40:
            r['株主還元姿勢'] = '還元水準は比較的高い'
        else:
            r['株主還元姿勢'] = '要IR確認'

        hist = tk.history(period='2y', auto_adjust=False)
        r['価格帯'], r['しこり判定'] = volume_profile(hist, r['株価'], r['通貨'])
        r['財務データ取得'] = '取得'
    except Exception as e:
        if r.get('実在確認') != '確認済':
            r['実在確認'] = '未確認' if r.get('実在確認') == '未確認' else r.get('実在確認')
            r['候補種別'] = '未確認' if r.get('候補種別') == '未判定' else r.get('候補種別')
        r['財務データ取得'] = f'取得エラー: {type(e).__name__}'
    cache[ticker] = r
    return r


def score_candidate(article_score, theme, fundamentals, article_count, theme_count):
    score = min(article_score, 35)
    reasons, risks = [], []
    if theme != 'その他': score += 10; reasons.append('成長テーマとの関連')
    # News volume is evidence, not a proxy for company quality. Cap it tightly.
    score += min(4, max(0, article_count - 1))
    if article_count >= 2: reasons.append(f'複数材料を検出（{article_count}件）')
    if theme_count >= 2: score += 3; reasons.append(f'複数テーマ接点（{theme_count}）')
    for key, pts, label in [('売上成長率',8,'売上成長'),('営業利益成長率',8,'営業利益成長'),('EPS成長率',10,'EPS成長'),('ROE',5,'ROE'),('ROIC',5,'ROIC')]:
        v = fundamentals.get(key)
        if v is not None and v > 10: score += pts; reasons.append(f'{label}が強い')
        elif v is not None and v < -5: score -= min(pts,5); risks.append(f'{label}悪化')
    cf = fundamentals.get('営業CF')
    if cf is not None and cf > 0: score += 5; reasons.append('営業CFプラス')
    elif cf is not None and cf < 0: score -= 5; risks.append('営業CFマイナス')
    if fundamentals.get('利益品質') == '良好': score += 5; reasons.append('利益の質が良好')
    elif fundamentals.get('利益品質') in ('警戒','赤字・要注意','特別損益影響を要確認'):
        score -= 8; risks.append(f"利益品質：{fundamentals.get('利益品質')}")
    if fundamentals.get('バリュートラップ') == '警戒': score -= 20; risks.append('バリュートラップ警戒')
    elif fundamentals.get('バリュートラップ') == '低バリュエーションだが要精査': reasons.append('低バリュエーションだが成長・CFを要確認')
    if fundamentals.get('配当性向引き上げ余地') == '高': score += 5; reasons.append('配当性向引き上げ余地が高い')
    if fundamentals.get('株主還元姿勢') == '利益成長に対して還元余地あり': score += 3; reasons.append('株主還元余地')
    # Tenbagger room: large incumbents should not outrank smaller companies solely on news volume.
    mc = fundamentals.get('時価総額')
    if mc is not None:
        if mc < 1e11: score += 10; reasons.append('小型株で時価総額余地')
        elif mc < 5e11: score += 7; reasons.append('中小型で時価総額余地')
        elif mc < 1e12: score += 4
        elif mc < 3e12: score += 1
        elif mc >= 1e13: score -= 8; risks.append('時価総額が大きく10倍余地は限定的')

    trap = fundamentals.get('しこり判定')
    if trap == '上値しこり警戒': risks.append('上値しこり')
    elif trap == '下値支持候補': score += 3; reasons.append('下値支持候補')
    elif trap == 'しこり吸収・上抜け候補': score += 5; reasons.append('上値しこり吸収・上抜け候補')
    return max(0, min(100, score)), reasons, risks


def importance(score):
    if score >= 75: return '🔥 最優先調査'
    if score >= 60: return '🟠 優先調査'
    if score >= 45: return '🟡 注目'
    return '⚪ 監視'


def collect_news():
    articles = []
    for feed_theme, feeds in RSS_FEEDS.items():
        for url in feeds:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:25]:
                    title = normalize_text(entry.get('title',''))
                    summary = normalize_text(re.sub('<[^>]+>', ' ', entry.get('summary','')))
                    link = entry.get('link','')
                    published = entry.get('published','')
                    if not title: continue
                    text = f'{title} {summary}'
                    material, material_score = detect_material(text)
                    detected_theme = detect_theme(text)
                    candidates = company_candidates(text)
                    articles.append({
                        '取得日': TODAY, 'テーマ': detected_theme if detected_theme != 'その他' else feed_theme,
                        '企業候補': candidates, '材料': material, '材料スコア': material_score,
                        'タイトル': title, '原文タイトル': title, '公開日時': published, 'URL': link,
                    })
            except Exception as e:
                print(f'RSS取得エラー: {url} / {e}')
    return articles


def build_company_rows(articles):
    by_ticker = defaultdict(list)
    for a in articles:
        for name, ticker, source in a['企業候補']:
            by_ticker[ticker].append((a, name, source))

    cache = {}
    rows = []
    # Limit enrichment to the strongest 80 tickers by news evidence to keep the free workflow stable.
    ranked_tickers = sorted(by_ticker, key=lambda t: (max(x[0]['材料スコア'] for x in by_ticker[t]), len(by_ticker[t])), reverse=True)[:80]
    for ticker in ranked_tickers:
        items = by_ticker[ticker]
        f = calculate_financial_quality(ticker, cache)
        if f.get('実在確認') != '確認済' or f.get('候補種別') != '事業会社':
            print(f'候補除外: {ticker} / {f.get("企業名")} / {f.get("財務データ取得")}')
            continue
        unique_articles = {x[0]['URL'] or x[0]['タイトル'] for x in items}
        unique_themes = {x[0]['テーマ'] for x in items}
        best = max(items, key=lambda x: x[0]['材料スコア'])
        a = best[0]
        score, reasons, risks = score_candidate(a['材料スコア'], a['テーマ'], f, len(unique_articles), len(unique_themes))
        rows.append(make_row(a, f, ticker, score, reasons, risks, len(unique_articles), len(unique_themes), items))
    return rows


def make_row(a, f, ticker, score, reasons, risks, article_count, theme_count, items):
    def val(key):
        return f.get(key) if f.get(key) is not None else '未取得'
    return {
        '取得日': TODAY, 'テーマ': a['テーマ'], '企業': f.get('企業名') if f.get('企業名') != '未取得' else ticker,
        '証券コード・ティッカー': ticker, '実在確認': f.get('実在確認','未確認'), '候補種別': f.get('候補種別','未判定'), '市場': f.get('市場','未取得'), '通貨': f.get('通貨','$'),
        '材料': a['材料'], '材料件数': article_count, 'テーマ接点数': theme_count,
        '重要度': importance(score), '総合スコア': score, '理由': ' / '.join(reasons) if reasons else '要追加調査',
        'リスク': ' / '.join(risks) if risks else '主要な警戒条件は未検出',
        '株価': val('株価'), 'PER': val('PER'), 'PBR': val('PBR'), 'PSR': val('PSR'), 'EPS': val('EPS'),
        'EPS成長率': val('EPS成長率'), '売上': fmt_num(f.get('売上')), '売上成長率': val('売上成長率'),
        '営業利益': fmt_num(f.get('営業利益')), '営業利益成長率': val('営業利益成長率'), '営業CF': fmt_num(f.get('営業CF')),
        'ROE': val('ROE'), 'ROIC': val('ROIC'), '利益率': val('利益率'), '時価総額': fmt_num(f.get('時価総額')),
        '配当利回り': val('配当利回り'), '配当性向': val('配当性向'), '利益品質': f.get('利益品質'),
        'バリュートラップ': f.get('バリュートラップ'), '配当性向引き上げ余地': f.get('配当性向引き上げ余地'),
        '株主還元姿勢': f.get('株主還元姿勢'), '価格帯': f.get('価格帯'), 'しこり判定': f.get('しこり判定'),
        'タイトル': a['タイトル'], '原文タイトル': a['原文タイトル'], '公開日時': a['公開日時'], 'URL': a['URL'],
        '関連タイトル数': len(items), '企業関与': '直接候補' if any(x[2] in ('alias','ticker') for x in items) else 'コード経由・要確認',
    }


def build_unidentified_rows(articles):
    rows = []
    for a in articles:
        if a['企業候補']: continue
        rows.append({
            '取得日': TODAY, 'テーマ': a['テーマ'], '企業': '未特定', '証券コード・ティッカー': '未特定', '実在確認': '未確認', '候補種別': '未特定',
            '市場':'未取得','通貨':'未取得','材料':a['材料'],'材料件数':1,'テーマ接点数':1,
            '重要度':importance(a['材料スコア']),'総合スコア':a['材料スコア'],'理由':'企業未特定。材料の企業帰属を確認',
            'リスク':'企業特定前のため評価未確定','株価':'未取得','PER':'未取得','PBR':'未取得','PSR':'未取得','EPS':'未取得',
            'EPS成長率':'未取得','売上':'未取得','売上成長率':'未取得','営業利益':'未取得','営業利益成長率':'未取得',
            '営業CF':'未取得','ROE':'未取得','ROIC':'未取得','利益率':'未取得','時価総額':'未取得','配当利回り':'未取得',
            '配当性向':'未取得','利益品質':'未判定','バリュートラップ':'未判定','配当性向引き上げ余地':'未判定',
            '株主還元姿勢':'未判定','価格帯':'未取得','しこり判定':'未判定','タイトル':a['タイトル'],
            '原文タイトル':a['原文タイトル'],'公開日時':a['公開日時'],'URL':a['URL'],'関連タイトル数':1,
        })
    return rows


def save_csv(rows):
    os.makedirs('data', exist_ok=True)
    path = f'data/radar_{TODAY}.csv'
    fields = list(rows[0].keys()) if rows else ['取得日']
    rows.sort(key=lambda x: safe_num(x.get('総合スコア')) or -1, reverse=True)
    with open(path,'w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
    return path


def save_top(rows):
    os.makedirs('data', exist_ok=True)
    path = f'data/top_candidates_{TODAY}.md'
    ranked = [r for r in rows if r.get('証券コード・ティッカー') != '未特定'][:20]
    with open(path,'w',encoding='utf-8') as f:
        f.write(f'# Future Stock Radar v3.2 — {TODAY}\n\n')
        f.write('> 調査優先度であり、売買推奨ではありません。未取得データは推測していません。\n\n')
        for i,r in enumerate(ranked,1):
            f.write(f"## {i}位 {r['企業']}（{r['証券コード・ティッカー']}） — {r['総合スコア']}/100\n")
            f.write(f"- テーマ：{r['テーマ']} / 材料：{r['材料']} / 材料件数：{r['材料件数']} / 企業関与：{r.get('企業関与','要確認')}\n")
            f.write(f"- 判定：{r['重要度']} / 株価：{r['株価']}{r['通貨']} / 時価総額：{r['時価総額']}\n")
            f.write(f"- PER：{r['PER']} / PBR：{r['PBR']} / PSR：{r['PSR']} / EPS：{r['EPS']}\n")
            f.write(f"- 売上成長率：{r['売上成長率']} / 営業利益成長率：{r['営業利益成長率']} / EPS成長率：{r['EPS成長率']}\n")
            f.write(f"- 営業CF：{r['営業CF']} / ROE：{r['ROE']} / ROIC：{r['ROIC']} / 利益品質：{r['利益品質']}\n")
            f.write(f"- バリュートラップ：{r['バリュートラップ']} / 配当性向引き上げ余地：{r['配当性向引き上げ余地']}\n")
            f.write(f"- 株主還元姿勢：{r['株主還元姿勢']}\n")
            f.write(f"- 価格帯：{r['価格帯']} / しこり判定：{r['しこり判定']}\n")
            f.write(f"- 理由：{r['理由']}\n- リスク：{r['リスク']}\n")
            f.write(f"- 原文：{r['原文タイトル']}\n- URL：{r['URL']}\n\n")
    return path


def main():
    articles = collect_news()
    cache = {}
    rows = build_company_rows(articles)
    rows.extend(build_unidentified_rows(articles))
    rows.sort(key=lambda r: safe_num(r.get('総合スコア')) or -1, reverse=True)
    print(f'記事数: {len(articles)} / 企業候補: {len(rows)}')
    print('CSV:', save_csv(rows))
    print('TOP:', save_top(rows))


if __name__ == '__main__':
    main()
