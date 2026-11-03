"""
코스피200 · 거래대금 상위 크롤러 GUI 앱 (PyQt6 + requests + BeautifulSoup4)

- [수집 시작]을 누르면 코스피200 지수 현재가, 일별 시세, 거래대금 상위 종목을 가져와 보여준다.
  (거래대금 상위: https://stock.naver.com/market/stock/kr/stocklist/priceTop, 100개씩 페이지를 넘기며 수집)
- 시장(전체/코스피/코스닥), 종목 수, 일별 시세 일수를 고를 수 있다.
- 상단 카드에 지수, 상승/하락 종목 수, 총 거래대금, 최대 상승 종목을 요약해 보여준다.
- 표의 머리글을 누르면 정렬되고, 종목을 더블클릭하면 네이버 종목 페이지가 열린다.
- [CSV 저장]은 현재 탭의 표를, [엑셀 저장]은 두 탭을 시트별로 한 파일에 저장한다.
- 수집은 별도 스레드(QThread)에서 실행되어 작업 중에도 창이 멈추지 않는다.

설치: pip install PyQt6 requests beautifulsoup4 openpyxl
실행: python kospi200_gui.py
"""

import sys
from datetime import datetime
from pathlib import Path

import requests
from PyQt6.QtCore import QRectF, Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QDesktopServices, QIcon, QLinearGradient, QPainter
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QStyledItemDelegate,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from kospi200_crawler import (
    MARKETS,
    fetch_daily_prices,
    fetch_index_summary,
    fetch_price_top,
    save_csv,
    save_excel,
)

RISE_COLOR = "#ff5c7a"  # 국내 증시 관례: 상승 빨강, 하락 파랑 (어두운 배경에 맞춘 네온 톤)
FALL_COLOR = "#4dabff"
FLAT_COLOR = "#94a3b8"
NUMERIC_KEYS = {"순위", "현재가", "전일비", "등락률(%)", "거래량", "거래대금(백만)", "시가총액(억)",
                "종가", "시가", "고가", "저가"}
BAR_KEYS = {"거래대금(백만)", "종가"}  # 셀 안에 막대그래프를 그릴 열

STYLE = """
QMainWindow, #central {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0b1020, stop:0.5 #111833, stop:1 #1a1036);
}
QWidget { font-family: 'Malgun Gothic'; font-size: 10pt; color: #e2e8f0; }

#header {
    border-radius: 20px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #7c3aed, stop:0.45 #db2777, stop:1 #f59e0b);
}
#title { color: white; font-size: 20pt; font-weight: 900; }
#subtitle { color: rgba(255, 255, 255, 0.85); font-size: 10pt; }
#liveBadge {
    background: rgba(0, 0, 0, 0.25); color: white; border-radius: 12px;
    padding: 4px 12px; font-weight: 800; font-size: 9pt;
}

#statCard {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.10); border-radius: 16px;
}
#statLabel { color: #94a3b8; font-size: 9pt; font-weight: 700; }
#statValue { color: white; font-size: 18pt; font-weight: 900; }
#statSub { color: #94a3b8; font-size: 9pt; font-weight: 700; }

#card {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.10); border-radius: 16px;
}
QLabel#fieldLabel { color: #a5b4fc; font-weight: 800; }

QComboBox, QSpinBox {
    background: rgba(15, 23, 42, 0.8); border: 2px solid #334155; border-radius: 10px;
    padding: 6px 10px; min-height: 22px; color: #f1f5f9;
}
QComboBox:hover, QSpinBox:hover { border-color: #7c3aed; }
QComboBox:focus, QSpinBox:focus { border-color: #db2777; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox QAbstractItemView {
    background: #1e293b; border: 1px solid #334155; color: #f1f5f9;
    selection-background-color: #7c3aed; selection-color: white;
}

QPushButton {
    border: none; border-radius: 12px; padding: 10px 20px;
    font-weight: 800; color: white; min-height: 22px;
}
#startButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #db2777); }
#startButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #ec4899); }
#csvButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #06b6d4); }
#csvButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #22d3ee); }
#excelButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #84cc16); }
#excelButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #a3e635); }
#startButton:disabled, #csvButton:disabled, #excelButton:disabled {
    background: #334155; color: #64748b;
}

QTabWidget::pane {
    border: 1px solid rgba(255, 255, 255, 0.10); border-radius: 16px;
    background: rgba(15, 23, 42, 0.75); top: -1px;
}
QTabBar::tab {
    background: transparent; color: #94a3b8; font-weight: 800;
    padding: 10px 22px; margin-right: 6px; border-bottom: 3px solid transparent;
}
QTabBar::tab:hover { color: #e2e8f0; }
QTabBar::tab:selected { color: white; border-bottom: 3px solid #db2777; }

QTableWidget {
    background: transparent; border: none; gridline-color: transparent; color: #e2e8f0;
    alternate-background-color: rgba(255, 255, 255, 0.03);
    selection-background-color: rgba(124, 58, 237, 0.35); selection-color: white;
}
QTableWidget::item { padding: 4px 8px; border-bottom: 1px solid rgba(255, 255, 255, 0.05); }
QHeaderView::section {
    background: rgba(15, 23, 42, 0.95); color: #a5b4fc; font-weight: 800;
    border: none; border-bottom: 2px solid #7c3aed; padding: 9px 8px;
}
QTableCornerButton::section { background: transparent; border: none; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #7c3aed, stop:1 #db2777);
    border-radius: 4px; min-height: 30px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }

QProgressBar {
    background: rgba(255, 255, 255, 0.08); border: none; border-radius: 5px;
    max-height: 10px; text-align: center; color: transparent;
}
QProgressBar::chunk {
    border-radius: 5px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:0.5 #db2777, stop:1 #f59e0b);
}
QStatusBar { background: transparent; color: #94a3b8; }
QToolTip { background: #1e293b; color: white; border: 1px solid #7c3aed; }
"""


