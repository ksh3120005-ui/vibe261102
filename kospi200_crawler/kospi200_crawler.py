"""
네이버페이 증권 코스피200 크롤러

https://stock.naver.com/market/stock/kr 페이지는 Next.js(JavaScript)로 그려지는 화면이라,
requests로 받은 HTML에는 코스피200 수치가 들어 있지 않습니다. (BeautifulSoup으로 파싱해도 빈 화면)
그래서 이 페이지가 내부적으로 호출하는 JSON API를 직접 요청해서 데이터를 가져옵니다.

수집 항목
  1) 코스피200 지수 현재가 / 전일비 / 등락률
  2) 코스피200 일별 시세 (시가 / 고가 / 저가 / 종가)
  3) 거래대금 상위 종목 200개 (https://stock.naver.com/market/stock/kr/stocklist/priceTop)
     현재가, 등락률, 거래량, 거래대금, 시가총액 / 100개씩 페이지를 넘기며 수집

사용법
  pip install requests beautifulsoup4
  python kospi200_crawler.py                   # 일별 시세 20일치 + 거래대금 상위 200개(전체 시장)
  python kospi200_crawler.py --days 60         # 일별 시세 60일치
  python kospi200_crawler.py --market KOSPI    # 거래대금 상위를 코스피 종목만
  python kospi200_crawler.py --excel           # 엑셀(.xlsx)로도 저장 (pip install openpyxl)
"""

import argparse
import csv
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

PAGE_URL = "https://stock.naver.com/market/stock/kr"
API_BASE = "https://m.stock.naver.com/api/index/KPI200"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    ),
    "Referer": PAGE_URL,
}
OUTPUT_DIR = Path(__file__).parent


def check_page_html() -> None:
    """원래 페이지를 BeautifulSoup으로 열어보고, 지수 값이 HTML에 없다는 것을 확인합니다."""
    res = requests.get(PAGE_URL, headers=HEADERS, timeout=10)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else "(제목 없음)"
    has_data = "코스피200" in soup.get_text() or "코스피 200" in soup.get_text()
    print(f"[페이지] {title} - HTML 안에 코스피200 데이터 {'있음' if has_data else '없음 (JS 렌더링)'}")


def get_json(path: str, params: dict | None = None):
    res = requests.get(f"{API_BASE}/{path}", headers=HEADERS, params=params, timeout=10)
    res.raise_for_status()
    return res.json()


def fetch_index_summary() -> dict:
    """코스피200 지수 현재가."""
    data = get_json("basic")
    return {
        "지수명": data["stockName"],
        "현재가": data["closePrice"],
        "전일비": data["compareToPreviousClosePrice"],
        "등락률(%)": data["fluctuationsRatio"],
        "상태": data["compareToPreviousPrice"]["text"],
        "장상태": data["marketStatus"],
        "기준시각": data["localTradedAt"],
    }


def fetch_daily_prices(days: int) -> list[dict]:
    """코스피200 일별 시세 (최근 days일)."""
    rows, page = [], 1
    while len(rows) < days:
        items = get_json("price", {"page": page, "pageSize": min(days, 60)})
        if not items:
            break
        for it in items:
            rows.append({
                "날짜": it["localTradedAt"],
                "종가": it["closePrice"],
                "전일비": it["compareToPreviousClosePrice"],
                "등락률(%)": it["fluctuationsRatio"],
                "시가": it["openPrice"],
                "고가": it["highPrice"],
                "저가": it["lowPrice"],
            })
        page += 1
        time.sleep(0.3)
    return rows[:days]


PRICE_TOP_URL = "https://stock.naver.com/market/stock/kr/stocklist/priceTop"
PRICE_TOP_API = "https://m.stock.naver.com/api/stocks/priceTop"
PAGE_SIZE = 100  # priceTop API가 한 번에 돌려주는 최대 개수
MARKETS = {"all": "전체", "KOSPI": "코스피", "KOSDAQ": "코스닥"}


def fetch_price_top(market: str = "all", limit: int = 200, log=print) -> list[dict]:
    """거래대금 상위 페이지(priceTop)의 종목을 페이지 단위로 돌며 limit개 수집.

    log: 페이지별 진행 메시지를 받을 함수 (GUI에서는 상태 표시줄로 전달)
    """
    rows, seen, page = [], set(), 1
    while len(rows) < limit:
        res = requests.get(
            f"{PRICE_TOP_API}/{market}",
            headers={**HEADERS, "Referer": PRICE_TOP_URL},
            params={"page": page, "pageSize": PAGE_SIZE},
            timeout=10,
        )
        res.raise_for_status()
        data = res.json()
        items = data["stocks"]
        log(f"  page {page}: {len(items)}건 (전체 {data['totalCount']}종목)")
        for it in items:
            if it["itemCode"] in seen:  # 장중에는 페이지 사이에 순위가 바뀌어 중복될 수 있음
                continue
            seen.add(it["itemCode"])
            rows.append({
                "순위": len(rows) + 1,
                "시장": "코스피" if it["sosok"] == "0" else "코스닥",
                "종목코드": it["itemCode"],
                "종목명": it["stockName"],
                "현재가": it["closePrice"],
                "전일비": it["compareToPreviousClosePrice"],
                "등락률(%)": it["fluctuationsRatio"],
                "거래량": it["accumulatedTradingVolume"],
                "거래대금(백만)": it["accumulatedTradingValue"],
                "시가총액(억)": it["marketValue"],
            })
        if len(items) < PAGE_SIZE or page * PAGE_SIZE >= data["totalCount"]:  # 마지막 페이지
            break
        page += 1
        time.sleep(0.3)
    return rows[:limit]


