"""
네이버 뉴스 크롤러 GUI 앱 (PyQt6 + requests + BeautifulSoup4)

- 검색어와 검색 방식(통합검색 / 뉴스탭)을 고르고 [크롤링 시작]을 누르면
  검색 결과의 네이버뉴스 기사들을 차례로 가져와 표에 보여준다.
- 표에서 기사를 선택하면 아래에 본문 전체가 표시된다.
- [CSV 저장]으로 결과를 파일로 저장할 수 있다.
- 크롤링은 별도 스레드(QThread)에서 실행되어 작업 중에도 창이 멈추지 않는다.

설치: pip install PyQt6 requests beautifulsoup4
실행: python naver_news_gui.py
"""

import html
import os
import sys
import time
from urllib.parse import quote

import requests
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from naver_news_crawler import collect_article_links, parse_article, save_csv, save_excel

# 검색 방식별 네이버 검색 URL (where=nexearch: 통합검색, where=news: 뉴스탭)
SEARCH_TYPES = {
    "통합검색": "https://search.naver.com/search.naver?where=nexearch&sm=top_hty&fbm=0&ie=utf8&query={}",
    "뉴스 탭": "https://search.naver.com/search.naver?where=news&ie=utf8&query={}",
}


def resource_path(name):
    """PyInstaller로 만든 exe에서는 임시 폴더(sys._MEIPASS)에, 그 외에는 이 파일 옆에 있는 리소스 경로."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)

# 앱 전체 스타일시트 (네이버 그린 계열 테마)
STYLE = """
QMainWindow, #central { background: #f2f5f9; }
QWidget { font-family: 'Malgun Gothic'; font-size: 10pt; color: #1f2937; }

#header {
    border-radius: 16px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #03c75a, stop:0.55 #00b894, stop:1 #0984e3);
}
#logo {
    background: white; color: #03c75a; border-radius: 12px;
    font-size: 22pt; font-weight: 900;
}
#title { color: white; font-size: 18pt; font-weight: 800; }
#subtitle { color: rgba(255, 255, 255, 0.85); font-size: 10pt; }
#countBadge {
    background: rgba(255, 255, 255, 0.22); color: white;
    border: 1px solid rgba(255, 255, 255, 0.5); border-radius: 15px;
    padding: 4px 14px; font-weight: 700;
}

#card { background: white; border-radius: 14px; }
#cardTitle { font-size: 11pt; font-weight: 800; color: #111827; }

QLineEdit, QComboBox {
    background: #f8fafc; border: 2px solid #e2e8f0; border-radius: 10px;
    padding: 7px 12px; min-height: 22px;
}
QLineEdit:focus, QComboBox:focus { border-color: #03c75a; background: white; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox QAbstractItemView {
    background: white; border: 1px solid #e2e8f0; border-radius: 8px;
    selection-background-color: #e6f9ee; selection-color: #03a74c;
}

QPushButton {
    border: none; border-radius: 10px; padding: 9px 18px;
    font-weight: 700; color: white; min-height: 22px;
}
#startButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #03c75a, stop:1 #00b894); }
#startButton:hover { background: #02b351; }
#startButton:pressed { background: #029a46; }
#stopButton { background: #ff6b6b; }
#stopButton:hover { background: #fa5252; }
#csvButton { background: #4c6ef5; }
#csvButton:hover { background: #3b5bdb; }
#excelButton { background: #1d6f42; }
#excelButton:hover { background: #185c37; }
#startButton:disabled, #stopButton:disabled, #csvButton:disabled, #excelButton:disabled {
    background: #cbd5e1; color: #f1f5f9;
}

