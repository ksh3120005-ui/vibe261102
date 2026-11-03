"""
S&P 500 과거 데이터 분석기 - PyQt6 GUI 앱

실행:
    python sp500_app.py
CSV 파일을 열면 클렌징 → 분석 → 차트까지 자동으로 수행하며,
결과를 PNG·CSV·엑셀(xlsx)로 저장할 수 있습니다.
"""
import contextlib
import io
import sys
from pathlib import Path

import matplotlib
import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PyQt6.QtCore import QAbstractTableModel, QDate, Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QPalette
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDateEdit, QFileDialog, QFrame, QGraphicsDropShadowEffect,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPlainTextEdit, QPushButton, QTableView, QTabWidget, QVBoxLayout, QWidget,
)

import sp500_analysis as core

CLOSE_CHART = "종가 라인그래프"

# ---------------------------------------------------------------------------
# 테마 (다크 네이비 + 블루·바이올렛 그라데이션)
# ---------------------------------------------------------------------------
BG, SURFACE, SURFACE_2, BORDER = "#0B1120", "#111827", "#1F2937", "#334155"
TEXT, MUTED = "#E2E8F0", "#94A3B8"
POSITIVE, NEGATIVE = "#22C55E", "#EF4444"

# 카드 이름 → (아이콘, 강조색)
KPI_STYLE = {
    "마지막 종가": ("💵", "#3B82F6"),
    "누적 수익률": ("🚀", "#8B5CF6"),
    "연평균(CAGR)": ("📈", "#06B6D4"),
    "연환산 변동성": ("🌊", "#F59E0B"),
    "최대 낙폭(MDD)": ("📉", "#EF4444"),
    "상승일 비율": ("☀️", "#22C55E"),
}

STYLESHEET = f"""
QMainWindow, QWidget#central {{ background: {BG}; }}
QLabel {{ color: {TEXT}; }}
QStatusBar {{ background: {SURFACE}; color: {MUTED}; border-top: 1px solid {BORDER}; }}

#header {{
    border-radius: 16px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #1D4ED8, stop:0.55 #6D28D9, stop:1 #BE185D);
}}
#header QLabel#title {{ font-size: 24px; font-weight: 800; color: white; }}
#header QLabel#subtitle {{ font-size: 12px; color: rgba(255,255,255,0.8); }}
#header QLineEdit {{
    background: rgba(255,255,255,0.15); color: white; border: 1px solid rgba(255,255,255,0.3);
    border-radius: 8px; padding: 7px 10px; selection-background-color: #1D4ED8;
}}

QPushButton {{
    color: {TEXT}; background: {SURFACE_2}; border: 1px solid {BORDER};
    border-radius: 8px; padding: 7px 16px; font-weight: 600;
}}
QPushButton:hover {{ background: {BORDER}; }}
QPushButton:pressed {{ background: {SURFACE}; }}
QPushButton#ghost {{ background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.35); color: white; }}
QPushButton#ghost:hover {{ background: rgba(255,255,255,0.28); }}
QPushButton#primary {{
    color: #1E1B4B; border: none;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FFFFFF, stop:1 #E0E7FF);
}}
QPushButton#primary:hover {{ background: white; }}
QPushButton#excel {{
    color: white; border: none;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10B981);
}}
QPushButton#excel:hover {{ background: #10B981; }}

#card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 14px; }}
#card QLabel#cardTitle {{ color: {MUTED}; font-size: 12px; }}
#card QLabel#cardIcon {{ font-size: 20px; }}
#card QLabel#cardValue {{ font-size: 22px; font-weight: 800; }}

QTabWidget::pane {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 14px; top: -1px; }}
QTabBar::tab {{
    background: transparent; color: {MUTED}; padding: 9px 22px; margin-right: 4px;
    border-top-left-radius: 10px; border-top-right-radius: 10px; font-weight: 600;
}}
QTabBar::tab:hover {{ color: {TEXT}; background: {SURFACE_2}; }}
QTabBar::tab:selected {{
    color: white;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563EB, stop:1 #7C3AED);
}}

QComboBox, QDateEdit {{
    background: {SURFACE_2}; color: {TEXT}; border: 1px solid {BORDER};
    border-radius: 8px; padding: 6px 10px; min-width: 110px;
}}
QComboBox:hover, QDateEdit:hover {{ border-color: #6366F1; }}
QComboBox:disabled, QDateEdit:disabled {{ color: #475569; background: {SURFACE}; }}
QComboBox QAbstractItemView {{
    background: {SURFACE_2}; color: {TEXT}; selection-background-color: #4F46E5; border: 1px solid {BORDER};
}}

QTableView {{
    background: {SURFACE}; alternate-background-color: #162033; color: {TEXT};
    gridline-color: {SURFACE_2}; border: none; selection-background-color: #4338CA;
}}
QHeaderView::section {{
    background: {SURFACE_2}; color: {MUTED}; padding: 6px; border: none;
    border-bottom: 2px solid #6366F1; font-weight: 700;
}}
QHeaderView::section:vertical {{ border-bottom: none; border-right: 2px solid #6366F1; padding: 0 8px; }}
QTableCornerButton::section {{ background: {SURFACE_2}; border: none; }}

QPlainTextEdit {{
    background: {SURFACE}; color: #C7D2FE; border: none; padding: 10px;
    selection-background-color: #4338CA;
}}

QScrollBar:vertical, QScrollBar:horizontal {{ background: {SURFACE}; border: none; width: 10px; height: 10px; }}
QScrollBar::handle {{ background: {BORDER}; border-radius: 5px; min-height: 30px; min-width: 30px; }}
QScrollBar::handle:hover {{ background: #475569; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

QToolBar {{ background: transparent; border: none; }}
QToolButton {{ background: transparent; border-radius: 6px; padding: 3px; }}
QToolButton:hover {{ background: {SURFACE_2}; }}
"""

