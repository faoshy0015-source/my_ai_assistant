import streamlit as st
import yfinance as yf
import requests
import os
import pandas as pd
import xml.etree.ElementTree as ET

from urllib.parse import quote
from dotenv import load_dotenv


# ==================================================
# 환경설정
# ==================================================

load_dotenv()

st.set_page_config(
    page_title="Lewis AI 투자 비서",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 Lewis AI 투자 비서")
st.caption("미국증시 + 한국증시 + 관심종목 + 시장 브리핑")


# ==================================================
# 비밀키 읽기
# PC에서는 .env
# Streamlit Cloud에서는 Secrets
# ==================================================

def get_secret(name):

    # 1. PC의 .env 또는 환경변수
    value = os.getenv(name)

    if value:
        return value

    # 2. Streamlit Cloud Secrets
    try:
        return st.secrets[name]
    except Exception:
        return None


# ==================================================
# 한국투자증권
# ==================================================

KIS_BASE_URL = "https://openapi.koreainvestment.com:9443"


@st.cache_resource(ttl=21600)
def get_kis_token():

    app_key = get_secret("KIS_APP_KEY")
    app_secret = get_secret("KIS_APP_SECRET")

    if not app_key or not app_secret:
        return None

    url = f"{KIS_BASE_URL}/oauth2/tokenP"

    headers = {
        "content-type": "application/json"
    }

    body = {
        "grant_type": "client_credentials",
        "appkey": app_key,
        "appsecret": app_secret
    }

    try:

        response = requests.post(
            url,
            headers=headers,
            json=body,
            timeout=10
        )

        if response.status_code != 200:
            return None

        result = response.json()

        return result.get("access_token")

    except Exception:

        return None


# ==================================================
# 국내주식 현재가
# ==================================================

@st.cache_data(ttl=60)
def get_kis_stock_price(stock_code):

    app_key = get_secret("KIS_APP_KEY")
    app_secret = get_secret("KIS_APP_SECRET")

    if not app_key or not app_secret:
        return None

    token = get_kis_token()

    if not token:
        return None

    url = (
        f"{KIS_BASE_URL}"
        "/uapi/domestic-stock/v1/quotations/inquire-price"
    )

    headers = {
        "content-type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": "FHKST01010100"
    }

    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": stock_code
    }

    try:

        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=10
        )

        if response.status_code != 200:
            return None

        result = response.json()

        if result.get("rt_cd") != "0":
            return None

        output = result.get("output", {})

        return {
            "price": float(output.get("stck_prpr", 0)),
            "change_rate": float(output.get("prdy_ctrt", 0))
        }

    except Exception:

        return None


# ==================================================
# 미국주식 / 지수
# ==================================================

@st.cache_data(ttl=60)
def get_us_price(symbol):

    try:

        data = yf.download(
            symbol,
            period="5d",
            progress=False,
            auto_adjust=False
        )

        if data.empty:
            return None

        close = data["Close"]

        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]

        price = float(close.iloc[-1])

        if len(close) >= 2:

            previous = float(close.iloc[-2])

            change_rate = (
                (price - previous) / previous
            ) * 100

        else:

            change_rate = 0

        return {
            "price": price,
            "change_rate": change_rate
        }

    except Exception:

        return None


# ==================================================
# 차트 데이터
# ==================================================

@st.cache_data(ttl=300)
def get_chart_data(symbol, market):

    try:

        if market == "🇺🇸 미국":

            ticker = symbol

        else:

            ticker = f"{symbol}.KS"

        data = yf.download(
            ticker,
            period="6mo",
            interval="1d",
            progress=False,
            auto_adjust=False
        )

        if data.empty:
            return None

        close = data["Close"]

        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]

        chart = pd.DataFrame({
            "종가": close
        })

        chart.index = pd.to_datetime(chart.index)

        return chart

    except Exception:

        return None


# ==================================================
# 뉴스 가져오기
# ==================================================

