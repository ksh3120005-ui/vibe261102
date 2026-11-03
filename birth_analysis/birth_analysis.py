"""
대한민국 출생아수·합계출산율·자연증가 데이터 클렌징 + 다각도 분석 (pandas)

실행:
    python birth_analysis.py [엑셀 경로]
정제 데이터(CSV)와 분석 결과(엑셀)는 이 스크립트와 같은 폴더의 output/ 에 저장됩니다.
"""
import sys
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")  # 'no default style' 경고 무시
if sys.stdout and hasattr(sys.stdout, "reconfigure"):   # GUI(exe) 실행 시 stdout 이 없을 수 있음
    sys.stdout.reconfigure(encoding="utf-8")

APP_DIR = Path(__file__).resolve().parent
OUT_DIR = APP_DIR / "output"
DEFAULT_XLSX = Path(r"C:\Users\user\Desktop\생산성본부_바이브코딩수업\DataSet\출생아수__합계출산율__자연증가_등.xlsx")

# 원본 행 이름 → 분석용 컬럼 이름
COLUMN_MAP = {
    "출생아수(명)": "출생아수",
    "자연증가건수(명)": "자연증가건수",
    "조출생률(천명당)": "조출생률",
    "자연증가율(천명당)": "자연증가율",
    "합계출산율(명)": "합계출산율",
    "출생성비(명)": "출생성비",
}

pd.set_option("display.width", 140)
pd.set_option("display.max_columns", 20)
pd.set_option("display.float_format", "{:,.3f}".format)


def section(title):
    print(f"\n{'=' * 70}\n {title}\n{'=' * 70}")


# ----------------------------------------------------------------------------
# 1. 데이터 클렌징
# ----------------------------------------------------------------------------
def load_and_clean(path=DEFAULT_XLSX):
    """KOSIS 엑셀(연도가 열인 wide 형태)을 연도별 행(long 형태) DataFrame 으로 정제"""
    raw = pd.read_excel(path, sheet_name="데이터", header=None)

    section("1. 원본 데이터 확인")
    print(f"원본 크기: {raw.shape}  (행=지표, 열=연도)")
    print(raw.iloc[:, :6])

    # (1) 첫 행을 헤더로, 첫 열을 인덱스로 → 전치(transpose)해서 연도를 행으로
    df = raw.set_index(0).T
    df.columns.name = None
    df = df.rename(columns={"기본항목별": "연도"})

    # (2) 연도 정리: '2025 p)' 같은 잠정치 표기를 분리해서 '잠정치' 플래그로 보존
    year_str = df["연도"].astype(str).str.strip()
    df["잠정치"] = year_str.str.contains("p", case=False)
    df["연도"] = year_str.str.extract(r"(\d{4})")[0].astype(int)

    # (3) 지표 컬럼명 간소화 + 숫자형 변환 (문자/공백/'-' 등은 NaN 처리)
    df = df.rename(columns=COLUMN_MAP)
    for col in COLUMN_MAP.values():
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", "").str.strip(), errors="coerce")

    # (4) 결측치·중복·이상치 점검
    print("\n[결측치 개수]")
    print(df[list(COLUMN_MAP.values())].isna().sum().to_string())
    dup = df["연도"].duplicated().sum()
    print(f"\n[연도 중복] {dup}건")
    df = df.drop_duplicates("연도").sort_values("연도").reset_index(drop=True)

    missing_years = sorted(set(range(df["연도"].min(), df["연도"].max() + 1)) - set(df["연도"]))
    print(f"[누락 연도] {missing_years or '없음'}")

    # 결측이 있으면 선형보간 (현재 데이터에는 없음)
    df[list(COLUMN_MAP.values())] = df[list(COLUMN_MAP.values())].interpolate()

    # 명(人) 단위 지표는 정수형으로
    for col in ("출생아수", "자연증가건수"):
        df[col] = df[col].round().astype("int64")

    # 논리 검증: 값 범위가 상식적인지
    checks = {
        "출생아수 > 0": (df["출생아수"] > 0).all(),
        "합계출산율 0~10": df["합계출산율"].between(0, 10).all(),
        "출생성비 90~130": df["출생성비"].between(90, 130).all(),
    }
    print("[값 범위 검증]", ", ".join(f"{k}: {'OK' if v else '확인 필요'}" for k, v in checks.items()))

    df = df[["연도", "잠정치", *COLUMN_MAP.values()]]
    section("정제 후 데이터 (상·하위 5행)")
    print(df.head().to_string(index=False))
    print("...")
    print(df.tail().to_string(index=False))
    print(f"\n정제 후 크기: {df.shape}, 기간: {df['연도'].min()}~{df['연도'].max()}")
    df.info()
    return df


