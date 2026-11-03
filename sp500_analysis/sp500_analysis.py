"""
S&P 500 과거 데이터 클렌징 + 다각도 분석 + 차트 (분석 로직 모듈)

GUI 앱(sp500_app.py)에서 import 해서 사용하며, 단독 실행도 가능합니다.
    python sp500_analysis.py [CSV 경로]
단독 실행 시 결과 이미지·정제 CSV·엑셀 파일은 이 스크립트와 같은 폴더의 output/ 에 저장됩니다.
"""
import io
import sys
from pathlib import Path

import matplotlib
import matplotlib.dates as mdates
import matplotlib.style
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

# PyInstaller exe 에서는 __file__ 이 임시 폴더를 가리키므로 exe 가 있는 폴더를 기준으로 함
APP_DIR = (Path(sys.executable) if getattr(sys, "frozen", False) else Path(__file__)).resolve().parent
OUT_DIR = APP_DIR / "output"
CSV_NAME = "S&P 500 과거 데이터.csv"


def find_default_csv():
    """exe(스크립트)와 같은 폴더 → 수업 DataSet 폴더 순으로 CSV 를 찾음"""
    for p in (APP_DIR / CSV_NAME, Path(r"C:\Users\user\Desktop\생산성본부_바이브코딩수업\DataSet") / CSV_NAME):
        if p.exists():
            return str(p)
    return ""


DEFAULT_CSV = find_default_csv()

matplotlib.rcParams["font.family"] = "Malgun Gothic"     # 한글 폰트 (Windows)
matplotlib.rcParams["axes.unicode_minus"] = False        # 마이너스 기호 깨짐 방지
pd.set_option("display.width", 120)
pd.set_option("display.float_format", "{:,.2f}".format)


def section(title):
    print(f"\n{'=' * 70}\n {title}\n{'=' * 70}")


# ---------------------------------------------------------------------------
# 1. 데이터 로드 & 클렌징
# ---------------------------------------------------------------------------
def load_and_clean(path):
    section("1. 데이터 클렌징")
    raw = pd.read_csv(path, encoding="utf-8-sig", dtype=str)   # BOM 제거, 일단 문자열로
    print(f"원본 shape: {raw.shape}")
    print(f"원본 컬럼: {list(raw.columns)}")
    print("\n[결측치 개수 - 원본]")
    print(raw.isna().sum())

    df = raw.rename(columns={
        "날짜": "Date", "종가": "Close", "시가": "Open", "고가": "High",
        "저가": "Low", "거래량": "Volume", "변동 %": "Change_pct",
    })

    # (1) 날짜: "2019- 11- 14" 처럼 공백이 섞여 있으므로 공백 제거 후 datetime 변환
    df["Date"] = pd.to_datetime(df["Date"].str.replace(" ", "", regex=False),
                                format="%Y-%m-%d", errors="coerce")

    # (2) 가격: 천 단위 콤마 제거 후 float 변환
    for col in ["Close", "Open", "High", "Low"]:
        df[col] = pd.to_numeric(df[col].str.replace(",", "", regex=False), errors="coerce")

    # (3) 변동 %: "%" 제거 후 float 변환
    df["Change_pct"] = pd.to_numeric(df["Change_pct"].str.rstrip("%"), errors="coerce")

    # (4) 거래량: 전부 비어 있으면 분석 가치가 없으므로 컬럼 삭제
    if "Volume" in df and df["Volume"].isna().all():
        print("\n- '거래량' 컬럼이 100% 결측 → 삭제")
        df = df.drop(columns="Volume")

    # (5) 변환 실패 / 결측 행 제거
    before = len(df)
    df = df.dropna(subset=["Date", "Close", "Open", "High", "Low"])
    print(f"- 변환 실패·결측 행 제거: {before - len(df)}건")

    # (6) 중복 날짜 제거
    dup = df["Date"].duplicated().sum()
    df = df.drop_duplicates(subset="Date")
    print(f"- 중복 날짜 제거: {dup}건")

    # (7) 논리 오류 검사: 가격 <= 0 은 제거,
    #     고가 < max(시가, 종가) / 저가 > min(시가, 종가) 는 입력 오차로 보고 보정
    #     (행을 지우면 다음 날 수익률이 왜곡되므로 삭제 대신 보정)
    nonpos = (df[["Open", "High", "Low", "Close"]] <= 0).any(axis=1)
    print(f"- 0 이하 가격 행 제거: {nonpos.sum()}건")
    df = df[~nonpos].copy()
    bad = (df["High"] < df[["Open", "Close"]].max(axis=1)) | (df["Low"] > df[["Open", "Close"]].min(axis=1))
    for _, r in df[bad].iterrows():
        print(f"  · OHLC 불일치 보정: {r['Date']:%Y-%m-%d} 시가 {r['Open']} 고가 {r['High']} 저가 {r['Low']} 종가 {r['Close']}")
    df["High"] = df[["Open", "High", "Close"]].max(axis=1)
    df["Low"] = df[["Open", "Low", "Close"]].min(axis=1)
    print(f"- OHLC 논리 오류 행 보정: {bad.sum()}건")

    # (8) 날짜 오름차순 정렬 + 인덱스 지정 (원본은 최신순)
    df = df.sort_values("Date").set_index("Date")

    # (9) 변동 % 검증: 종가로 직접 계산한 수익률과 비교
    calc = df["Close"].pct_change() * 100
    mismatch = ((calc - df["Change_pct"]).abs() > 0.05).sum()
    print(f"- '변동 %' vs 종가로 계산한 수익률 불일치(>0.05%p): {mismatch}건")
    df["Return"] = calc  # 이후 분석은 직접 계산한 수익률 사용

    print(f"\n클렌징 후 shape: {df.shape}")
    print(f"기간: {df.index.min():%Y-%m-%d} ~ {df.index.max():%Y-%m-%d}")
    print(df.dtypes)
    return df