@st.cache_data(ttl=600)
def get_news(query, limit=10):

    try:

        encoded_query = quote(query)

        url = (
            "https://news.google.com/rss/search?"
            f"q={encoded_query}"
            "&hl=ko"
            "&gl=KR"
            "&ceid=KR:ko"
        )

        response = requests.get(
            url,
            timeout=10,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        if response.status_code != 200:
            return []

        root = ET.fromstring(response.content)

        news = []

        for item in root.findall(".//item")[:limit]:

            title = item.findtext("title") or ""
            link = item.findtext("link") or ""
            description = item.findtext("description") or ""
            pub_date = item.findtext("pubDate") or ""

            if title and link:

                news.append({
                    "title": title,
                    "link": link,
                    "description": description,
                    "date": pub_date
                })

        return news

    except Exception:

        return []


# ==================================================
# 뉴스 영향도 분석
# ==================================================

def analyze_news(title, description=""):

    text = (
        str(title) + " " +
        str(description)
    ).lower()

    score = 0

    high_keywords = [
        "금리",
        "연준",
        "fed",
        "fomc",
        "인플레이션",
        "cpi",
        "고용",
        "미중",
        "중국",
        "관세",
        "반도체",
        "ai",
        "인공지능",
        "유가",
        "원유",
        "중동",
        "전쟁"
    ]

    medium_keywords = [
        "엔비디아",
        "애플",
        "마이크로소프트",
        "메타",
        "구글",
        "테슬라",
        "나스닥",
        "s&p",
        "코스피",
        "삼성전자",
        "sk하이닉스",
        "배터리",
        "전기차"
    ]

    for keyword in high_keywords:

        if keyword in text:
            score += 3

    for keyword in medium_keywords:

        if keyword in text:
            score += 1

    related = []

    if any(
        keyword in text
        for keyword in [
            "반도체",
            "ai",
            "인공지능",
            "엔비디아",
            "hbm",
            "메모리"
        ]
    ):

        related += [
            "삼성전자",
            "SK하이닉스"
        ]

    if any(
        keyword in text
        for keyword in [
            "전력",
            "전력기기",
            "데이터센터"
        ]
    ):

        related += [
            "효성중공업",
            "HD현대일렉트릭"
        ]

    if any(
        keyword in text
        for keyword in [
            "배터리",
            "전기차",
            "테슬라",
            "ev"
        ]
    ):

        related += [
            "LG에너지솔루션",
            "삼성SDI"
        ]

    if any(
        keyword in text
        for keyword in [
            "금리",
            "연준",
            "은행"
        ]
    ):

        related += [
            "KB금융",
            "하나금융지주"
        ]

    if any(
        keyword in text
        for keyword in [
            "방산",
            "중동",
            "전쟁",
            "국방"
        ]
    ):

        related += [
            "LIG넥스원"
        ]

    if any(
        keyword in text
        for keyword in [
            "자동차",
            "현대차",
            "전기차"
        ]
    ):

        related += [
            "현대차"
        ]

    if any(
        keyword in text
        for keyword in [
            "네이버",
            "플랫폼"
        ]
    ):

        related += [
            "NAVER"
        ]

    related = list(dict.fromkeys(related))

    if score >= 8:

        level = "🔴 매우 높음"

    elif score >= 5:

        level = "🟠 높음"

    elif score >= 3:

        level = "🟡 보통"

    else:

        level = "🟢 낮음"

    clean_description = (
        description
        .replace("<p>", "")
        .replace("</p>", "")
        .replace("<br>", " ")
        .replace("&nbsp;", " ")
    )

    if len(clean_description) > 350:

        clean_description = (
            clean_description[:350] + "..."
        )

    if not clean_description.strip():

        clean_description = (
            "기사 제목을 중심으로 시장 관련성을 분석했습니다."
        )

    if any(
        keyword in text
        for keyword in [
            "반도체",
            "ai",
            "인공지능",
            "엔비디아",
            "hbm",
            "메모리"
        ]
    ):

        impact = (
            "미국 AI·반도체 투자심리와 연결될 가능성이 있어 "
            "국내 반도체 및 AI 인프라 관련주의 투자심리에 "
            "영향을 줄 수 있습니다."
        )

    elif any(
        keyword in text
        for keyword in [
            "금리",
            "연준",
            "fed",
            "fomc",
            "cpi",
            "인플레이션"
        ]
    ):

        impact = (
            "미국 금리 기대 변화가 달러와 글로벌 자금 흐름에 "
            "영향을 줄 수 있어 국내 성장주와 금융주에 "
            "영향을 줄 수 있습니다."
        )

    elif any(
        keyword in text
        for keyword in [
            "유가",
            "원유",
            "중동",
            "전쟁"
        ]
    ):

        impact = (
            "국제유가와 인플레이션 기대에 영향을 줄 수 있어 "
            "한국의 에너지 비용과 업종별 투자심리에 "
            "영향을 줄 가능성이 있습니다."
        )

    elif any(
        keyword in text
        for keyword in [
            "미중",
            "중국",
            "관세"
        ]
    ):

        impact = (
            "미·중 무역 및 공급망 변화와 연결될 수 있어 "
            "반도체·자동차·배터리 등 수출주의 투자심리에 "
            "영향을 줄 가능성이 있습니다."
        )

    else:

        impact = (
            "글로벌 투자심리와 국내 증시에 영향을 줄 수 있는 "
            "시장 관련 뉴스입니다."
        )

    return {
        "score": score,
        "level": level,
        "summary": clean_description,
        "impact": impact,
        "related": related
    }


# ==================================================
# 시장 브리핑
# ==================================================

def create_market_briefing():

    sp500 = get_us_price("^GSPC")
    nasdaq = get_us_price("^IXIC")
    dow = get_us_price("^DJI")

    lines = []

    lines.append("### 🇺🇸 미국 증시")

    if sp500:

        lines.append(
            f"- S&P 500: "
            f"{sp500['price']:,.2f} "
            f"({sp500['change_rate']:+.2f}%)"
        )

    if nasdaq:

        lines.append(
            f"- NASDAQ: "
            f"{nasdaq['price']:,.2f} "
            f"({nasdaq['change_rate']:+.2f}%)"
        )

    if dow:

        lines.append(
            f"- Dow Jones: "
            f"{dow['price']:,.2f} "
            f"({dow['change_rate']:+.2f}%)"
        )

    lines.append("")
    lines.append("### 📌 시장 흐름")

    if sp500 and nasdaq:

        if (
            sp500["change_rate"] > 0
            and nasdaq["change_rate"] > 0
        ):

            lines.append(
                "미국 주요 지수가 모두 상승한 상태입니다. "
                "기술주와 성장주 흐름을 함께 확인할 필요가 있습니다."
            )

        elif (
            sp500["change_rate"] < 0
            and nasdaq["change_rate"] < 0
        ):

            lines.append(
                "미국 주요 지수가 모두 하락한 상태입니다. "
                "금리·유가·위험회피 흐름을 확인할 필요가 있습니다."
            )

        else:

            lines.append(
                "미국 주요 지수의 방향이 엇갈리고 있습니다."
            )

    lines.append("")
    lines.append("### 🇰🇷 한국증시 연결 포인트")

    lines.append(
        "미국 기술주와 반도체주의 움직임은 "
        "삼성전자·SK하이닉스 등 국내 반도체주에 "
        "영향을 줄 수 있습니다."
    )

    lines.append(
        "미국 금리와 달러, 유가 움직임은 "
        "국내 성장주·금융주·산업재의 투자심리에 "
        "영향을 줄 수 있습니다."
    )

    return "\n".join(lines)


# ==================================================
# 미국 시장
# ==================================================

st.subheader("🇺🇸 미국 시장")

us_market = [
    ("S&P 500", "^GSPC"),
    ("NASDAQ", "^IXIC"),
    ("Dow Jones", "^DJI")
]

cols = st.columns(3)

for col, (name, symbol) in zip(cols, us_market):

    data = get_us_price(symbol)

    with col:

        if data:

            st.metric(
                name,
                f"{data['price']:,.2f}",
                f"{data['change_rate']:+.2f}%"
            )

        else:

            st.metric(
                name,
                "조회 실패"
            )


# ==================================================
# 관심종목
# ==================================================

kr_stocks = [
    ("삼성전자", "005930"),
    ("SK하이닉스", "000660"),
    ("SK스퀘어", "402340"),
    ("NAVER", "035420"),
    ("현대차", "005380"),
    ("LG에너지솔루션", "373220"),
    ("삼성SDI", "006400"),
    ("효성중공업", "298340"),
    ("HD현대일렉트릭", "267260"),
    ("KB금융", "105560"),
    ("하나금융지주", "086790"),
    ("LIG넥스원", "079550")
]

us_stocks = [
    ("엔비디아", "NVDA"),
    ("테슬라", "TSLA"),
    ("마이크로소프트", "MSFT"),
    ("AMD", "AMD"),
    ("애플", "AAPL"),
    ("메타", "META"),
    ("알파벳A", "GOOGL"),
    ("슈퍼마이크로컴퓨터", "SMCI")
]


watchlist = []


for name, code in kr_stocks:

    data = get_kis_stock_price(code)

    if data:

        watchlist.append({
            "시장": "🇰🇷 한국",
            "종목": name,
            "티커": code,
            "현재가": data["price"],
            "등락률": data["change_rate"]
        })


for name, symbol in us_stocks:

    data = get_us_price(symbol)

    if data:

        watchlist.append({
            "시장": "🇺🇸 미국",
            "종목": name,
            "티커": symbol,
            "현재가": data["price"],
            "등락률": data["change_rate"]
        })


df = pd.DataFrame(watchlist)


# ==================================================
# 관심종목 + 차트
# ==================================================

st.subheader("📋 관심종목")

if not df.empty:

    left_col, right_col = st.columns([1, 3])

    with left_col:

        st.markdown("### 종목 선택")

        options = []
        option_map = {}

        for _, row in df.iterrows():

            label = (
                f"{row['종목']} "
                f"{row['등락률']:+.2f}%"
            )

            options.append(label)
            option_map[label] = row

        selected_label = st.radio(
            "종목",
            options,
            label_visibility="collapsed"
        )

        selected = option_map[selected_label]

    with right_col:

        st.markdown(
            f"## 📈 {selected['종목']}"
        )

        col1, col2 = st.columns(2)

        with col1:

            if selected["시장"] == "🇰🇷 한국":

                price_text = (
                    f"{selected['현재가']:,.0f}원"
                )

            else:

                price_text = (
                    f"${selected['현재가']:,.2f}"
                )

            st.metric(
                "현재가",
                price_text
            )

        with col2:

            st.metric(
                "등락률",
                f"{selected['등락률']:+.2f}%"
            )

        chart = get_chart_data(
            selected["티커"],
            selected["시장"]
        )

        if chart is not None:

            st.line_chart(
                chart,
                use_container_width=True,
                height=450
            )

        else:

            st.warning(
                "차트 데이터를 가져오지 못했습니다."
            )


# ==================================================
# 상승 / 하락 종목
# ==================================================

if not df.empty:

    st.subheader("📈 상승 종목")

    up_df = df[
        df["등락률"] > 0
    ].copy()

    if up_df.empty:

        st.info(
            "현재 상승 종목이 없습니다."
        )

    else:

        st.dataframe(
            up_df[
                ["시장", "종목", "현재가", "등락률"]
            ],
            use_container_width=True,
            hide_index=True
        )

    st.subheader("📉 하락 종목")

    down_df = df[
        df["등락률"] < 0
    ].copy()

    if down_df.empty:

        st.info(
            "현재 하락 종목이 없습니다."
        )

    else:

        st.dataframe(
            down_df[
                ["시장", "종목", "현재가", "등락률"]
            ],
            use_container_width=True,
            hide_index=True
        )


# ==================================================
# 주요 기능
# ==================================================

st.subheader("📌 주요 기능")

col1, col2, col3, col4 = st.columns(4)


with col1:

    market_button = st.button(
        "📊 시장 브리핑",
        use_container_width=True
    )


with col2:

    news_button = st.button(
        "📰 뉴스 요약",
        use_container_width=True
    )


with col3:

    st.button(
        "⭐ 관심종목",
        use_container_width=True
    )


with col4:

    st.button(
        "🤖 AI 분석",
        use_container_width=True
    )


# ==================================================
# 시장 브리핑
# ==================================================

if market_button:

    st.divider()

    st.subheader(
        "📊 오늘의 시장 브리핑"
    )

    st.markdown(
        create_market_briefing()
    )


# ==================================================
# 뉴스 요약
# ==================================================

if news_button:

    st.divider()

    st.subheader(
        "📰 한국증시 영향 뉴스"
    )

    st.caption(
        "뉴스의 시장 관련 키워드를 분석하여 "
        "한국증시 영향도가 높은 순서로 정렬합니다."
    )

    us_news = get_news(
        "미국 증시 반도체 AI 금리 유가 미중",
        10
    )

    kr_news = get_news(
        "한국 증시 삼성전자 SK하이닉스 코스피",
        10
    )

    all_news = (
        us_news +
        kr_news
    )

    unique_news = {}

    for news in all_news:

        title = news["title"]

        if title not in unique_news:

            unique_news[title] = news

    all_news = list(
        unique_news.values()
    )

    analyzed_news = []

    for news in all_news:

        analysis = analyze_news(
            news["title"],
            news["description"]
        )

        news_item = {
            **news,
            **analysis
        }

        analyzed_news.append(
            news_item
        )

    analyzed_news.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    if analyzed_news:

        for index, news in enumerate(
            analyzed_news[:10],
            start=1
        ):

            st.markdown(
                f"## {index}. "
                f"{news['level']}"
            )

            st.markdown(
                f"### {news['title']}"
            )

            st.markdown(
                "**🔎 핵심 내용**"
            )

            st.write(
                news["summary"]
            )

            st.markdown(
                "**🇰🇷 한국증시 영향**"
            )

            st.write(
                news["impact"]
            )

            st.markdown(
                "**🎯 관련 종목**"
            )

            if news["related"]:

                stock_text = " · ".join(
                    news["related"]
                )

                st.info(
                    stock_text
                )

            else:

                st.info(
                    "직접적인 관련 종목을 특정하기 어렵습니다."
                )

            st.markdown(
                f"[📰 원문 기사 보기]({news['link']})"
            )

            st.divider()

    else:

        st.warning(
            "뉴스를 가져오지 못했습니다. "
            "잠시 후 다시 눌러주세요."
        )


# ==================================================
# AI 분석
# ==================================================

st.subheader("🤖 AI 시장 분석")

st.info(
    "현재는 OpenAI API 크레딧 없이 사용할 수 있는 "
    "시장 데이터와 뉴스 분석 기능을 구축하고 있습니다."
)


# ==================================================
# 하단
# ==================================================

st.caption(
    "※ 국내주식: 한국투자증권 Open API / "
    "미국주식: Yahoo Finance / "
    "뉴스: Google News RSS"
)
