import feedparser
import re
import csv
import os
from datetime import datetime, timezone

# ============================================================
# Future Stock Radar v2
# 「テーマ」→「企業」→「材料の強さ」を自動判定
# ============================================================

RSS_FEEDS = {
    "AIデータセンター": [
        "https://news.google.com/rss/search?q=AI+data+center",
        "https://news.google.com/rss/search?q=data+center+power",
        "https://news.google.com/rss/search?q=data+center+cooling",
    ],

    "光通信": [
        "https://news.google.com/rss/search?q=co-packaged+optics",
        "https://news.google.com/rss/search?q=silicon+photonics",
        "https://news.google.com/rss/search?q=optical+I/O",
        "https://news.google.com/rss/search?q=optical+interconnect",
    ],

    "冷却・熱管理": [
        "https://news.google.com/rss/search?q=liquid+cooling+data+center",
        "https://news.google.com/rss/search?q=immersion+cooling",
        "https://news.google.com/rss/search?q=thermal+management+data+center",
        "https://news.google.com/rss/search?q=heat+exchanger+data+center",
    ],

    "電力・蓄電": [
        "https://news.google.com/rss/search?q=data+center+electricity",
        "https://news.google.com/rss/search?q=data+center+power+grid",
        "https://news.google.com/rss/search?q=energy+storage+data+center",
        "https://news.google.com/rss/search?q=fuel+cell+data+center",
    ],

    "半導体": [
        "https://news.google.com/rss/search?q=advanced+packaging+semiconductor",
        "https://news.google.com/rss/search?q=chiplet",
        "https://news.google.com/rss/search?q=HBM",
        "https://news.google.com/rss/search?q=compound+semiconductor",
        "https://news.google.com/rss/search?q=GaN+semiconductor",
        "https://news.google.com/rss/search?q=SiC+semiconductor",
    ],

    "宇宙": [
        "https://news.google.com/rss/search?q=space+data+center",
        "https://news.google.com/rss/search?q=orbital+data+center",
        "https://news.google.com/rss/search?q=satellite+computing",
        "https://news.google.com/rss/search?q=space+optical+communication",
        "https://news.google.com/rss/search?q=inter-satellite+laser",
    ],

    "宇宙熱管理": [
        "https://news.google.com/rss/search?q=space+radiator",
        "https://news.google.com/rss/search?q=spacecraft+thermal+management",
        "https://news.google.com/rss/search?q=heat+rejection+spacecraft",
    ],

    "宇宙太陽光・発電": [
        "https://news.google.com/rss/search?q=space+solar+power",
        "https://news.google.com/rss/search?q=space+solar+panel",
        "https://news.google.com/rss/search?q=space+energy",
    ],
}


# ============================================================
# 材料判定キーワード
# ============================================================

MATERIALS = {
    "大型受注": {
        "keywords": [
            "order", "orders", "purchase order",
            "follow-on order", "contract",
            "受注", "大型受注", "契約"
        ],
        "score": 30
    },

    "量産・生産開始": {
        "keywords": [
            "production", "mass production",
            "volume production", "manufacturing",
            "量産", "生産開始"
        ],
        "score": 25
    },

    "大企業との提携": {
        "keywords": [
            "partnership", "partner", "strategic partnership",
            "collaboration", "alliance",
            "提携", "協業", "共同開発"
        ],
        "score": 25
    },

    "戦略的投資": {
        "keywords": [
            "investment", "strategic investment",
            "invests", "funding",
            "投資", "出資"
        ],
        "score": 22
    },

    "政府支援": {
        "keywords": [
            "government", "subsidy", "grant",
            "funded by", "government funding",
            "政府", "補助金", "助成金"
        ],
        "score": 20
    },

    "特許・技術": {
        "keywords": [
            "patent", "patented", "intellectual property",
            "breakthrough", "new technology",
            "特許", "新技術", "技術革新"
        ],
        "score": 15
    },

    "研究開発": {
        "keywords": [
            "research", "development", "R&D",
            "demonstration", "prototype",
            "研究", "開発", "実証", "試作"
        ],
        "score": 12
    },

    "設備投資": {
        "keywords": [
            "capital expenditure", "capex",
            "factory expansion", "facility expansion",
            "new facility", "設備投資", "工場増設"
        ],
        "score": 18
    },

    "業績上方修正": {
        "keywords": [
            "raises outlook", "raised guidance",
            "upgrade guidance", "higher revenue",
            "record revenue", "record sales",
            "上方修正", "最高益", "増収"
        ],
        "score": 30
    },
}


# ============================================================
# 企業名抽出用のパターン
# ============================================================

# 「会社名 + Corporation / Inc. / Systems」など
COMPANY_PATTERNS = [
    r"\b[A-Z][A-Za-z0-9&.\- ]{1,40}\s+(?:Inc\.|Corp\.|Corporation|Ltd\.|Limited|PLC|Systems|Technologies|Technology|Industries)\b",

    # 「Company」が付くケース
    r"\b[A-Z][A-Za-z0-9&.\- ]{1,40}\s+Company\b",
]


# ============================================================
# テーマ判定
# ============================================================