# ---------------------------------------------------------------------------
# 2. 다각도 분석
# ---------------------------------------------------------------------------
def analyze(df):
    """분석 결과를 출력하고, 차트·요약에 쓰이는 값을 dict 로 반환"""
    close = df["Close"]
    ret = df["Return"].dropna()

    section("2. 기술통계")
    print(df[["Open", "High", "Low", "Close", "Return"]].describe())

    section("3. 전체 기간 성과")
    years = (close.index[-1] - close.index[0]).days / 365.25
    total = close.iloc[-1] / close.iloc[0] - 1
    cagr = (1 + total) ** (1 / years) - 1
    vol = ret.std() / 100 * np.sqrt(252)
    print(f"시작 종가 {close.iloc[0]:,.2f} → 마지막 종가 {close.iloc[-1]:,.2f}")
    print(f"누적 수익률: {total:.2%}  |  연평균(CAGR): {cagr:.2%}  |  연환산 변동성: {vol:.2%}")
    print(f"샤프비율(무위험 0% 가정): {cagr / vol:.2f}")

    section("4. 연도별 분석")
    yearly = close.resample("YE").agg(["first", "last", "min", "max"])
    yearly["수익률(%)"] = close.resample("YE").last().pct_change() * 100
    yearly.loc[yearly.index[0], "수익률(%)"] = (yearly["last"].iloc[0] / yearly["first"].iloc[0] - 1) * 100
    yearly["변동성(%)"] = ret.groupby(ret.index.year).std().values * np.sqrt(252)
    yearly.index = yearly.index.year
    print(yearly)
    print(f"\n최고 연도: {yearly['수익률(%)'].idxmax()} ({yearly['수익률(%)'].max():.2f}%)")
    print(f"최악 연도: {yearly['수익률(%)'].idxmin()} ({yearly['수익률(%)'].min():.2f}%)")
    print(f"상승 연도 {(yearly['수익률(%)'] > 0).sum()}개 / 하락 연도 {(yearly['수익률(%)'] <= 0).sum()}개")

    section("5. 최대 낙폭(MDD)")
    peak = close.cummax()
    dd = close / peak - 1
    trough = dd.idxmin()
    peak_date = close[:trough].idxmax()
    recovered = close[trough:][close[trough:] >= close[peak_date]]
    print(f"MDD: {dd.min():.2%}")
    print(f"고점 {peak_date:%Y-%m-%d} ({close[peak_date]:,.2f}) → 저점 {trough:%Y-%m-%d} ({close[trough]:,.2f})")
    print(f"고점 회복일: {recovered.index[0]:%Y-%m-%d}" if len(recovered) else "고점 미회복")

    section("6. 일간 수익률 극단값")
    print("[가장 크게 오른 날 Top 5]")
    print(ret.nlargest(5).to_string())
    print("\n[가장 크게 내린 날 Top 5]")
    print(ret.nsmallest(5).to_string())
    print(f"\n상승일 비율: {(ret > 0).mean():.2%}")

    section("7. 요일별 / 월별 평균 수익률 (%)")
    dow = ret.groupby(ret.index.dayofweek).agg(["mean", "std", "count"])
    dow.index = ["월", "화", "수", "목", "금"]
    print(dow)
    monthly_ret = close.resample("ME").last().pct_change().dropna() * 100
    by_month = monthly_ret.groupby(monthly_ret.index.month).agg(["mean", lambda s: (s > 0).mean() * 100])
    by_month.columns = ["평균 월수익률(%)", "상승 확률(%)"]
    by_month.index = [f"{m}월" for m in by_month.index]
    print()
    print(by_month)

    section("8. 이동평균 기반 추세")
    ma50, ma200 = close.rolling(50).mean(), close.rolling(200).mean()
    signal = (ma50 > ma200).astype(int).diff()
    print(f"골든크로스 횟수: {(signal == 1).sum()}  |  데드크로스 횟수: {(signal == -1).sum()}")
    print(f"200일선 위에 있었던 비율: {(close > ma200)[ma200.notna()].mean():.2%}")

    return {
        "yearly": yearly, "dd": dd, "monthly_ret": monthly_ret,
        "summary": {
            "마지막 종가": f"{close.iloc[-1]:,.2f}",
            "누적 수익률": f"{total:.2%}",
            "연평균(CAGR)": f"{cagr:.2%}",
            "연환산 변동성": f"{vol:.2%}",
            "최대 낙폭(MDD)": f"{dd.min():.2%}",
            "상승일 비율": f"{(ret > 0).mean():.2%}",
        },
    }