# 앱 화면용 차트 스타일 (엑셀·CLI 저장 차트는 sp500_analysis.EXPORT_STYLE 의 흰 배경 사용)
CHART_STYLE = {
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": BORDER, "axes.labelcolor": MUTED, "axes.titlecolor": TEXT,
    "xtick.color": MUTED, "ytick.color": MUTED, "text.color": TEXT,
    "grid.color": BORDER, "legend.facecolor": SURFACE_2, "legend.edgecolor": BORDER,
    "legend.labelcolor": TEXT, "axes.titlesize": 15, "axes.titleweight": "bold",
}


def resource_path(name):
    """PyInstaller exe 에서는 임시 폴더(sys._MEIPASS)에, 그 외에는 이 파일 옆에 있는 리소스 경로"""
    base = getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)
    return str(Path(base) / name)


def out_path(name):
    """저장 대화상자의 기본 경로: exe(스크립트) 옆 output 폴더"""
    core.OUT_DIR.mkdir(exist_ok=True)
    return str(core.OUT_DIR / name)


def add_shadow(widget, blur=24, alpha=110):
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, 4)
    effect.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(effect)


class DataFrameModel(QAbstractTableModel):
    """pandas DataFrame 을 QTableView 에 보여주기 위한 모델"""

    SIGNED_COLUMNS = {"Change_pct", "Return"}   # 양수=초록, 음수=빨강으로 표시

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
        value = self._df.iat[index.row(), index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
            if isinstance(value, float):
                return "" if pd.isna(value) else f"{value:,.2f}"
            return str(value)
        if role == Qt.ItemDataRole.ForegroundRole and self._df.columns[index.column()] in self.SIGNED_COLUMNS:
            if pd.notna(value) and value != 0:
                return QColor(POSITIVE if value > 0 else NEGATIVE)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return str(self._df.columns[section])
        return f"{self._df.index[section]:%Y-%m-%d}"


class KpiCard(QFrame):
    """요약 지표 카드 (아이콘 + 제목 + 값, 상단 컬러 바)"""

    def __init__(self, title):
        super().__init__()
        icon, self.accent = KPI_STYLE[title]
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 12)
        layout.setSpacing(6)

        bar = QFrame()
        bar.setFixedHeight(4)
        bar.setStyleSheet(f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
                          f" stop:0 {self.accent}, stop:1 transparent);"
                          " border-top-left-radius: 14px; border-top-right-radius: 14px;")
        layout.addWidget(bar)

        top = QHBoxLayout()
        top.setContentsMargins(16, 4, 16, 0)
        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        icon_label = QLabel(icon)
        icon_label.setObjectName("cardIcon")
        top.addWidget(title_label)
        top.addStretch(1)
        top.addWidget(icon_label)
        layout.addLayout(top)

        self.value_label = QLabel("-")
        self.value_label.setObjectName("cardValue")
        self.value_label.setContentsMargins(16, 0, 16, 0)
        layout.addWidget(self.value_label)
        add_shadow(self)

    def set_value(self, text):
        self.value_label.setText(text)
        color = NEGATIVE if text.startswith("-") else self.accent
        self.value_label.setStyleSheet(f"color: {color};")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("S&P 500 Analytics")
        self.resize(1360, 900)
        self.df = None
        self.result = None

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
        for i, name in enumerate(KPI_STYLE):
            card = KpiCard(name)
            self.kpi_cards[name] = card
            kpi_grid.addWidget(card, 0, i)
        root.addLayout(kpi_grid)

        # --- 탭 ---
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_chart_tab(), "📊  차트")
        self.tabs.addTab(self._build_data_tab(), "🗂️  정제 데이터")
        self.clean_log = self._make_text_view()
        self.tabs.addTab(self.clean_log, "🧹  클렌징 로그")
        self.analysis_log = self._make_text_view()
        self.tabs.addTab(self.analysis_log, "🔍  분석 결과")
        root.addWidget(self.tabs, 1)

        self.statusBar().showMessage("CSV 파일을 선택하고 [분석 실행]을 누르세요.")

        if core.DEFAULT_CSV:
            self.run_analysis()
        else:
            self.statusBar().showMessage(f"📂 [찾아보기]로 '{core.CSV_NAME}' 파일을 선택하세요.")

    # ---------------- UI 구성 ----------------
    def _build_header(self):
        header = QFrame()
        header.setObjectName("header")
        layout = QVBoxLayout(header)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(12)

        title_row = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = QLabel("📈 S&P 500 Analytics")
        title.setObjectName("title")
        self.subtitle = QLabel("과거 데이터 클렌징 · 다각도 분석 · 시각화")
        self.subtitle.setObjectName("subtitle")
        titles.addWidget(title)
        titles.addWidget(self.subtitle)
        title_row.addLayout(titles)
        title_row.addStretch(1)
        excel_btn = QPushButton("📥  엑셀로 저장")
        excel_btn.setObjectName("excel")
        excel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        excel_btn.clicked.connect(self.export_excel)
        title_row.addWidget(excel_btn)
        layout.addLayout(title_row)

        file_row = QHBoxLayout()
        self.path_edit = QLineEdit(core.DEFAULT_CSV)
        self.path_edit.setPlaceholderText("S&P 500 과거 데이터 CSV 파일 경로")
        browse_btn = QPushButton("📂  찾아보기")
        browse_btn.setObjectName("ghost")
        browse_btn.clicked.connect(self.browse_file)
        run_btn = QPushButton("▶  분석 실행")
        run_btn.setObjectName("primary")
        run_btn.clicked.connect(self.run_analysis)
        for b in (browse_btn, run_btn):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        file_row.addWidget(self.path_edit, 1)
        file_row.addWidget(browse_btn)
        file_row.addWidget(run_btn)
        layout.addLayout(file_row)

        add_shadow(header, blur=32, alpha=140)
        return header

    def _build_chart_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)

        controls = QHBoxLayout()
        self.chart_combo = QComboBox()
        self.chart_combo.addItems(core.CHARTS.keys())
        self.chart_combo.setMinimumWidth(180)
        self.chart_combo.currentTextChanged.connect(self.redraw_chart)

        self.start_date = QDateEdit(QDate(2000, 1, 1))
        self.end_date = QDateEdit(QDate(2019, 12, 31))
        for w in (self.start_date, self.end_date):
            w.setCalendarPopup(True)
            w.setDisplayFormat("yyyy-MM-dd")
            w.dateChanged.connect(self.redraw_chart)

        save_btn = QPushButton("🖼️  PNG 저장")
        save_btn.clicked.connect(self.save_chart)

        controls.addWidget(QLabel("차트"))
        controls.addWidget(self.chart_combo)
        controls.addSpacing(20)
        controls.addWidget(QLabel("기간"))
        controls.addWidget(self.start_date)
        controls.addWidget(QLabel("~"))
        controls.addWidget(self.end_date)
        controls.addStretch(1)
        controls.addWidget(save_btn)
        layout.addLayout(controls)

        self.figure = Figure(layout="tight")
        self.canvas = FigureCanvasQTAgg(self.figure)
        toolbar = NavigationToolbar2QT(self.canvas, tab)
        controls.insertWidget(controls.count() - 1, toolbar)
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
        path, _ = QFileDialog.getOpenFileName(
            self, "S&P 500 CSV 선택", str(Path(self.path_edit.text()).parent), "CSV 파일 (*.csv)")
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
                result = core.analyze(df)
        except Exception as e:  # 잘못된 파일·형식 등
            QMessageBox.critical(self, "분석 실패", f"파일을 분석하지 못했습니다.\n\n{e}")
            self.statusBar().showMessage("분석 실패")
            return

        self.df, self.result = df, result
        period = f"{df.index.min():%Y-%m-%d} ~ {df.index.max():%Y-%m-%d}"
        self.subtitle.setText(f"과거 데이터 클렌징 · 다각도 분석 · 시각화   |   {period}  ·  {len(df):,}거래일")
        self.clean_log.setPlainText(clean_buf.getvalue())
        self.analysis_log.setPlainText(analysis_buf.getvalue())
        self.table_model.set_frame(df)
        self.data_info.setText(f"총 {len(df):,}행 · 수익률 양수는 초록, 음수는 빨강")
        for name, value in result["summary"].items():
            self.kpi_cards[name].set_value(value)
        self.redraw_chart()
        self.statusBar().showMessage(f"✅ 분석 완료: {len(df):,}행, {period}")

    def redraw_chart(self):
        name = self.chart_combo.currentText()
        is_close = name == CLOSE_CHART
        self.start_date.setEnabled(is_close)
        self.end_date.setEnabled(is_close)
        if self.df is None:
            return

        _, draw = core.CHARTS[name]
        with matplotlib.rc_context(CHART_STYLE):
            self.figure.clear()
            self.figure.set_facecolor(SURFACE)
            if is_close:
                start = self.start_date.date().toString("yyyy-MM-dd")
                end = self.end_date.date().toString("yyyy-MM-dd")
                if start >= end:
                    self.statusBar().showMessage("⚠️ 시작일이 종료일보다 빨라야 합니다.")
                    return
                draw(self.figure, self.df, self.result, start, end)
            else:
                draw(self.figure, self.df, self.result)
        self.canvas.draw()

    def save_chart(self):
        if self.df is None:
            return
        default_name = core.CHARTS[self.chart_combo.currentText()][0]
        path, _ = QFileDialog.getSaveFileName(
            self, "차트 저장", out_path(default_name), "PNG 이미지 (*.png)")
        if path:
            self.figure.savefig(path, dpi=150)
            self.statusBar().showMessage(f"💾 저장됨: {path}")

    def export_csv(self):
        if self.df is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "정제 데이터 저장", out_path("sp500_cleaned.csv"), "CSV 파일 (*.csv)")
        if path:
            self.df.to_csv(path, encoding="utf-8-sig")
            self.statusBar().showMessage(f"💾 저장됨: {path}")

    def export_excel(self):
        if self.df is None:
            QMessageBox.information(self, "엑셀 저장", "먼저 분석을 실행하세요.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "엑셀로 저장", out_path("sp500_analysis.xlsx"), "Excel 통합 문서 (*.xlsx)")
        if not path:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            core.export_excel(self.df, self.result, path)
        except PermissionError:
            QMessageBox.warning(self, "엑셀 저장 실패",
                                "파일이 다른 프로그램(엑셀 등)에서 열려 있습니다.\n닫은 뒤 다시 시도하세요.")
            return
        except Exception as e:
            QMessageBox.critical(self, "엑셀 저장 실패", str(e))
            return
        finally:
            QApplication.restoreOverrideCursor()
        self.statusBar().showMessage(f"📥 엑셀 저장 완료: {path}")
        QMessageBox.information(self, "엑셀 저장 완료",
                                f"다음 시트로 저장했습니다.\n요약 · 정제 데이터 · 연도별 분석 · 월별 수익률 · 차트\n\n{path}")


def dark_palette():
    """Fusion 스타일용 다크 팔레트 (달력 팝업·툴바 아이콘 등 QSS 가 닿지 않는 곳까지 적용)"""
    p = QPalette()
    for role, color in {
        QPalette.ColorRole.Window: SURFACE, QPalette.ColorRole.WindowText: TEXT,
        QPalette.ColorRole.Base: SURFACE, QPalette.ColorRole.AlternateBase: SURFACE_2,
        QPalette.ColorRole.Text: TEXT, QPalette.ColorRole.Button: SURFACE_2,
        QPalette.ColorRole.ButtonText: TEXT, QPalette.ColorRole.Highlight: "#4F46E5",
        QPalette.ColorRole.HighlightedText: "#FFFFFF", QPalette.ColorRole.ToolTipBase: SURFACE_2,
        QPalette.ColorRole.ToolTipText: TEXT, QPalette.ColorRole.PlaceholderText: MUTED,
    }.items():
        p.setColor(role, QColor(color))
    return p


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setPalette(dark_palette())
    app.setFont(QFont("Malgun Gothic", 9))
    app.setStyleSheet(STYLESHEET)
    app.setWindowIcon(QIcon(resource_path("app.ico")))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