def save_csv(rows: list[dict], filename: str) -> Path:
    path = OUTPUT_DIR / filename
    with open(path, "w", newline="", encoding="utf-8-sig") as f:  # 엑셀에서 한글 깨짐 방지
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return path


def save_excel(sheets: dict[str, list[dict]], filename: str) -> Path:
    """{시트이름: 행 목록}을 한 엑셀(.xlsx) 파일에 시트별로 저장한다. (pip install openpyxl 필요)

    숫자 열은 '1,392,500' 같은 문자열이 아닌 실제 숫자로 넣어 엑셀에서 정렬·계산이 되도록 한다.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    text_keys = {"시장", "종목코드", "종목명", "날짜"}
    wb = Workbook()
    wb.remove(wb.active)
    for title, rows in sheets.items():
        if not rows:
            continue
        ws = wb.create_sheet(title)
        keys = list(rows[0].keys())
        ws.append(keys)
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="03C75A")
            cell.alignment = Alignment(horizontal="center")

        for row in rows:
            ws.append([row[k] if k in text_keys else float(str(row[k]).replace(",", "") or 0)
                       for k in keys])

        for r, row in enumerate(rows, 2):
            change = float(str(row.get("전일비", "0")).replace(",", "") or 0)
            color = "E03131" if change > 0 else "1C7ED6" if change < 0 else None
            for c, key in enumerate(keys, 1):
                cell = ws.cell(r, c)
                if key not in text_keys and "날짜" in keys:
                    cell.number_format = "#,##0.00"  # 지수 시세는 소수점 둘째 자리
                elif key == "등락률(%)":
                    cell.number_format = "0.00"
                elif key not in text_keys:
                    cell.number_format = "#,##0"
                if key in ("전일비", "등락률(%)") and color:
                    cell.font = Font(color=color)
                if key == "종목명" and row.get("종목코드"):
                    cell.hyperlink = f"https://stock.naver.com/domestic/stock/{row['종목코드']}"
                    cell.font = Font(bold=True, color="0563C1", underline="single")

        for c, key in enumerate(keys, 1):
            width = max(len(key), *(len(str(row[key])) for row in rows)) * 1.3 + 2
            ws.column_dimensions[get_column_letter(c)].width = min(width, 40)
        ws.freeze_panes = "A2"  # 머리글 행 고정
        ws.auto_filter.ref = ws.dimensions  # 머리글에 필터 버튼

    path = OUTPUT_DIR / filename
    wb.save(path)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="네이버 코스피200 크롤러")
    parser.add_argument("--days", type=int, default=20, help="일별 시세 수집 일수 (기본 20)")
    parser.add_argument("--limit", type=int, default=200, help="저장할 거래대금 상위 종목 수 (기본 200)")
    parser.add_argument("--market", choices=MARKETS, default="all",
                        help="거래대금 상위 시장: all(전체) / KOSPI / KOSDAQ (기본 all)")
    parser.add_argument("--excel", action="store_true", help="두 결과를 엑셀 파일 하나에 시트별로도 저장")
    args = parser.parse_args()

    check_page_html()

    summary = fetch_index_summary()
    print(f"\n[{summary['지수명']}] {summary['현재가']} "
          f"({summary['전일비']}, {summary['등락률(%)']}%) {summary['상태']} / "
          f"{summary['장상태']} / {summary['기준시각']}")

    stamp = datetime.now().strftime("%Y%m%d")

    daily = fetch_daily_prices(args.days)
    print(f"\n일별 시세 {len(daily)}건")
    for r in daily[:5]:
        print(f"  {r['날짜']}  종가 {r['종가']:>8}  {r['등락률(%)']:>6}%")
    print(f"  -> {save_csv(daily, f'kospi200_daily_{stamp}.csv').name}")

    print(f"\n거래대금 상위 수집 ({MARKETS[args.market]})")
    stocks = fetch_price_top(args.market, args.limit)
    print(f"거래대금 상위 {len(stocks)}개 (상위 5)")
    for r in stocks[:5]:
        print(f"  {r['순위']:>3}. [{r['시장']}] {r['종목명']:<12} {r['현재가']:>10}원  "
              f"거래대금 {r['거래대금(백만)']:>10}백만")
    print(f"  -> {save_csv(stocks, f'price_top_{args.market}_{stamp}.csv').name}")

    if args.excel:
        path = save_excel({"거래대금 상위": stocks, "코스피200 일별 시세": daily},
                          f"kospi200_{args.market}_{stamp}.xlsx")
        print(f"\n엑셀 -> {path.name}")


if __name__ == "__main__":
    main()
