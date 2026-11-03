"""
네이버 검색 결과에서 뉴스 기사를 찾아 본문까지 크롤링하는 스크립트 (requests + BeautifulSoup4)

동작 방식
1. 네이버 검색 결과 페이지(URL)를 가져온다.
2. 페이지 안의 '네이버뉴스' 링크(n.news.naver.com/mnews/article/...)를 모두 수집한다.
   - 네이버 검색 페이지의 CSS 클래스명은 난독화되어 자주 바뀌므로, 클래스 대신 링크 주소 패턴으로 찾는다.
3. 각 기사 페이지에 들어가 제목 / 언론사 / 작성일 / 본문을 추출한다.
4. 결과를 화면에 출력하고 CSV 파일로 저장한다.

설치: pip install requests beautifulsoup4
실행: python naver_news_crawler.py
"""

import csv
import re
import time

import requests
from bs4 import BeautifulSoup

SEARCH_URL = (
    "https://search.naver.com/search.naver?where=nexearch&sm=top_hty&fbm=0"
    "&ie=utf8&query=%EB%B0%98%EB%8F%84%EC%B2%B4&ackey=f3pa7w5z"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.naver.com/",
}

# 네이버뉴스 기사 주소 패턴: https://n.news.naver.com/mnews/article/{언론사ID}/{기사ID}
ARTICLE_PATTERN = re.compile(r"https://n\.news\.naver\.com/(?:mnews/)?article/(\d+)/(\d+)")


def get_soup(url):
    """URL의 HTML을 가져와 BeautifulSoup 객체로 반환한다."""
    response = requests.get(url, headers=HEADERS, timeout=10)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def collect_article_links(search_url):
    """검색 결과 페이지에서 네이버뉴스 기사 링크를 중복 없이 수집한다."""
    soup = get_soup(search_url)
    links = []
    seen = set()
    for a in soup.find_all("a", href=True):
        match = ARTICLE_PATTERN.match(a["href"])
        if not match:
            continue
        # 같은 기사가 ?sid= 등 다른 파라미터로 여러 번 나올 수 있으므로 (언론사ID, 기사ID)로 중복 제거
        key = match.groups()
        if key in seen:
            continue
        seen.add(key)
        links.append(a["href"])
    return links


def parse_article(url):
    """네이버뉴스 기사 페이지에서 제목, 언론사, 작성일, 본문을 추출한다."""
    soup = get_soup(url)

    title_tag = soup.select_one("h2#title_area") or soup.select_one(".media_end_head_headline")
    title = title_tag.get_text(strip=True) if title_tag else ""

    press_tag = soup.select_one(".media_end_head_top_logo img")
    press = (press_tag.get("title") or press_tag.get("alt", "")) if press_tag else ""

    date_tag = soup.select_one("span._ARTICLE_DATE_TIME")
    date = date_tag.get("data-date-time", date_tag.get_text(strip=True)) if date_tag else ""

    body_tag = soup.select_one("#dic_area") or soup.select_one("#newsct_article")
    body = ""
    if body_tag:
        # 사진 설명, 스크립트 등 본문이 아닌 요소 제거
        for tag in body_tag.select("script, style, .img_desc, .end_photo_org em, .media_end_summary"):
            tag.decompose()
        body = body_tag.get_text("\n", strip=True)

    return {"title": title, "press": press, "date": date, "url": url, "content": body}


def save_csv(articles, filename):
    # utf-8-sig: 엑셀에서 열어도 한글이 깨지지 않도록 BOM 포함
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["title", "press", "date", "url", "content"])
        writer.writeheader()
        writer.writerows(articles)


def save_excel(articles, filename):
    """기사 목록을 엑셀(.xlsx) 파일로 저장한다. (pip install openpyxl 필요)"""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "뉴스"

    columns = [("제목", "title", 50), ("언론사", "press", 14), ("작성일", "date", 20),
               ("URL", "url", 45), ("본문", "content", 100)]

    ws.append([name for name, _, _ in columns])
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="03C75A")
        cell.alignment = Alignment(horizontal="center")

    for article in articles:
        # 엑셀 셀 하나에는 최대 32,767자까지만 들어가므로 긴 본문은 잘라서 저장
        ws.append([article[key][:32767] for _, key, _ in columns])

    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=cell.column_letter == "E")
        url_cell = row[3]
        url_cell.hyperlink = url_cell.value
        url_cell.font = Font(color="0563C1", underline="single")

    for i, (_, _, width) in enumerate(columns, 1):
        ws.column_dimensions[ws.cell(1, i).column_letter].width = width
    ws.freeze_panes = "A2"  # 머리글 행 고정

    wb.save(filename)


def main():
    links = collect_article_links(SEARCH_URL)
    print(f"네이버뉴스 기사 링크 {len(links)}개 발견\n")

    articles = []
    for i, link in enumerate(links, 1):
        try:
            article = parse_article(link)
        except requests.RequestException as e:
            print(f"[{i}] 요청 실패: {link} ({e})")
            continue
        articles.append(article)

        print(f"[{i}] {article['title']}")
        print(f"    언론사: {article['press']} | 작성일: {article['date']}")
        print(f"    URL: {article['url']}")
        print(f"    본문: {article['content'][:150]}...\n")

        time.sleep(0.5)  # 서버 부담을 줄이기 위한 요청 간격

    save_csv(articles, "naver_news_반도체.csv")
    print(f"총 {len(articles)}개 기사를 naver_news_반도체.csv 에 저장했습니다.")


if __name__ == "__main__":
    main()