# ----------------------------------------------------------------------------
# 2. 다각도 분석
# ----------------------------------------------------------------------------
def analyze(df):
    results = {}

    # (1) 기술통계
    section("2-1. 기술통계")
    desc = df.drop(columns=["연도", "잠정치"]).describe().T
    print(desc)
    results["기술통계"] = desc

    # (2) 최고·최저 연도
    section("2-2. 지표별 최고/최저 연도")
    extremes = pd.DataFrame({
        col: {
            "최고 연도": df.loc[df[col].idxmax(), "연도"],
            "최고값": df[col].max(),
            "최저 연도": df.loc[df[col].idxmin(), "연도"],
            "최저값": df[col].min(),
        }
        for col in COLUMN_MAP.values()
    }).T
    extremes = extremes.astype({"최고 연도": int, "최저 연도": int})
    print(extremes)
    results["최고최저"] = extremes

    # (3) 전년 대비 증감
    section("2-3. 출생아수 전년 대비 증감")
    yoy = df[["연도", "출생아수"]].copy()
    yoy["증감(명)"] = yoy["출생아수"].diff()
    yoy["증감률(%)"] = yoy["출생아수"].pct_change() * 100
    print("▶ 감소폭이 가장 컸던 5개 연도")
    print(yoy.nsmallest(5, "증감률(%)").to_string(index=False))
    print("\n▶ 증가폭이 가장 컸던 5개 연도")
    print(yoy.nlargest(5, "증감률(%)").to_string(index=False))
    print("\n▶ 최근 10년")
    print(yoy.tail(10).to_string(index=False))
    results["전년대비"] = yoy

    # (4) 연대별 평균
    section("2-4. 연대별 평균")
    decade = df.assign(연대=(df["연도"] // 10 * 10).astype(str) + "년대")
    by_decade = decade.groupby("연대")[list(COLUMN_MAP.values())].mean()
    by_decade["출생아수"] = by_decade["출생아수"].round().astype("int64")
    by_decade["자연증가건수"] = by_decade["자연증가건수"].round().astype("int64")
    print(by_decade)
    results["연대별평균"] = by_decade

    # (5) 장기 변화: 1970 대비 & CAGR
    section("2-5. 장기 변화 (1970 → 최근)")
    first, last = df.iloc[0], df.iloc[-1]
    n_years = last["연도"] - first["연도"]
    for col in ("출생아수", "합계출산율", "조출생률"):
        ratio = last[col] / first[col]
        cagr = (ratio ** (1 / n_years) - 1) * 100
        print(f"{col:6s}: {first[col]:>12,.3f} → {last[col]:>12,.3f}  "
              f"({(ratio - 1) * 100:+.1f}%, 연평균 {cagr:+.2f}%)")

    # (6) 주요 임계점
    section("2-6. 주요 임계점")
    milestones = {
        "합계출산율 2.1 미만(인구대체수준 하회) 첫 해": df.loc[df["합계출산율"] < 2.1, "연도"].min(),
        "합계출산율 1.3 미만(초저출산) 첫 해": df.loc[df["합계출산율"] < 1.3, "연도"].min(),
        "합계출산율 1.0 미만 첫 해": df.loc[df["합계출산율"] < 1.0, "연도"].min(),
        "출생아수 50만 명 미만 첫 해": df.loc[df["출생아수"] < 500_000, "연도"].min(),
        "출생아수 30만 명 미만 첫 해": df.loc[df["출생아수"] < 300_000, "연도"].min(),
        "자연증가 마이너스(인구 자연감소) 첫 해": df.loc[df["자연증가건수"] < 0, "연도"].min(),
    }
    for k, v in milestones.items():
        print(f"  - {k}: {v}년")
    results["임계점"] = pd.Series(milestones, name="연도").to_frame()

    # (7) 상관관계
    section("2-7. 지표 간 상관계수 (Pearson)")
    corr = df[list(COLUMN_MAP.values())].corr()
    print(corr)
    results["상관계수"] = corr

    # (8) 출생성비 정상범위(103~107) 이탈 연도
    section("2-8. 출생성비 정상범위(103~107) 초과 연도")
    abnormal = df.loc[df["출생성비"] > 107, ["연도", "출생성비"]]
    print(abnormal.to_string(index=False))
    print(f"→ 총 {len(abnormal)}개 연도, 마지막 초과 연도: {abnormal['연도'].max()}년")

    # (9) 최근 반등 여부
    section("2-9. 최근 반등 여부")
    recent = df.tail(4)[["연도", "잠정치", "출생아수", "합계출산율"]]
    print(recent.to_string(index=False))
    low_year = df.loc[df["출생아수"].idxmin(), "연도"]
    print(f"→ 출생아수 최저점은 {low_year}년, 이후 {len(df[df['연도'] > low_year])}년 연속 증가"
          f" (2025년은 잠정치)")

    return results


def export_excel(df, results, path):
    """정제 데이터 + 분석 결과 표를 시트별로 엑셀에 저장"""
    with pd.ExcelWriter(path) as writer:
        df.to_excel(writer, sheet_name="정제데이터", index=False)
        for name, table in results.items():
            table.to_excel(writer, sheet_name=name, index=name not in ("전년대비",))


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_XLSX
    df = load_and_clean(path)
    results = analyze(df)

    OUT_DIR.mkdir(exist_ok=True)
    df.to_csv(OUT_DIR / "birth_clean.csv", index=False, encoding="utf-8-sig")
    export_excel(df, results, OUT_DIR / "birth_analysis.xlsx")
    print(f"\n저장 완료: {OUT_DIR / 'birth_clean.csv'}, {OUT_DIR / 'birth_analysis.xlsx'}")


if __name__ == "__main__":
    main()