# ---------------------------------------------------------------------------
# 3. 시각화 - 각 함수는 전달받은 Figure 에 그림 (GUI 캔버스·파일 저장 공용)
# ---------------------------------------------------------------------------
# 어두운 배경·흰 배경 모두에서 잘 보이는 색
BLUE, GREEN, RED, AMBER, PINK = "#3B82F6", "#22C55E", "#EF4444", "#F59E0B", "#EC4899"


def plot_close_line(fig, df, result, start="2000-01-01", end="2019-12-31"):
    """요청 사항: 종가 기준 라인그래프 (기본 2000년 1월 ~ 2019년 12월)"""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    data = df.loc[start:end, "Close"]

    ax = fig.add_subplot()
    ax.plot(data.index, data.values, color=BLUE, linewidth=1.4, label="종가")
    if len(data):
        floor = data.min() - (data.max() - data.min()) * 0.08   # 최저점 라벨이 들어갈 여백
        ax.fill_between(data.index, data.values, floor, color=BLUE, alpha=0.15)
        ax.set_ylim(bottom=floor)
        # 기간 내 최고점·최저점 표시
        for date, color, label, offset, ha in ((data.idxmax(), GREEN, "최고", (-10, 0), "right"),
                                                (data.idxmin(), RED, "최저", (10, 0), "left")):
            ax.scatter(date, data[date], color=color, s=50, zorder=3)
            ax.annotate(f"{label} {data[date]:,.0f}\n{date:%Y-%m-%d}", (date, data[date]),
                        textcoords="offset points", xytext=offset, ha=ha, va="center",
                        fontsize=9, color=color, fontweight="bold")
    ax.set_title(f"S&P 500 종가 추이 ({start:%Y.%m} ~ {end:%Y.%m})", fontsize=16, fontweight="bold")
    ax.set_xlabel("연도")
    ax.set_ylabel("종가 (포인트)")
    ax.set_xlim(start, end)
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.grid(alpha=0.3)
    ax.legend()


def plot_moving_average(fig, df, result):
    close = df["Close"]
    ax = fig.add_subplot()
    ax.plot(close, label="종가", linewidth=1, color=BLUE, alpha=0.7)
    ax.plot(close.rolling(50).mean(), label="50일 이동평균", linewidth=1.2, color=AMBER)
    ax.plot(close.rolling(200).mean(), label="200일 이동평균", linewidth=1.6, color=PINK)
    ax.set_title("종가와 이동평균선")
    ax.legend(); ax.grid(alpha=0.3)


def plot_yearly_return(fig, df, result):
    yearly = result["yearly"]
    ax = fig.add_subplot()
    colors = [RED if v < 0 else GREEN for v in yearly["수익률(%)"]]
    bars = ax.bar(yearly.index.astype(str), yearly["수익률(%)"], color=colors)
    ax.bar_label(bars, fmt="%.1f", fontsize=8, padding=2)
    ax.axhline(0, color=matplotlib.rcParams["axes.edgecolor"], linewidth=0.8)
    ax.set_title("연도별 수익률 (%)")
    ax.tick_params(axis="x", rotation=45)
    ax.grid(axis="y", alpha=0.3)