def resource_path(name):
    """PyInstaller로 만든 exe에서는 임시 폴더(sys._MEIPASS)에, 그 외에는 이 파일 옆에 있는 리소스 경로."""
    base = getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)
    return str(Path(base) / name)


def save_dir():
    """저장 대화상자의 기본 폴더: exe로 실행하면 exe가 있는 폴더, 아니면 이 파일이 있는 폴더."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def to_number(text):
    """'1,392,500' / '-5.40' 같은 문자열을 정렬용 숫자로."""
    try:
        return float(str(text).replace(",", ""))
    except ValueError:
        return 0.0


def change_color(value):
    return RISE_COLOR if value > 0 else FALL_COLOR if value < 0 else FLAT_COLOR


def glow(widget, color, blur=30):
    """위젯 주변에 색이 번지는 네온 그림자를 단다."""
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, 0)
    effect.setColor(QColor(color))
    widget.setGraphicsEffect(effect)


class NumericItem(QTableWidgetItem):
    """머리글 클릭 정렬 시 문자열이 아닌 숫자 크기로 비교하는 셀."""

    def __lt__(self, other):
        return self.data(Qt.ItemDataRole.UserRole) < other.data(Qt.ItemDataRole.UserRole)


class BarDelegate(QStyledItemDelegate):
    """셀 뒤에 값 크기만큼 그라데이션 막대를 그린다 (거래대금, 종가 열).

    minimum~maximum 범위로 길이를 정한다. 종가처럼 값들이 비슷한 열은 최솟값을 바닥으로 잡아야 차이가 보인다.
    """

    def __init__(self, parent=None, minimum=0.0, maximum=1.0):
        super().__init__(parent)
        self.minimum, self.maximum = minimum, maximum

    def paint(self, painter, option, index):
        value = index.data(Qt.ItemDataRole.UserRole) or 0
        span = self.maximum - self.minimum
        if span > 0 and not option.state & QStyle.StateFlag.State_Selected:
            ratio = 0.08 + 0.92 * min(max((value - self.minimum) / span, 0.0), 1.0)
            rect = QRectF(option.rect).adjusted(4, 7, -4, -7)
            rect.setWidth(rect.width() * ratio)
            gradient = QLinearGradient(rect.topLeft(), rect.topRight())
            gradient.setColorAt(0, QColor(124, 58, 237, 150))
            gradient.setColorAt(1, QColor(219, 39, 119, 150))
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(gradient))
            painter.drawRoundedRect(rect, 5, 5)
            painter.restore()
        super().paint(painter, option, index)


class PillDelegate(QStyledItemDelegate):
    """등락률을 색깔 알약(pill) 모양 배지로 그린다."""

    def paint(self, painter, option, index):
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(124, 58, 237, 90))
        value = index.data(Qt.ItemDataRole.UserRole) or 0
        color = QColor(change_color(value))
        text = f"{'▲' if value > 0 else '▼' if value < 0 else '–'} {abs(value):.2f}%"
        width = min(option.rect.width() - 8, option.fontMetrics.horizontalAdvance(text) + 22)
        rect = QRectF(option.rect.right() - width - 6, option.rect.top() + 6,
                      width, option.rect.height() - 12)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        fill = QColor(color)
        fill.setAlpha(45)
        painter.setPen(color)
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        font = option.font
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()


class CrawlWorker(QThread):
    """지수 현재가, 일별 시세, 거래대금 상위 종목을 백그라운드에서 수집하는 스레드."""

    # list/dict 타입으로 보내면 Qt가 QVariantMap으로 바꾸면서 키(열) 순서가 가나다순으로 섞이므로 object로 전달
    summary_ready = pyqtSignal(object)
    daily_ready = pyqtSignal(object)
    stocks_ready = pyqtSignal(object)
    progress = pyqtSignal(int, str)  # 진행 단계(0~3), 메시지
    failed = pyqtSignal(str)

    def __init__(self, market, limit, days):
        super().__init__()
        self.market, self.limit, self.days = market, limit, days

    def run(self):
        try:
            self.progress.emit(0, "코스피200 지수 가져오는 중...")
            self.summary_ready.emit(fetch_index_summary())

            self.progress.emit(1, f"일별 시세 {self.days}일치 가져오는 중...")
            self.daily_ready.emit(fetch_daily_prices(self.days))

            self.progress.emit(2, f"거래대금 상위 {self.limit}개 가져오는 중...")
            stocks = fetch_price_top(self.market, self.limit,
                                     log=lambda msg: self.progress.emit(2, f"거래대금 상위 수집{msg}"))
            self.progress.emit(3, "표 그리는 중...")
            self.stocks_ready.emit(stocks)
        except (requests.RequestException, KeyError, ValueError) as e:
            self.failed.emit(f"수집 실패: {e}")


class StatCard(QFrame):
    """상단 요약 카드: 제목, 큰 값, 보조 설명. 왼쪽에 색 막대로 포인트를 준다."""

    def __init__(self, label, accent):
        super().__init__()
        self.setObjectName("statCard")
        self.accent = accent
        self.label = QLabel(label)
        self.label.setObjectName("statLabel")
        self.value = QLabel("-")
        self.value.setObjectName("statValue")
        self.sub = QLabel("수집 전")
        self.sub.setObjectName("statSub")
        bar = QFrame()
        bar.setFixedWidth(5)
        bar.setStyleSheet(f"background: {accent}; border-radius: 2px;")
        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(self.label)
        text.addWidget(self.value)
        text.addWidget(self.sub)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(12)
        layout.addWidget(bar)
        layout.addLayout(text, 1)
        glow(self, QColor(accent).darker(150), 26)

    def set(self, value, sub, color=None):
        self.value.setText(value)
        self.value.setStyleSheet(f"color: {color};" if color else "")
        self.sub.setText(sub)
        self.sub.setStyleSheet(f"color: {color};" if color else "")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("코스피200 · 거래대금 상위 크롤러")
        self.resize(1280, 900)
        self.setStyleSheet(STYLE)

        self.stocks, self.daily = [], []
        self.worker = None

        # 헤더: 제목 + LIVE 배지
        title = QLabel("📊  KOSPI 200 · 거래대금 TOP")
        title.setObjectName("title")
        subtitle = QLabel("네이버페이 증권 실시간 데이터를 모아 보고, CSV · 엑셀로 저장하세요")
        subtitle.setObjectName("subtitle")
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        self.live_badge = QLabel("● 대기 중")
        self.live_badge.setObjectName("liveBadge")

        header_frame = QFrame()
        header_frame.setObjectName("header")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(26, 20, 26, 20)
        header_layout.addLayout(title_box, 1)
        header_layout.addWidget(self.live_badge, 0, Qt.AlignmentFlag.AlignTop)
        glow(header_frame, "#db2777", 45)

        # 요약 카드 4장
        self.index_card = StatCard("코스피 200", "#a855f7")
        self.breadth_card = StatCard("상승 · 하락 종목", "#ff5c7a")
        self.value_card = StatCard("총 거래대금", "#22d3ee")
        self.best_card = StatCard("최대 상승 종목", "#f59e0b")
        stats = QGridLayout()
        stats.setSpacing(14)
        for i, card in enumerate((self.index_card, self.breadth_card, self.value_card, self.best_card)):
            stats.addWidget(card, 0, i)

        # 옵션 카드: 시장, 종목 수, 일별 시세 일수, 버튼
        self.market_combo = QComboBox()
        for code, name in MARKETS.items():
            self.market_combo.addItem(name, code)

        self.limit_spin = self.make_spin(10, 1000, 200, 10, " 개")
        self.days_spin = self.make_spin(5, 500, 20, 5, " 일")

        self.start_button = self.make_button("▶  수집 시작", "startButton", self.start_crawl)
        self.save_button = self.make_button("📄  CSV 저장", "csvButton", self.save_results)
        self.excel_button = self.make_button("📗  엑셀 저장", "excelButton", self.save_excel_results)
        for button in (self.save_button, self.excel_button):
            button.setEnabled(False)
        glow(self.start_button, "#db2777", 24)

        option_card = QFrame()
        option_card.setObjectName("card")
        top = QHBoxLayout(option_card)
        top.setContentsMargins(18, 12, 18, 12)
        top.setSpacing(8)
        for label, widget in (("시장", self.market_combo), ("거래대금 상위", self.limit_spin),
                              ("일별 시세", self.days_spin)):
            field = QLabel(label)
            field.setObjectName("fieldLabel")
            top.addWidget(field)
            top.addWidget(widget)
            top.addSpacing(12)
        top.addStretch(1)
        top.addWidget(self.start_button)
        top.addSpacing(4)
        top.addWidget(self.save_button)
        top.addWidget(self.excel_button)

        # 탭: 거래대금 상위 / 일별 시세
        self.stock_table = self.make_table()
        self.stock_table.cellDoubleClicked.connect(self.open_stock_page)
        self.daily_table = self.make_table()
        self.tabs = QTabWidget()
        self.tabs.addTab(self.stock_table, "💰  거래대금 상위")
        self.tabs.addTab(self.daily_table, "📈  코스피200 일별 시세")

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(3)

        layout = QVBoxLayout()
        layout.setContentsMargins(22, 22, 22, 10)
        layout.setSpacing(16)
        layout.addWidget(header_frame)
        layout.addLayout(stats)
        layout.addWidget(option_card)
        layout.addWidget(self.tabs, 1)
        layout.addWidget(self.progress_bar)

        central = QWidget()
        central.setObjectName("central")
        central.setLayout(layout)
        self.setCentralWidget(central)
        self.statusBar().showMessage("옵션을 고르고 [수집 시작]을 누르세요. 종목을 더블클릭하면 네이버 종목 페이지가 열립니다.")

    def make_button(self, text, name, slot):
        button = QPushButton(text)
        button.setObjectName(name)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(slot)
        return button

    def make_spin(self, minimum, maximum, value, step, suffix):
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        spin.setSingleStep(step)
        spin.setSuffix(suffix)
        spin.setMinimumWidth(90)
        spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)  # 화살표 없이 깔끔하게 (입력·마우스 휠로 변경)
        spin.setToolTip("숫자를 입력하거나 마우스 휠로 바꾸세요")
        return spin

    def make_table(self):
        table = QTableWidget(0, 0)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(38)
        return table

    def fill_table(self, table, rows):
        """dict 리스트를 표에 채운다. 숫자 열은 오른쪽 정렬·숫자 정렬, 막대·배지 장식을 붙인다."""
        table.setSortingEnabled(False)  # 채우는 동안 정렬이 끼어들지 않도록
        table.clear()
        table.setRowCount(0)
        if not rows:
            return
        keys = list(rows[0].keys())
        table.setColumnCount(len(keys))
        table.setHorizontalHeaderLabels(keys)
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            color = change_color(to_number(row.get("전일비", 0)))
            for c, key in enumerate(keys):
                text = str(row[key])
                if key in NUMERIC_KEYS:
                    item = NumericItem(text)
                    item.setData(Qt.ItemDataRole.UserRole, to_number(text))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    if key == "전일비":
                        item.setForeground(QColor(color))
                    elif key == "순위" and to_number(text) <= 3:
                        item.setForeground(QColor(("#fbbf24", "#e2e8f0", "#f59e0b")[int(to_number(text)) - 1]))
                else:
                    item = QTableWidgetItem(text)
                if key == "종목명":
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    item.setForeground(QColor("#ffffff"))
                elif key == "시장":
                    item.setForeground(QColor("#c4b5fd" if text == "코스피" else "#67e8f9"))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                elif key in ("종목코드", "날짜"):
                    item.setForeground(QColor("#94a3b8"))
                table.setItem(r, c, item)

        for c, key in enumerate(keys):
            table.setItemDelegateForColumn(c, None)
            if key == "등락률(%)":
                table.setItemDelegateForColumn(c, PillDelegate(table))
            elif key in BAR_KEYS:
                values = [to_number(row[key]) for row in rows]
                low = 0.0 if key == "거래대금(백만)" else min(values) * 0.995
                table.setItemDelegateForColumn(c, BarDelegate(table, low, max(values)))

        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        for key in ("종목명", "거래대금(백만)", "종가"):
            if key in keys:
                header.setSectionResizeMode(keys.index(key), QHeaderView.ResizeMode.Stretch)
        if "등락률(%)" in keys:
            header.setSectionResizeMode(keys.index("등락률(%)"), QHeaderView.ResizeMode.Fixed)
            table.setColumnWidth(keys.index("등락률(%)"), 120)
        table.setSortingEnabled(True)

    def start_crawl(self):
        if self.worker and self.worker.isRunning():
            return
        self.set_running(True)
        self.progress_bar.setValue(0)

        self.worker = CrawlWorker(self.market_combo.currentData(), self.limit_spin.value(),
                                  self.days_spin.value())
        self.worker.summary_ready.connect(self.show_summary)
        self.worker.daily_ready.connect(self.show_daily)
        self.worker.stocks_ready.connect(self.show_stocks)
        self.worker.progress.connect(self.on_progress)
        self.worker.failed.connect(self.on_failed)
        self.worker.finished.connect(lambda: self.set_running(False))
        self.worker.start()

    def set_running(self, running):
        for widget in (self.start_button, self.market_combo, self.limit_spin, self.days_spin):
            widget.setEnabled(not running)
        has_data = not running and bool(self.stocks or self.daily)
        self.save_button.setEnabled(has_data)
        self.excel_button.setEnabled(has_data)
        self.live_badge.setText("● 수집 중..." if running else "● 업데이트 완료" if has_data else "● 대기 중")

    def on_progress(self, step, message):
        self.progress_bar.setValue(step)
        self.statusBar().showMessage(message.replace("  ", " "))

    def on_failed(self, message):
        self.statusBar().showMessage(message)
        QMessageBox.warning(self, "오류", message)

    def show_summary(self, s):
        change = to_number(s["전일비"])
        arrow = "▲" if change > 0 else "▼" if change < 0 else "–"
        self.index_card.label.setText(f"{s['지수명']} · {s['기준시각'][11:16]} {s['장상태']}")
        self.index_card.set(s["현재가"], f"{arrow} {s['전일비'].lstrip('-')}  ({s['등락률(%)']}%)",
                            change_color(change))

    def show_daily(self, rows):
        self.daily = rows
        self.fill_table(self.daily_table, rows)

    def show_stocks(self, rows):
        self.stocks = rows
        self.fill_table(self.stock_table, rows)
        self.tabs.setTabText(0, f"💰  거래대금 상위 ({len(rows)})")

        changes = [to_number(r["등락률(%)"]) for r in rows]
        up, down = sum(c > 0 for c in changes), sum(c < 0 for c in changes)
        self.breadth_card.set(f"{up} : {down}", f"보합 {len(rows) - up - down} · 상위 {len(rows)}종목 기준",
                              change_color(up - down))
        total = sum(to_number(r["거래대금(백만)"]) for r in rows) / 1_000_000  # 백만원 -> 조원
        self.value_card.set(f"{total:,.1f}조", f"상위 {len(rows)}종목 합계 (원)")
        best = max(rows, key=lambda r: to_number(r["등락률(%)"]))
        self.best_card.set(best["종목명"], f"▲ {best['등락률(%)']}%  ·  {best['현재가']}원", RISE_COLOR)

        self.statusBar().showMessage(f"완료: 거래대금 상위 {len(rows)}개, 일별 시세 {len(self.daily)}일 "
                                     f"({datetime.now():%H:%M:%S} 기준)")

    def open_stock_page(self, row, _col):
        """종목을 더블클릭하면 네이버페이 증권 종목 페이지를 연다."""
        for c in range(self.stock_table.columnCount()):
            if self.stock_table.horizontalHeaderItem(c).text() == "종목코드":
                code = self.stock_table.item(row, c).text()
                QDesktopServices.openUrl(QUrl(f"https://stock.naver.com/domestic/stock/{code}"))
                return

    def save_results(self):
        if self.tabs.currentIndex() == 0:
            rows, name = self.stocks, f"price_top_{self.market_combo.currentData()}"
        else:
            rows, name = self.daily, "kospi200_daily"
        if not rows:
            QMessageBox.information(self, "알림", "저장할 데이터가 없습니다.")
            return
        default = str(save_dir() / f"{name}_{datetime.now():%Y%m%d}.csv")
        filename, _ = QFileDialog.getSaveFileName(self, "CSV 저장", default, "CSV 파일 (*.csv)")
        if not filename:
            return
        try:
            save_csv(rows, filename)
        except PermissionError:
            QMessageBox.warning(self, "알림", "파일이 다른 프로그램(엑셀 등)에서 열려 있어 저장할 수 없습니다.")
            return
        self.statusBar().showMessage(f"{len(rows)}건을 {filename} 에 저장했습니다.")

    def save_excel_results(self):
        """두 탭(거래대금 상위, 일별 시세)을 시트별로 엑셀 파일 하나에 저장한다."""
        if not (self.stocks or self.daily):
            return
        default = str(save_dir() / f"kospi200_{self.market_combo.currentData()}_{datetime.now():%Y%m%d}.xlsx")
        filename, _ = QFileDialog.getSaveFileName(self, "엑셀 저장", default, "엑셀 파일 (*.xlsx)")
        if not filename:
            return
        try:
            save_excel({"거래대금 상위": self.stocks, "코스피200 일별 시세": self.daily}, filename)
        except ImportError:
            QMessageBox.warning(self, "알림", "엑셀 저장에는 openpyxl이 필요합니다.\npip install openpyxl")
            return
        except PermissionError:
            QMessageBox.warning(self, "알림", "파일이 다른 프로그램(엑셀 등)에서 열려 있어 저장할 수 없습니다.")
            return
        self.statusBar().showMessage(f"거래대금 상위 {len(self.stocks)}개 · 일별 시세 {len(self.daily)}일을 "
                                     f"{filename} 에 저장했습니다.")

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.wait()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon(resource_path("app.ico")))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
