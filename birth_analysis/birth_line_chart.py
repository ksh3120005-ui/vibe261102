"""
대한민국 출생아수 1970~2025 라인 그래프

실행:
    python birth_line_chart.py [엑셀 경로]
birth_analysis.py 의 클렌징 함수를 재사용하며, 그래프는 output/birth_line_chart.png 로 저장됩니다.
GUI 앱(birth_app.py)에서는 draw() 로 원하는 지표·기간을 Figure 에 그립니다.
"""
import contextlib
import io
import sys
from pathlib import Path

import matplotlib
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter, MaxNLocator

from birth_analysis import DEFAULT_XLSX, OUT_DIR, load_and_clean

matplotlib.rcParams["font.family"] = "Malgun Gothic"   # 한글 폰트 (Windows)
matplotlib.rcParams["axes.unicode_minus"] = False      # 마이너스 기호 깨짐 방지

LINE = "#2a78d6"        # 시리즈 색
INK = "#0b0b0b"         # 주 텍스트
INK_2 = "#52514e"       # 보조 텍스트(축·주석)
GRID = "#e4e3df"        # 그리드
SURFACE = "#fcfcfb"     # 배경

# 지표 → (단위, 값 표시 형식)
INDICATORS = {
    "출생아수": ("명", "{:,.0f}명"),
    "자연증가건수": ("명", "{:,.0f}명"),
    "합계출산율": ("명(여성 1명당)", "{:.3f}명"),
    "조출생률": ("인구 천 명당", "{:.1f}"),
    "자연증가율": ("인구 천 명당", "{:.1f}"),
    "출생성비": ("여아 100명당 남아", "{:.1f}"),
}


def draw(fig, df, col="출생아수", start=1970, end=2025):
    """fig 에 지표 col 의 start~end 연도 라인 그래프를 그림"""
    unit, fmt = INDICATORS[col]
    df = df[(df["연도"] >= start) & (df["연도"] <= end)].reset_index(drop=True)
    fig.clear()
    fig.set_facecolor(SURFACE)
    ax = fig.add_subplot()
    ax.set_facecolor(SURFACE)

    final = df[~df["잠정치"]]                      # 확정치
    ax.plot(final["연도"], final[col], color=LINE, linewidth=2, marker="o", markersize=3.5)
    if df["잠정치"].any() and not final.empty:     # 마지막 확정치 ~ 잠정치 구간은 점선
        prelim = df[df["연도"] >= final["연도"].max()]
        ax.plot(prelim["연도"], prelim[col], color=LINE, linewidth=2, linestyle="--")

    # 주요 지점만 직접 라벨링 (최고점, 최저점, 마지막 연도)
    span = max(end - start, 1)
    points = {len(df) - 1: "", df[col].idxmax(): "최고", df[col].idxmin(): "최저"}   # 겹치면 최고/최저 우선
    for i, tag in points.items():
        row = df.loc[i]
        year = f"{row['연도']}년" + ("(잠정)" if row["잠정치"] else "")
        text = f"{year} {tag}\n{fmt.format(row[col])}".replace(" \n", "\n")
        pos = (row["연도"] - start) / span
        ha = "left" if pos < 0.08 else "right" if pos > 0.92 else "center"
        dx = {"left": 8, "right": -8, "center": 0}[ha]
        dy = -34 if tag == "최저" else 12
        ax.scatter(row["연도"], row[col], s=50, color=LINE, zorder=3)
        ax.annotate(text, (row["연도"], row[col]), xytext=(dx, dy), textcoords="offset points",
                    ha=ha, fontsize=9.5, color=INK)

    if df[col].min() < 0:   # 자연증가 등 음수가 있는 지표는 0 기준선 표시
        ax.axhline(0, color=INK_2, linewidth=1)

    ax.set_title(f"대한민국 연도별 {col} ({start}~{end})", loc="left", fontsize=15, color=INK, pad=28)
    note = "  ·  잠정치는 점선" if df["잠정치"].any() else ""
    ax.text(0, 1.02, f"단위: {unit}{note}  ·  출처: 국가데이터처 「인구동향조사」",
            transform=ax.transAxes, fontsize=9, color=INK_2)

    ax.set_xlim(start - 1, end + 1.5)
    if col == "출생아수":
        ax.set_ylim(0, df[col].max() * 1.12)
    else:
        ax.margins(y=0.25)   # 최고/최저 라벨이 축과 겹치지 않도록 여백
    ax.xaxis.set_major_locator(MaxNLocator(nbins=12, integer=True))
    if unit == "명":
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v / 10_000:,.0f}만" if v else "0"))
    ax.tick_params(colors=INK_2, length=0, labelsize=9.5)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(INK_2)
    fig.tight_layout()


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_XLSX
    with contextlib.redirect_stdout(io.StringIO()):   # 클렌징 로그는 숨김
        df = load_and_clean(path)

    fig = Figure(figsize=(12, 6))
    draw(fig, df)
    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / "birth_line_chart.png"
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    print(f"저장 완료: {out}")


if __name__ == "__main__":
    main()
