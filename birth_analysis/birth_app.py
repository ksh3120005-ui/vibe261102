"""
대한민국 출생아수 분석기 - PyQt6 GUI 앱

실행:
    python birth_app.py
KOSIS 엑셀 파일을 열면 클렌징 → 분석 → 라인 그래프까지 자동으로 수행하며,
결과를 PNG·CSV·엑셀(xlsx)로 저장할 수 있습니다.
"""
import contextlib
import io
import sys
from pathlib import Path

import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PyQt6.QtCore import QAbstractTableModel, Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QTableView,
    QTabWidget, QVBoxLayout, QWidget,
)

import birth_analysis as core
import birth_line_chart as chart

# ---------------------------------------------------------------------------
# 테마 (차트와 같은 밝은 배경 + 블루 포인트)
# ---------------------------------------------------------------------------
BG, SURFACE, SURFACE_2, BORDER = "#f3f2ef", chart.SURFACE, "#f0efec", "#dcdbd6"
TEXT, MUTED, ACCENT = chart.INK, chart.INK_2, chart.LINE
NEGATIVE = "#c8372d"

KPI_NAMES = ["최근 출생아수", "최고 출생아수", "최저 출생아수", "1970년 대비", "최근 합계출산율", "자연감소 시작"]

STYLESHEET = f"""
QMainWindow, QWidget#central {{ background: {BG}; }}
QLabel {{ color: {TEXT}; }}
QStatusBar {{ background: {SURFACE}; color: {MUTED}; border-top: 1px solid {BORDER}; }}

#header {{ background: {ACCENT}; border-radius: 14px; }}
#header QLabel#title {{ font-size: 22px; font-weight: 800; color: white; }}
#header QLabel#subtitle {{ font-size: 12px; color: rgba(255,255,255,0.85); }}
#header QLineEdit {{
    background: rgba(255,255,255,0.18); color: white; border: 1px solid rgba(255,255,255,0.4);
    border-radius: 8px; padding: 7px 10px;
}}
#header QPushButton {{ background: rgba(255,255,255,0.18); color: white; border: 1px solid rgba(255,255,255,0.45); }}
#header QPushButton:hover {{ background: rgba(255,255,255,0.3); }}
#header QPushButton#primary {{ background: white; color: {ACCENT}; border: none; }}

QPushButton {{
    color: {TEXT}; background: {SURFACE}; border: 1px solid {BORDER};
    border-radius: 8px; padding: 7px 16px; font-weight: 600;
}}
QPushButton:hover {{ background: {SURFACE_2}; }}

#card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px; }}
#card QLabel#cardTitle {{ color: {MUTED}; font-size: 12px; }}
#card QLabel#cardValue {{ font-size: 20px; font-weight: 800; }}
#card QLabel#cardNote {{ color: {MUTED}; font-size: 11px; }}

QTabWidget::pane {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px; top: -1px; }}
QTabBar::tab {{
    background: transparent; color: {MUTED}; padding: 9px 22px; margin-right: 4px;
    border-top-left-radius: 10px; border-top-right-radius: 10px; font-weight: 600;
}}
QTabBar::tab:hover {{ color: {TEXT}; background: {SURFACE_2}; }}
QTabBar::tab:selected {{ color: white; background: {ACCENT}; }}

QComboBox, QSpinBox {{
    background: {SURFACE}; color: {TEXT}; border: 1px solid {BORDER};
    border-radius: 8px; padding: 5px 10px; min-width: 80px;
}}
QComboBox:hover, QSpinBox:hover {{ border-color: {ACCENT}; }}

QTableView {{
    background: {SURFACE}; alternate-background-color: {SURFACE_2}; color: {TEXT};
    border: none; selection-background-color: #cde2fb; selection-color: {TEXT};
}}
QHeaderView::section {{
    background: {SURFACE_2}; color: {MUTED}; padding: 6px; border: none;
    border-bottom: 2px solid {ACCENT}; font-weight: 700;
}}
QPlainTextEdit {{ background: {SURFACE}; color: {TEXT}; border: none; padding: 10px; }}
QToolBar {{ background: transparent; border: none; }}
"""