QTableWidget {
    background: white; border: none; gridline-color: transparent;
    alternate-background-color: #f8fbff;
    selection-background-color: #e6f9ee; selection-color: #065f46;
}
QTableWidget::item { padding: 6px 10px; border-bottom: 1px solid #f1f5f9; }
QHeaderView::section {
    background: #f8fafc; color: #64748b; font-weight: 700;
    border: none; border-bottom: 2px solid #e2e8f0; padding: 8px 10px;
}

QTextBrowser { background: white; border: none; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #cbd5e1; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #94a3b8; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QSplitter::handle { background: transparent; height: 12px; }

QProgressBar {
    background: #e2e8f0; border: none; border-radius: 5px;
    max-height: 10px; text-align: center; color: transparent;
}
QProgressBar::chunk {
    border-radius: 5px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #03c75a, stop:1 #0984e3);
}

QStatusBar { background: #f2f5f9; color: #64748b; }
"""


class CrawlWorker(QThread):
    """검색 결과 수집과 기사 파싱을 백그라운드에서 수행하는 스레드."""

    links_found = pyqtSignal(int)  # 발견한 기사 링크 수
    article_parsed = pyqtSignal(dict)  # 기사 1건 파싱 완료
    progress = pyqtSignal(int)  # 처리한 링크 수
    failed = pyqtSignal(str)  # 오류 메시지

    def __init__(self, search_url):
        super().__init__()
        self.search_url = search_url
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            links = collect_article_links(self.search_url)
        except requests.RequestException as e:
            self.failed.emit(f"검색 페이지 요청 실패: {e}")
            return

        self.links_found.emit(len(links))
        for i, link in enumerate(links, 1):
            if self._stop:
                break
            try:
                self.article_parsed.emit(parse_article(link))
            except requests.RequestException as e:
                self.failed.emit(f"기사 요청 실패: {link} ({e})")
            self.progress.emit(i)
            time.sleep(0.5)  # 서버 부담을 줄이기 위한 요청 간격


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("네이버 뉴스 크롤러")
        self.resize(1100, 800)
        self.setStyleSheet(STYLE)

        self.articles = []
        self.worker = None

        # 헤더: 로고, 제목, 수집 건수 배지
        logo = QLabel("N")
        logo.setObjectName("logo")
        logo.setFixedSize(52, 52)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("네이버 뉴스 크롤러")
        title.setObjectName("title")
        subtitle = QLabel("검색어로 네이버 뉴스를 모아 보고, CSV · 엑셀로 저장하세요")
        subtitle.setObjectName("subtitle")
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        self.count_badge = QLabel("수집 0건")
        self.count_badge.setObjectName("countBadge")

        header_frame = QFrame()
        header_frame.setObjectName("header")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(22, 18, 22, 18)
        header_layout.setSpacing(16)
        header_layout.addWidget(logo)
        header_layout.addLayout(title_box, 1)
        header_layout.addWidget(self.count_badge)

        # 검색 카드: 검색어, 검색 방식, 버튼
        self.keyword_edit = QLineEdit("반도체")
        self.keyword_edit.setPlaceholderText("🔍  검색어를 입력하세요")
        self.keyword_edit.returnPressed.connect(self.start_crawl)

        self.type_combo = QComboBox()
        self.type_combo.addItems(SEARCH_TYPES.keys())
        self.type_combo.setMinimumWidth(110)

        self.start_button = self.make_button("▶  크롤링 시작", "startButton", self.start_crawl)
        self.stop_button = self.make_button("■  중지", "stopButton", self.stop_crawl)
        self.save_button = self.make_button("CSV 저장", "csvButton", self.save_results)
        self.excel_button = self.make_button("엑셀 저장", "excelButton", self.save_excel_results)
        for button in (self.stop_button, self.save_button, self.excel_button):
            button.setEnabled(False)

        search_card = self.make_card()
        top = QHBoxLayout(search_card)
        top.setContentsMargins(16, 14, 16, 14)
        top.setSpacing(10)
        top.addWidget(self.keyword_edit, 1)
        top.addWidget(self.type_combo)
        top.addWidget(self.start_button)
        top.addWidget(self.stop_button)
        top.addSpacing(8)
        top.addWidget(self.save_button)
        top.addWidget(self.excel_button)

        # 기사 목록 카드
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["제목", "언론사", "작성일"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.table.itemSelectionChanged.connect(self.show_article)

        list_card = self.make_card("📰  기사 목록", self.table)

        # 본문 카드
        self.body_view = QTextBrowser()
        self.body_view.setOpenExternalLinks(True)
        self.body_view.setPlaceholderText("목록에서 기사를 선택하면 본문이 여기에 표시됩니다.")

        body_card = self.make_card("📄  기사 본문", self.body_view)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(list_card)
        splitter.addWidget(body_card)
        splitter.setSizes([330, 400])

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 10)
        layout.setSpacing(14)
        layout.addWidget(header_frame)
        layout.addWidget(search_card)
        layout.addWidget(splitter, 1)
        layout.addWidget(self.progress_bar)

        central = QWidget()
        central.setObjectName("central")
        central.setLayout(layout)
        self.setCentralWidget(central)
        self.statusBar().showMessage("검색어를 입력하고 [크롤링 시작]을 누르세요.")

    def make_button(self, text, name, slot):
        button = QPushButton(text)
        button.setObjectName(name)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(slot)
        return button

    def make_card(self, title=None, content=None):
        """흰색 둥근 카드(그림자 포함)를 만들고, 제목과 내용 위젯이 있으면 넣는다."""
        card = QFrame()
        card.setObjectName("card")
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(15, 23, 42, 28))
        card.setGraphicsEffect(shadow)
        if content is not None:
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 14, 16, 16)
            card_layout.setSpacing(10)
            label = QLabel(title)
            label.setObjectName("cardTitle")
            card_layout.addWidget(label)
            card_layout.addWidget(content)
        return card

    def start_crawl(self):
        keyword = self.keyword_edit.text().strip()
        if not keyword:
            QMessageBox.warning(self, "알림", "검색어를 입력하세요.")
            return
        if self.worker and self.worker.isRunning():
            return

        search_url = SEARCH_TYPES[self.type_combo.currentText()].format(quote(keyword))

        self.articles.clear()
        self.table.setRowCount(0)
        self.body_view.clear()
        self.count_badge.setText("수집 0건")
        self.progress_bar.setValue(0)
        self.set_running(True)
        self.statusBar().showMessage(f"'{keyword}' 검색 결과를 가져오는 중...")

        self.worker = CrawlWorker(search_url)
        self.worker.links_found.connect(self.on_links_found)
        self.worker.article_parsed.connect(self.add_article)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.failed.connect(lambda msg: self.statusBar().showMessage(msg))
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def stop_crawl(self):
        if self.worker:
            self.worker.stop()
            self.statusBar().showMessage("중지하는 중...")

    def set_running(self, running):
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        self.keyword_edit.setEnabled(not running)
        self.type_combo.setEnabled(not running)
        self.save_button.setEnabled(not running and bool(self.articles))
        self.excel_button.setEnabled(not running and bool(self.articles))

    def on_links_found(self, count):
        self.progress_bar.setMaximum(max(count, 1))
        self.statusBar().showMessage(f"네이버뉴스 기사 링크 {count}개 발견, 본문 수집 중...")

    def add_article(self, article):
        self.articles.append(article)
        row = self.table.rowCount()
        self.table.insertRow(row)
        for col, key in enumerate(["title", "press", "date"]):
            item = QTableWidgetItem(article[key])
            item.setToolTip(article[key])
            if key == "press":
                item.setForeground(QColor("#03a74c"))
            elif key == "date":
                item.setForeground(QColor("#94a3b8"))
            self.table.setItem(row, col, item)
        self.count_badge.setText(f"수집 {len(self.articles)}건")

    def show_article(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        article = self.articles[rows[0].row()]
        url = html.escape(article["url"], quote=True)
        paragraphs = "".join(
            f'<p style="margin:0 0 12px 0; line-height:170%;">{html.escape(line)}</p>'
            for line in article["content"].splitlines()
        )
        self.body_view.setHtml(f"""
            <div style="font-family:'Malgun Gothic'; color:#1f2937;">
              <p style="font-size:17pt; font-weight:800; color:#0f172a; margin:4px 0 10px 0;">
                {html.escape(article['title'])}</p>
              <p style="margin:0 0 6px 0;">
                <span style="background:#e6f9ee; color:#03a74c; font-weight:700;">
                  &nbsp;{html.escape(article['press'])}&nbsp;</span>
                &nbsp;<span style="color:#94a3b8;">🕒 {html.escape(article['date'])}</span></p>
              <p style="margin:0 0 14px 0;">
                <a href="{url}" style="color:#4c6ef5; text-decoration:none;">🔗 원문 보기</a></p>
              <hr style="color:#e2e8f0;">
              <div style="font-size:11pt;">{paragraphs}</div>
            </div>""")

    def on_finished(self):
        self.set_running(False)
        self.statusBar().showMessage(f"완료: 기사 {len(self.articles)}개 수집")

    def save_results(self):
        if not self.articles:
            return
        default_name = f"naver_news_{self.keyword_edit.text().strip()}.csv"
        filename, _ = QFileDialog.getSaveFileName(self, "CSV 저장", default_name, "CSV 파일 (*.csv)")
        if not filename:
            return
        save_csv(self.articles, filename)
        self.statusBar().showMessage(f"{len(self.articles)}개 기사를 {filename} 에 저장했습니다.")

    def save_excel_results(self):
        if not self.articles:
            return
        default_name = f"naver_news_{self.keyword_edit.text().strip()}.xlsx"
        filename, _ = QFileDialog.getSaveFileName(self, "엑셀 저장", default_name, "엑셀 파일 (*.xlsx)")
        if not filename:
            return
        try:
            save_excel(self.articles, filename)
        except ImportError:
            QMessageBox.warning(self, "알림", "엑셀 저장에는 openpyxl이 필요합니다.\npip install openpyxl")
            return
        except PermissionError:
            QMessageBox.warning(self, "알림", "파일이 다른 프로그램(엑셀 등)에서 열려 있어 저장할 수 없습니다.")
            return
        self.statusBar().showMessage(f"{len(self.articles)}개 기사를 {filename} 에 저장했습니다.")

    def closeEvent(self, event):
        # 창을 닫을 때 실행 중인 스레드를 정리
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # 운영체제와 상관없이 스타일시트가 일관되게 적용되도록
    app.setWindowIcon(QIcon(resource_path("app.ico")))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