def detect_theme(text):
    text_lower = text.lower()

    for theme, feeds in RSS_FEEDS.items():

        keywords = {
            "AIデータセンター": [
                "ai data center",
                "data center",
                "hyperscale"
            ],

            "光通信": [
                "co-packaged optics",
                "silicon photonics",
                "optical i/o",
                "optical interconnect"
            ],

            "冷却・熱管理": [
                "liquid cooling",
                "immersion cooling",
                "thermal management",
                "heat exchanger"
            ],

            "電力・蓄電": [
                "data center power",
                "data center electricity",
                "energy storage",
                "fuel cell",
                "grid"
            ],

            "半導体": [
                "advanced packaging",
                "chiplet",
                "hbm",
                "compound semiconductor",
                "gan",
                "sic"
            ],

            "宇宙": [
                "space data center",
                "orbital data center",
                "satellite computing",
                "space optical communication",
                "inter-satellite laser"
            ],

            "宇宙熱管理": [
                "space radiator",
                "spacecraft thermal",
                "heat rejection"
            ],

            "宇宙太陽光・発電": [
                "space solar power",
                "space solar panel",
                "space energy"
            ]
        }

        for keyword in keywords.get(theme, []):
            if keyword in text_lower:
                return theme

    return "その他"


# ============================================================
# 材料判定
# ============================================================

def detect_material(text):

    text_lower = text.lower()

    found = []
    score = 0

    for material, data in MATERIALS.items():

        for keyword in data["keywords"]:

            if keyword.lower() in text_lower:

                found.append(material)
                score += data["score"]
                break

    # 重複による過剰評価を防止
    score = min(score, 100)

    if not found:
        found = ["テーマ関連ニュース"]

    return " / ".join(found), score


# ============================================================
# 企業名抽出
# ============================================================

def extract_companies(text):

    companies = []

    for pattern in COMPANY_PATTERNS:

        matches = re.findall(pattern, text)

        for match in matches:

            company = " ".join(match.split())

            if company not in companies:
                companies.append(company)

    # ノイズになりやすい一般語を除外
    blacklist = [
        "Data Center Company",
        "Technology Company",
        "Research Company",
        "Energy Company",
        "Semiconductor Company",
    ]

    companies = [
        c for c in companies
        if c not in blacklist
    ]

    return companies[:5]


# ============================================================
# 重要度判定
# ============================================================

def importance_level(score):

    if score >= 70:
        return "🔥 最重要"

    if score >= 50:
        return "🟠 重要"

    if score >= 30:
        return "🟡 注目"

    return "⚪ 情報"


# ============================================================
# RSS取得
# ============================================================

def collect_news():

    results = []

    for theme, feeds in RSS_FEEDS.items():

        for url in feeds:

            try:

                feed = feedparser.parse(url)

                for entry in feed.entries[:20]:

                    title = entry.get("title", "")
                    link = entry.get("link", "")
                    published = entry.get("published", "")

                    text = f"{title} {published}"

                    detected_theme = detect_theme(text)

                    material, material_score = detect_material(text)

                    companies = extract_companies(title)

                    # テーマスコア
                    theme_score = 10 if detected_theme != "その他" else 0

                    # 企業が明確なら加点
                    company_score = 15 if companies else 0

                    total_score = min(
                        theme_score +
                        material_score +
                        company_score,
                        100
                    )

                    results.append({
                        "取得日": datetime.now(
                            timezone.utc
                        ).strftime("%Y-%m-%d"),

                        "テーマ": detected_theme,

                        "企業": " / ".join(companies),

                        "材料": material,

                        "重要度": importance_level(
                            total_score
                        ),

                        "スコア": total_score,

                        "タイトル": title,

                        "公開日時": published,

                        "URL": link,
                    })

            except Exception as e:

                print(
                    f"RSS取得エラー: {url} / {e}"
                )

    return results


# ============================================================
# 重複除去
# ============================================================

def remove_duplicates(results):

    seen = set()
    unique = []

    for item in results:

        key = (
            item["タイトル"]
            .strip()
            .lower()
        )

        if key in seen:
            continue

        seen.add(key)
        unique.append(item)

    return unique


# ============================================================
# CSV保存
# ============================================================

def save_csv(results):

    os.makedirs("data", exist_ok=True)

    today = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d")

    filename = (
        f"data/radar_{today}.csv"
    )

    fields = [
        "取得日",
        "テーマ",
        "企業",
        "材料",
        "重要度",
        "スコア",
        "タイトル",
        "公開日時",
        "URL",
    ]

    # スコア順
    results.sort(
        key=lambda x: x["スコア"],
        reverse=True
    )

    with open(
        filename,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fields
        )

        writer.writeheader()

        writer.writerows(results)

    return filename


# ============================================================
# メイン処理
# ============================================================

def main():

    print("=" * 60)
    print("Future Stock Radar v2")
    print("テンバガー早期発見システム")
    print("=" * 60)

    results = collect_news()

    results = remove_duplicates(results)

    filename = save_csv(results)

    print()
    print(
        f"取得ニュース数: {len(results)}"
    )

    print()
    print("🔥 TOP 20")
    print("-" * 60)

    for item in results[:20]:

        print(
            f"[{item['スコア']:3}] "
            f"{item['重要度']} "
            f"{item['テーマ']} | "
            f"{item['企業']} | "
            f"{item['材料']}"
        )

        print(
            f"      {item['タイトル'][:100]}"
        )

    print()
    print(
        f"保存完了: {filename}"
    )


if __name__ == "__main__":
    main()