def out_path(name):
    """저장 대화상자의 기본 경로: 스크립트 옆 output 폴더"""
    core.OUT_DIR.mkdir(exist_ok=True)
    return str(core.OUT_DIR / name)


class DataFrameModel(QAbstractTableModel):
    """pandas DataFrame 을 QTableView 에 보여주기 위한 모델"""

    SIGNED_COLUMNS = {"자연증가건수", "자연증가율"}   # 음수는 빨강으로 표시

    def __init__(self, df=None):
        super().__init__()
        self._df = pd.DataFrame() if df is None else df

    def set_frame(self, df):
        self.beginResetModel()
        self._df = df
        self.endResetModel()

    def rowCount(self, parent=None):
        return len(self._df)

    def columnCount(self, parent=None):
        return self._df.shape[1]

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        col = self._df.columns[index.column()]
        value = self._df.iat[index.row(), index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
            if col == "연도":
                return str(value)
            if col == "잠정치":
                return "잠정" if value else ""
            if col == "합계출산율":
                return f"{value:.3f}"
            return f"{value:,}" if pd.api.types.is_integer(value) else f"{value:,.1f}"
        if role == Qt.ItemDataRole.ForegroundRole and col in self.SIGNED_COLUMNS and value < 0:
            return QColor(NEGATIVE)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return str(self._df.columns[section])
        return None


class KpiCard(QFrame):
    """요약 지표 카드 (제목 + 값 + 보조 설명)"""

    def __init__(self, title):
        super().__init__()
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        self.value_label = QLabel("-")
        self.value_label.setObjectName("cardValue")
        self.note_label = QLabel("")
        self.note_label.setObjectName("cardNote")
        for w in (title_label, self.value_label, self.note_label):
            layout.addWidget(w)

    def set_value(self, value, note=""):
        self.value_label.setText(value)
        self.value_label.setStyleSheet(f"color: {NEGATIVE if value.startswith('-') else TEXT};")
        self.note_label.setText(note)


def summarize(df):
    """KPI 카드에 표시할 (값, 설명) 계산"""
    first, last = df.iloc[0], df.iloc[-1]
    peak = df.loc[df["출생아수"].idxmax()]
    low = df.loc[df["출생아수"].idxmin()]
    last_tag = f"{last['연도']}년" + (" (잠정)" if last["잠정치"] else "")
    change = (last["출생아수"] / first["출생아수"] - 1) * 100
    decline = df.loc[df["자연증가건수"] < 0, "연도"]
    return {
        "최근 출생아수": (f"{last['출생아수']:,}명", last_tag),
        "최고 출생아수": (f"{peak['출생아수']:,}명", f"{peak['연도']}년"),
        "최저 출생아수": (f"{low['출생아수']:,}명", f"{low['연도']}년"),
        "1970년 대비": (f"{change:+.1f}%", f"{first['연도']}년 → {last['연도']}년"),
        "최근 합계출산율": (f"{last['합계출산율']:.3f}명", last_tag),
        "자연감소 시작": (f"{decline.min()}년" if not decline.empty else "없음", "사망자 > 출생아"),
    }


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("대한민국 출생아수 분석기")
        self.resize(1320, 900)
        self.df = None
        self.results = None

        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 10)
        root.setSpacing(14)

        root.addWidget(self._build_header())

        # --- 요약 지표 카드 ---
        kpi_grid = QGridLayout()
        kpi_grid.setSpacing(12)
        self.kpi_cards = {}
        for i, name in enumerate(KPI_NAMES):
            self.kpi_cards[name] = KpiCard(name)
            kpi_grid.addWidget(self.kpi_cards[name], 0, i)
        root.addLayout(kpi_grid)

        # --- 탭 ---
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_chart_tab(), "📊  라인 그래프")
        self.tabs.addTab(self._build_data_tab(), "🗂️  정제 데이터")
        self.clean_log = self._make_text_view()
        self.tabs.addTab(self.clean_log, "🧹  클렌징 로그")
        self.analysis_log = self._make_text_view()
        self.tabs.addTab(self.analysis_log, "🔍  분석 결과")
        root.addWidget(self.tabs, 1)

        if core.DEFAULT_XLSX.exists():
            self.run_analysis()
        else:
            self.statusBar().showMessage("📂 [찾아보기]로 출생아수 엑셀 파일을 선택하세요.")

    # ---------------- UI 구성 ----------------
    def _build_header(self):
        header = QFrame()
        header.setObjectName("header")
        layout = QVBoxLayout(header)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        title_row = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = QLabel("👶 대한민국 출생아수 분석기")
        title.setObjectName("title")
        self.subtitle = QLabel("출생아수 · 합계출산율 · 자연증가 데이터 클렌징 · 분석 · 시각화")
        self.subtitle.setObjectName("subtitle")
        titles.addWidget(title)
        titles.addWidget(self.subtitle)
        title_row.addLayout(titles)
        title_row.addStretch(1)
        excel_btn = QPushButton("📥  엑셀로 저장")
        excel_btn.clicked.connect(self.export_excel)
        title_row.addWidget(excel_btn)
        layout.addLayout(title_row)

        file_row = QHBoxLayout()
        self.path_edit = QLineEdit(str(core.DEFAULT_XLSX) if core.DEFAULT_XLSX.exists() else "")
        self.path_edit.setPlaceholderText("출생아수__합계출산율__자연증가_등.xlsx 경로")
        browse_btn = QPushButton("📂  찾아보기")
        browse_btn.clicked.connect(self.browse_file)
        run_btn = QPushButton("▶  분석 실행")
        run_btn.setObjectName("primary")
        run_btn.clicked.connect(self.run_analysis)
        for b in (excel_btn, browse_btn, run_btn):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        file_row.addWidget(self.path_edit, 1)
        file_row.addWidget(browse_btn)
        file_row.addWidget(run_btn)
        layout.addLayout(file_row)
        return header

    def _build_chart_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)

        controls = QHBoxLayout()
        self.indicator_combo = QComboBox()
        self.indicator_combo.addItems(chart.INDICATORS.keys())
        self.indicator_combo.setMinimumWidth(140)
        self.indicator_combo.currentTextChanged.connect(self.redraw_chart)

        self.start_year = QSpinBox()
        self.end_year = QSpinBox()
        for w, value in ((self.start_year, 1970), (self.end_year, 2025)):
            w.setRange(1970, 2025)
            w.setValue(value)
            w.valueChanged.connect(self.redraw_chart)

        reset_btn = QPushButton("전체 기간")
        reset_btn.clicked.connect(self.reset_period)
        save_btn = QPushButton("🖼️  PNG 저장")
        save_btn.clicked.connect(self.save_chart)

        controls.addWidget(QLabel("지표"))
        controls.addWidget(self.indicator_combo)
        controls.addSpacing(20)
        controls.addWidget(QLabel("기간"))
        controls.addWidget(self.start_year)
        controls.addWidget(QLabel("~"))
        controls.addWidget(self.end_year)
        controls.addWidget(reset_btn)
        controls.addStretch(1)

        self.figure = Figure()
        self.canvas = FigureCanvasQTAgg(self.figure)
        controls.addWidget(NavigationToolbar2QT(self.canvas, tab))
        controls.addWidget(save_btn)
        layout.addLayout(controls)
        layout.addWidget(self.canvas, 1)
        return tab

    def _build_data_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)
        self.table_model = DataFrameModel()
        table = QTableView()
        table.setModel(self.table_model)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setDefaultSectionSize(28)
        export_btn = QPushButton("💾  CSV로 저장")
        export_btn.clicked.connect(self.export_csv)
        row = QHBoxLayout()
        self.data_info = QLabel("")
        self.data_info.setStyleSheet(f"color: {MUTED};")
        row.addWidget(self.data_info)
        row.addStretch(1)
        row.addWidget(export_btn)
        layout.addLayout(row)
        layout.addWidget(table, 1)
        return tab

    @staticmethod
    def _make_text_view():
        view = QPlainTextEdit()
        view.setReadOnly(True)
        view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        view.setFont(QFont("D2Coding, Consolas, Malgun Gothic", 10))
        return view

    # ---------------- 동작 ----------------
    def browse_file(self):
        start_dir = str(Path(self.path_edit.text()).parent) if self.path_edit.text() else ""
        path, _ = QFileDialog.getOpenFileName(self, "출생아수 엑셀 선택", start_dir, "Excel 파일 (*.xlsx)")
        if path:
            self.path_edit.setText(path)
            self.run_analysis()

    def run_analysis(self):
        path = self.path_edit.text().strip()
        try:
            # 분석 모듈의 print 출력을 잡아서 텍스트 탭에 표시
            clean_buf, analysis_buf = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(clean_buf):
                df = core.load_and_clean(path)
            with contextlib.redirect_stdout(analysis_buf):
                results = core.analyze(df)
        except Exception as e:  # 잘못된 파일·형식 등
            QMessageBox.critical(self, "분석 실패", f"파일을 분석하지 못했습니다.\n\n{e}")
            self.statusBar().showMessage("분석 실패")
            return

        self.df, self.results = df, results
        first, last = int(df["연도"].min()), int(df["연도"].max())
        self.subtitle.setText(f"출생아수 · 합계출산율 · 자연증가 데이터 클렌징 · 분석 · 시각화   |   {first}~{last}년")
        self.clean_log.setPlainText(clean_buf.getvalue())
        self.analysis_log.setPlainText(analysis_buf.getvalue())
        self.table_model.set_frame(df)
        self.data_info.setText(f"총 {len(df)}개 연도 · 자연증가 음수(인구 자연감소)는 빨강")
        for name, (value, note) in summarize(df).items():
            self.kpi_cards[name].set_value(value, note)

        for w in (self.start_year, self.end_year):   # 데이터 기간에 맞춰 연도 범위 갱신
            w.blockSignals(True)
            w.setRange(first, last)
        self.start_year.setValue(first)
        self.end_year.setValue(last)
        for w in (self.start_year, self.end_year):
            w.blockSignals(False)

        self.redraw_chart()
        self.statusBar().showMessage(f"✅ 분석 완료: {first}~{last}년, {len(df)}개 연도")

    def reset_period(self):
        if self.df is not None:
            self.start_year.setValue(int(self.df["연도"].min()))
            self.end_year.setValue(int(self.df["연도"].max()))

    def redraw_chart(self):
        if self.df is None:
            return
        start, end = self.start_year.value(), self.end_year.value()
        if start >= end:
            self.statusBar().showMessage("⚠️ 시작 연도가 종료 연도보다 빨라야 합니다.")
            return
        chart.draw(self.figure, self.df, self.indicator_combo.currentText(), start, end)
        self.canvas.draw()
        self.statusBar().showMessage(f"📊 {self.indicator_combo.currentText()} {start}~{end}년")

    def save_chart(self):
        if self.df is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "그래프 저장", out_path("birth_line_chart.png"), "PNG 이미지 (*.png)")
        if path:
            self.figure.savefig(path, dpi=150, facecolor=chart.SURFACE)
            self.statusBar().showMessage(f"💾 저장됨: {path}")

    def export_csv(self):
        if self.df is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "정제 데이터 저장", out_path("birth_clean.csv"), "CSV 파일 (*.csv)")
        if path:
            self.df.to_csv(path, index=False, encoding="utf-8-sig")
            self.statusBar().showMessage(f"💾 저장됨: {path}")

    def export_excel(self):
        if self.df is None:
            QMessageBox.information(self, "엑셀 저장", "먼저 분석을 실행하세요.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "엑셀로 저장", out_path("birth_analysis.xlsx"), "Excel 통합 문서 (*.xlsx)")
        if not path:
            return
        try:
            core.export_excel(self.df, self.results, path)
        except PermissionError:
            QMessageBox.warning(self, "엑셀 저장 실패",
                                "파일이 다른 프로그램(엑셀 등)에서 열려 있습니다.\n닫은 뒤 다시 시도하세요.")
            return
        except Exception as e:
            QMessageBox.critical(self, "엑셀 저장 실패", str(e))
            return
        self.statusBar().showMessage(f"📥 엑셀 저장 완료: {path}")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Malgun Gothic", 9))
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