def plot_drawdown(fig, df, result):
    dd = result["dd"]
    ax = fig.add_subplot()
    ax.fill_between(dd.index, dd.values * 100, 0, color=RED, alpha=0.4)
    ax.plot(dd.index, dd.values * 100, color=RED, linewidth=0.8)
    ax.set_title("고점 대비 낙폭 (Drawdown, %)")
    ax.grid(alpha=0.3)


def plot_return_dist_volatility(fig, df, result):
    ax1, ax2 = fig.subplots(1, 2)
    ax1.hist(df["Return"].dropna(), bins=100, color=BLUE)
    ax1.set_title("일간 수익률 분포 (%)")
    ax2.plot(df["Return"].rolling(21).std() * np.sqrt(252), color=AMBER, linewidth=1)
    ax2.set_title("21일 롤링 변동성 (연환산, %)")
    for a in (ax1, ax2):
        a.grid(alpha=0.3)


def plot_monthly_heatmap(fig, df, result):
    monthly_ret = result["monthly_ret"]
    pivot = monthly_ret.to_frame("r").assign(Y=monthly_ret.index.year, M=monthly_ret.index.month) \
                       .pivot(index="Y", columns="M", values="r")
    ax = fig.add_subplot()
    lim = np.nanmax(np.abs(pivot.values))
    im = ax.imshow(pivot.values, cmap="RdYlGn", vmin=-lim, vmax=lim, aspect="auto")
    ax.set_xticks(range(pivot.shape[1]), [f"{m}월" for m in pivot.columns])
    ax.set_yticks(range(len(pivot)), pivot.index)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            v = pivot.values[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:.1f}", ha="center", va="center", fontsize=7)
    fig.colorbar(im, ax=ax, label="월 수익률 (%)")
    ax.set_title("연도 x 월 수익률 히트맵 (%)")


# 차트 이름 → (파일명, 그리기 함수)
CHARTS = {
    "종가 라인그래프": ("01_close_2000_2019.png", plot_close_line),
    "종가 + 이동평균선": ("02_moving_average.png", plot_moving_average),
    "연도별 수익률": ("03_yearly_return.png", plot_yearly_return),
    "고점 대비 낙폭": ("04_drawdown.png", plot_drawdown),
    "수익률 분포 / 변동성": ("05_return_dist_volatility.png", plot_return_dist_volatility),
    "월별 수익률 히트맵": ("06_monthly_heatmap.png", plot_monthly_heatmap),
}


# 파일 저장용 차트는 앱 테마와 무관하게 흰 배경 스타일로 그림
EXPORT_STYLE = ["default", {"font.family": "Malgun Gothic", "axes.unicode_minus": False}]


def render_chart_png(name, df, result, dpi=150):
    """차트를 PNG 바이트로 렌더링 (파일·엑셀 저장 공용)"""
    with matplotlib.style.context(EXPORT_STYLE):
        fig = Figure(figsize=(14, 6), layout="tight")
        CHARTS[name][1](fig, df, result)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=dpi)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 4. 엑셀 저장 - 요약 / 정제 데이터 / 연도별 / 월별 히트맵 / 차트 이미지 시트
# ---------------------------------------------------------------------------
def export_excel(df, result, path, include_charts=True):
    from openpyxl.drawing.image import Image as XLImage
    from openpyxl.formatting.rule import CellIsRule, ColorScaleRule
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    header_fill = PatternFill("solid", fgColor="1E293B")
    header_font = Font(bold=True, color="FFFFFF")
    thin = Side(style="thin", color="CBD5E1")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    red_green = ColorScaleRule(start_type="min", start_color="F8696B",
                               mid_type="num", mid_value=0, mid_color="FFFFFF",
                               end_type="max", end_color="63BE7B")

    def style_table(ws, n_rows, n_cols, widths=None, number_format="#,##0.00", start_row=1):
        for c in range(1, n_cols + 1):
            cell = ws.cell(start_row, c)
            cell.fill, cell.font, cell.border = header_fill, header_font, border
            cell.alignment = Alignment(horizontal="center", vertical="center")
            ws.column_dimensions[get_column_letter(c)].width = (widths or {}).get(c, 14)
        for row in ws.iter_rows(min_row=start_row + 1, max_row=start_row + n_rows, max_col=n_cols):
            for cell in row:
                cell.border = border
                if isinstance(cell.value, float):
                    cell.number_format = number_format
        ws.freeze_panes = ws.cell(start_row + 1, 2)

    data = df.reset_index().rename(columns={
        "Date": "날짜", "Close": "종가", "Open": "시가", "High": "고가", "Low": "저가",
        "Change_pct": "변동(%)", "Return": "수익률(%)",
    })
    data["날짜"] = data["날짜"].dt.date

    yearly = result["yearly"].rename(columns={"first": "시초가", "last": "종가", "min": "최저", "max": "최고"})
    yearly.index.name = "연도"

    monthly_ret = result["monthly_ret"]
    heat = monthly_ret.to_frame("r").assign(Y=monthly_ret.index.year, M=monthly_ret.index.month) \
                      .pivot(index="Y", columns="M", values="r")
    heat.columns = [f"{m}월" for m in heat.columns]
    heat.index.name = "연도"

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        # 요약
        summary = pd.DataFrame(list(result["summary"].items()), columns=["지표", "값"])
        summary.to_excel(writer, sheet_name="요약", index=False, startrow=3)
        ws = writer.sheets["요약"]
        ws["A1"] = "S&P 500 과거 데이터 분석 요약"
        ws["A1"].font = Font(size=16, bold=True, color="1E293B")
        ws["A2"] = f"기간: {df.index.min():%Y-%m-%d} ~ {df.index.max():%Y-%m-%d}  ({len(df):,}거래일)"
        ws["A2"].font = Font(color="64748B")
        style_table(ws, len(summary), 2, widths={1: 22, 2: 18}, start_row=4)
        ws.freeze_panes = None
        for row in ws.iter_rows(min_row=5, max_row=4 + len(summary), min_col=2, max_col=2):
            row[0].alignment = Alignment(horizontal="right")
            row[0].font = Font(bold=True)

        # 정제 데이터
        data.to_excel(writer, sheet_name="정제 데이터", index=False)
        ws = writer.sheets["정제 데이터"]
        style_table(ws, len(data), data.shape[1], widths={1: 13})
        ws.auto_filter.ref = ws.dimensions
        rng = f"G2:G{len(data) + 1}"
        ws.conditional_formatting.add(rng, CellIsRule(operator="lessThan", formula=["0"], font=Font(color="DC2626")))
        ws.conditional_formatting.add(rng, CellIsRule(operator="greaterThan", formula=["0"], font=Font(color="16A34A")))

        # 연도별 분석
        yearly.to_excel(writer, sheet_name="연도별 분석")
        ws = writer.sheets["연도별 분석"]
        style_table(ws, len(yearly), yearly.shape[1] + 1, widths={1: 10})
        ws.conditional_formatting.add(f"F2:F{len(yearly) + 1}", red_green)

        # 월별 수익률 히트맵
        heat.to_excel(writer, sheet_name="월별 수익률")
        ws = writer.sheets["월별 수익률"]
        style_table(ws, len(heat), heat.shape[1] + 1, widths={c: 9 for c in range(1, 14)})
        last_col = get_column_letter(heat.shape[1] + 1)
        ws.conditional_formatting.add(f"B2:{last_col}{len(heat) + 1}", red_green)

        # 차트 이미지
        if include_charts:
            ws = writer.book.create_sheet("차트")
            row = 1
            for name in CHARTS:
                ws.cell(row, 1, name).font = Font(size=13, bold=True, color="1E293B")
                img = XLImage(io.BytesIO(render_chart_png(name, df, result, dpi=100)))
                img.width, img.height = 1050, 450
                ws.add_image(img, f"A{row + 1}")
                row += 25


def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSV
    if not csv_path:
        sys.exit(f"CSV 경로를 인자로 주거나 '{CSV_NAME}' 를 이 폴더에 두세요.")
    OUT_DIR.mkdir(exist_ok=True)

    df = load_and_clean(csv_path)
    df.to_csv(OUT_DIR / "sp500_cleaned.csv", encoding="utf-8-sig")
    result = analyze(df)

    for name, (filename, _) in CHARTS.items():
        (OUT_DIR / filename).write_bytes(render_chart_png(name, df, result))
    export_excel(df, result, OUT_DIR / "sp500_analysis.xlsx")

    print(f"\n그래프·정제 데이터·엑셀 저장 위치: {OUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
