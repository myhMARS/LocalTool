import base64
import re

from PyQt6.QtCore import QSize, Qt, QTimer, QUrl
from PyQt6.QtGui import QColor, QDesktopServices
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMenu, QMessageBox, QPushButton, QSizePolicy, QSplitter,
    QStackedWidget, QStatusBar, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from localtool.mailer.controller import MailController
from localtool.mailer.dialogs import ComposeDialog, SettingsDialog
from localtool.mailer.style import avatar_color, STYLE
from localtool.mailer.widgets import AvatarWidget, EmailItemWidget, SenderFolderWidget, SpinnerWidget
from localtool.mailer.workers import FOLDER_INBOX, FOLDER_SENT


class _MailWebPage(QWebEnginePage):
    """Custom page that opens external links in the system browser."""
    def acceptNavigationRequest(self, url: QUrl, nav_type, is_main_frame):
        if nav_type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
            QDesktopServices.openUrl(url)
            return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)


class MainWindow(QMainWindow):
    """Pure View: UI assembly and event binding. All business logic is in MailController."""

    STREAM_BATCH = 60

    def __init__(self, controller: MailController):
        super().__init__()
        self._ctrl = controller
        self._compose_dlg: ComposeDialog | None = None

        self._stream_queue: list = []
        self._stream_offset = 0
        self._fix_timer = QTimer(self)
        self._fix_timer.setSingleShot(True)
        self._fix_timer.timeout.connect(self._fix_item_widths)

        self.setWindowTitle("Email")
        self.setMinimumSize(960, 580)
        self.resize(1140, 740)
        self.setStyleSheet(STYLE)

        self._setup_ui()
        self._bind_controller()

    # ==================================================================
    # UI construction
    # ==================================================================

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._build_toolbar(root)
        self._build_body(root)
        self._build_statusbar()

    def _build_toolbar(self, root: QVBoxLayout):
        bar = QWidget()
        bar.setObjectName("toolbar")
        self._toolbar_layout = QHBoxLayout(bar)
        self._toolbar_layout.setContentsMargins(24, 14, 24, 14)
        self._toolbar_layout.setSpacing(12)

        brand = QLabel("Email")
        brand.setObjectName("toolbar_title")
        self._toolbar_layout.addWidget(brand)

        self._account_widget = None
        self._build_account_area()

        self._toolbar_layout.addStretch()

        compose_btn = QPushButton("Compose")
        compose_btn.setObjectName("primary_btn")
        compose_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        compose_btn.setFixedHeight(34)
        compose_btn.clicked.connect(self._on_compose)
        self._toolbar_layout.addWidget(compose_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("tool_btn")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setFixedHeight(34)
        refresh_btn.clicked.connect(self._ctrl.refresh)
        self._toolbar_layout.addWidget(refresh_btn)

        settings_btn = QPushButton("Settings")
        settings_btn.setObjectName("tool_btn")
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.setFixedHeight(34)
        settings_btn.clicked.connect(self._on_settings)
        self._toolbar_layout.addWidget(settings_btn)

        root.addWidget(bar)

    def _build_account_area(self):
        """Create or recreate the account badge / switcher after brand label."""
        if self._account_widget is not None:
            self._toolbar_layout.removeWidget(self._account_widget)
            self._account_widget.deleteLater()
            self._account_widget = None

        accounts = self._ctrl.cfg.accounts
        if not accounts:
            return

        if len(accounts) > 1:
            btn = QPushButton()
            btn.setFixedHeight(34)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton {"
                "  background: #F7F8FA;"
                "  border: 1px solid #E8EAED;"
                "  border-radius: 17px;"
                "  padding: 5px 14px 5px 16px;"
                "  font-size: 12.5px;"
                "  color: #1F2937;"
                "  font-weight: 600;"
                "  text-align: left;"
                "}"
                "QPushButton:hover { background: #F0F1F4; border-color: #D1D5DB; }"
                "QPushButton:pressed { background: #E8EAEE; }"
            )
            self.account_switcher = btn
            self._update_account_btn_text()
            btn.clicked.connect(self._show_account_menu)
            self._account_widget = btn
        else:
            addr = accounts[self._ctrl.active_idx].email
            if addr:
                badge = QLabel(addr)
                badge.setObjectName("toolbar_subtitle")
                badge.setStyleSheet(
                    "font-size: 11px; color: #9CA3AF; font-weight: 500; "
                    "background: #F3F4F6; border-radius: 6px; padding: 2px 10px;"
                )
                self._account_widget = badge

        if self._account_widget is not None:
            self._toolbar_layout.insertWidget(1, self._account_widget)

    def _build_body(self, root: QVBoxLayout):
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        splitter.addWidget(self._build_list_panel())
        splitter.addWidget(self._build_detail_panel())

        splitter.setSizes([380, 760])
        splitter.setStyleSheet(
            "QSplitter::handle { background: #E5E7EB; } "
            "QSplitter::handle:horizontal { width: 1px; }"
        )
        root.addWidget(splitter, 1)

    def _build_list_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setStyleSheet(
            "background: #F9FAFB; border-bottom: 1px solid #E5E7EB;"
        )
        hv = QVBoxLayout(header)
        hv.setContentsMargins(16, 10, 16, 8)
        hv.setSpacing(8)

        # ── row 1: folder tabs + filter pill ──
        row1 = QHBoxLayout()
        row1.setSpacing(10)

        folder_tabs = QWidget()
        folder_tabs.setStyleSheet(
            "QWidget#folder_tabs { background: #F3F4F6; border-radius: 10px; }"
            "QWidget#folder_tabs > QPushButton { background: transparent; border: none; "
            "border-radius: 8px; padding: 5px 14px; color: #6B7280; font-size: 12px; "
            "font-weight: 700; }"
            "QWidget#folder_tabs > QPushButton:hover { color: #4D6BFE; }"
            "QWidget#folder_tabs > QPushButton#folder_active { background: #FFFFFF; "
            "color: #4D6BFE; }"
        )
        folder_tabs.setObjectName("folder_tabs")
        ft_layout = QHBoxLayout(folder_tabs)
        ft_layout.setContentsMargins(3, 3, 3, 3)
        ft_layout.setSpacing(0)

        self.inbox_tab = QPushButton("Inbox")
        self.inbox_tab.setObjectName("folder_active")
        self.inbox_tab.setCursor(Qt.CursorShape.PointingHandCursor)
        self.inbox_tab.clicked.connect(lambda: self._ctrl.switch_folder(FOLDER_INBOX))
        ft_layout.addWidget(self.inbox_tab)

        self.sent_tab = QPushButton("Sent")
        self.sent_tab.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sent_tab.clicked.connect(lambda: self._ctrl.switch_folder(FOLDER_SENT))
        ft_layout.addWidget(self.sent_tab)

        row1.addWidget(folder_tabs)

        self.group_btn = QPushButton("Group")
        self.group_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.group_btn.setStyleSheet(
            "QPushButton { background: transparent; border: 1px solid #E5E7EB; "
            "border-radius: 8px; padding: 4px 12px; color: #6B7280; font-size: 11px; "
            "font-weight: 600; }"
            "QPushButton:hover { border-color: #4D6BFE; color: #4D6BFE; }"
            "QPushButton#group_active { background: #EEF2FF; border-color: #4D6BFE; "
            "color: #4D6BFE; }"
        )
        self.group_btn.clicked.connect(self._ctrl.toggle_grouped)
        row1.addWidget(self.group_btn)

        row1.addStretch()

        pill = QWidget()
        pill.setStyleSheet(
            "QWidget#filter_pill { background: #F3F4F6; border-radius: 12px; }"
            "QWidget#filter_pill > QPushButton { background: transparent; border: none; "
            "border-radius: 10px; padding: 4px 12px; color: #6B7280; font-size: 11px; "
            "font-weight: 700; }"
            "QWidget#filter_pill > QPushButton:hover { color: #4D6BFE; }"
            "QWidget#filter_pill > QPushButton#filter_active { background: #FFFFFF; "
            "color: #4D6BFE; }"
        )
        pill.setObjectName("filter_pill")
        pill_layout = QHBoxLayout(pill)
        pill_layout.setContentsMargins(3, 3, 3, 3)
        pill_layout.setSpacing(0)

        self.filter_btn = QPushButton("All")
        self.filter_btn.setObjectName("filter_active")
        self.filter_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.filter_btn.clicked.connect(self._ctrl.toggle_filter)
        pill_layout.addWidget(self.filter_btn)

        sep = QWidget()
        sep.setFixedSize(1, 14)
        sep.setStyleSheet("background: #D1D5DB; border: none; border-radius: 0px;")
        pill_layout.addWidget(sep, 0, Qt.AlignmentFlag.AlignVCenter)

        self._spinner = SpinnerWidget(14)
        self.list_count = QLabel("")
        self.list_count.setStyleSheet(
            "font-size: 11px; color: #6B7280; font-weight: 600; padding: 0px 8px; border: none;"
        )
        self.list_count.setMinimumWidth(28)
        spinner_wrap = QWidget()
        spinner_wrap.setStyleSheet("background: transparent;")
        sw_layout = QHBoxLayout(spinner_wrap)
        sw_layout.setContentsMargins(0, 0, 0, 0)
        sw_layout.setSpacing(0)
        sw_layout.addStretch()
        sw_layout.addWidget(self._spinner)
        sw_layout.addStretch()
        self._count_stack = QStackedWidget()
        self._count_stack.setStyleSheet("background: transparent;")
        self._count_stack.addWidget(spinner_wrap)
        self._count_stack.addWidget(self.list_count)
        self._count_stack.setCurrentIndex(1)
        pill_layout.addWidget(self._count_stack, 0, Qt.AlignmentFlag.AlignVCenter)

        pill.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        row1.addWidget(pill, 0, Qt.AlignmentFlag.AlignVCenter)
        self._filter_pill = pill
        hv.addLayout(row1)

        # ── row 2: search bar ──
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMaximumHeight(30)
        self.search_input.setStyleSheet(
            "QLineEdit { background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px; "
            "padding: 5px 10px; font-size: 12px; color: #111827; }"
            "QLineEdit:focus { border: 1.5px solid #4D6BFE; }"
        )
        self.search_input.textChanged.connect(self._ctrl.set_search)
        hv.addWidget(self.search_input)

        layout.addWidget(header)

        # ── flat list view ──
        self.email_list = QListWidget()
        self.email_list.setFrameShape(QFrame.Shape.NoFrame)
        self.email_list.setSpacing(0)
        self.email_list.setIconSize(QSize(40, 40))
        self.email_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.email_list.currentRowChanged.connect(self._on_list_row_changed)
        self.email_list.setCursor(Qt.CursorShape.PointingHandCursor)
        self.email_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.email_list.installEventFilter(self)

        # ── grouped tree view ──
        self.email_tree = QTreeWidget()
        self.email_tree.setFrameShape(QFrame.Shape.NoFrame)
        self.email_tree.setHeaderHidden(True)
        self.email_tree.setIndentation(22)
        self.email_tree.setIconSize(QSize(40, 40))
        self.email_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.email_tree.setCursor(Qt.CursorShape.PointingHandCursor)
        self.email_tree.setVerticalScrollMode(QTreeWidget.ScrollMode.ScrollPerPixel)
        self.email_tree.setAnimated(False)
        self.email_tree.setStyleSheet(
            "QTreeWidget { border: none; outline: none; }"
            "QTreeWidget::item { border: none; }"
            "QTreeWidget::item:selected { background: transparent; }"
        )
        self.email_tree.itemClicked.connect(self._on_tree_clicked)
        self.email_tree.installEventFilter(self)

        self._list_stack = QStackedWidget()
        self._list_stack.addWidget(self.email_list)
        self._list_stack.addWidget(self.email_tree)
        layout.addWidget(self._list_stack)

        return panel

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if event.type() == QEvent.Type.Resize:
            if obj is self.email_list or obj is self.email_tree:
                self._fix_timer.start(80)
        return super().eventFilter(obj, event)

    def _build_detail_panel(self) -> QStackedWidget:
        self.detail_stack = QStackedWidget()

        # ── placeholder ──
        placeholder = QWidget()
        placeholder.setStyleSheet("background: #F9FAFB;")
        ph = QVBoxLayout(placeholder)
        ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph.setSpacing(0)

        icon = QLabel("@")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-size: 56px; color: #D1D5DB; margin-bottom: 12px; font-weight: 300;")
        ph.addWidget(icon)

        title = QLabel("No message selected")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "font-size: 18px; font-weight: 700; color: #9CA3AF; letter-spacing: -0.2px;"
        )
        ph.addWidget(title)

        hint = QLabel("Choose an email from the list to start reading")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("font-size: 13px; color: #D1D5DB; margin-top: 6px;")
        ph.addWidget(hint)

        self.detail_stack.addWidget(placeholder)

        # ── detail page ──
        detail = QWidget()
        detail.setObjectName("detail_panel")
        dl = QVBoxLayout(detail)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(0)

        dh = QWidget()
        dh.setObjectName("detail_header")
        dhl = QVBoxLayout(dh)
        dhl.setContentsMargins(28, 20, 28, 20)
        dhl.setSpacing(10)

        self.detail_subject = QLabel("")
        self.detail_subject.setObjectName("detail_subject")
        self.detail_subject.setWordWrap(True)
        self.detail_subject.setStyleSheet(
            "font-size: 22px; font-weight: 800; color: #111827; letter-spacing: -0.3px;"
        )
        dhl.addWidget(self.detail_subject)

        meta = QHBoxLayout()
        meta.setSpacing(12)

        self.avatar_widget = AvatarWidget("", 36)
        meta.addWidget(self.avatar_widget)

        from_col = QVBoxLayout()
        from_col.setSpacing(1)
        self.detail_from = QLabel("")
        self.detail_from.setObjectName("detail_meta")
        self.detail_from.setStyleSheet(
            "font-size: 13px; font-weight: 700; color: #111827;"
        )
        from_col.addWidget(self.detail_from)
        self.detail_to = QLabel("")
        self.detail_to.setObjectName("detail_meta_light")
        self.detail_to.setStyleSheet("font-size: 12px; color: #9CA3AF;")
        from_col.addWidget(self.detail_to)
        meta.addLayout(from_col, 1)

        self.detail_date = QLabel("")
        self.detail_date.setStyleSheet(
            "font-size: 12px; color: #9CA3AF; font-weight: 500;"
        )
        meta.addWidget(self.detail_date)

        dhl.addLayout(meta)

        reply = QPushButton("Reply")
        reply.setCursor(Qt.CursorShape.PointingHandCursor)
        reply.clicked.connect(self._on_compose)
        reply.setStyleSheet(
            "QPushButton { background: transparent; border: 1px solid #E5E7EB; "
            "border-radius: 8px; padding: 5px 16px; color: #4D6BFE; font-size: 12px; "
            "font-weight: 600; }"
            "QPushButton:hover { background: #EEF2FF; border-color: #4D6BFE; }"
        )
        dhl.addWidget(reply)

        # attachments area
        self._attachments_box = QWidget()
        self._attachments_box.setVisible(False)
        self._attachments_box.setStyleSheet(
            "QWidget#attachments_box { background: #F3F4F6; border-radius: 8px; padding: 6px 12px; }"
        )
        self._attachments_box.setObjectName("attachments_box")
        self._attachments_layout = QVBoxLayout(self._attachments_box)
        self._attachments_layout.setContentsMargins(0, 0, 0, 0)
        self._attachments_layout.setSpacing(4)
        dhl.addWidget(self._attachments_box)

        dl.addWidget(dh)

        self.detail_body = QWebEngineView()
        self.detail_body.setPage(_MailWebPage(self.detail_body))
        self.detail_body.setStyleSheet("background: #F9FAFB;")
        self.detail_body.settings().setAttribute(
            QWebEngineSettings.WebAttribute.AutoLoadImages, True
        )
        self.detail_body.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        self.detail_body.setHtml(
            "<html><body style='margin:0;background:#F9FAFB;'></body></html>"
        )
        dl.addWidget(self.detail_body, 1)

        self.detail_stack.addWidget(detail)
        self.detail_stack.setCurrentIndex(0)

        return self.detail_stack

    def _build_statusbar(self):
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet(
            "QStatusBar { background: #F3F4F6; color: #6B7280; font-size: 11px; "
            "border-top: 1px solid #E5E7EB; padding: 4px 16px; }"
        )
        self.setStatusBar(self.status_bar)

    # ==================================================================
    # Controller signal → UI updates
    # ==================================================================

    def _bind_controller(self):
        ctrl = self._ctrl
        ctrl.emails_updated.connect(self._on_emails_updated)
        ctrl.loading_changed.connect(self._on_loading_changed)
        ctrl.status_message.connect(self.status_bar.showMessage)
        ctrl.detail_header_ready.connect(self._on_detail_header_ready)
        ctrl.detail_loading.connect(self._show_loading_skeleton)
        ctrl.detail_body_ready.connect(self._on_detail_body_ready)
        ctrl.detail_error.connect(self._on_detail_error)
        ctrl.counts_updated.connect(self._on_counts_updated)
        ctrl.marked_read.connect(self._on_marked_read)
        ctrl.send_finished.connect(self._on_send_finished)
        ctrl.send_error.connect(self._on_send_error)
        ctrl.config_loaded.connect(self._build_account_area)
        ctrl.list_error.connect(self._on_list_error)
        ctrl.folder_reset.connect(self._on_folder_reset)

    def _on_emails_updated(self, data: list):
        self._stream_queue = list(data)
        self._stream_offset = 0
        self._stream_tick()

    def _on_loading_changed(self, loading: bool):
        if loading:
            self._count_stack.setCurrentIndex(0)
            self._spinner.start()
        else:
            self._spinner.stop()
            self._count_stack.setCurrentIndex(1)

    def _on_detail_header_ready(self, em: dict, active_cfg, is_sent: bool):
        self.detail_subject.setText(em["subject"])
        self.detail_date.setText(em["date"])
        if is_sent:
            self.detail_from.setText(f"to {em.get('to', '')}" if em.get('to') else "")
            self.detail_to.setText(f"from {active_cfg.email}")
            display_name = em.get("display", em.get("to", ""))
        else:
            self.detail_from.setText(em["from"])
            self.detail_to.setText(f"to {active_cfg.email}")
            display_name = em["from"]
        self.avatar_widget._name = display_name
        self.avatar_widget._bg = QColor(avatar_color(display_name))
        self.avatar_widget.update()
        self.detail_stack.setCurrentIndex(1)

    def _show_loading_skeleton(self):
        self._attachments_box.setVisible(False)
        self.detail_body.setHtml(
            "<html><body style='margin:0;background:#F9FAFB;display:flex;"
            "align-items:center;justify-content:center;height:100vh;"
            "font-family:-apple-system,BlinkMacSystemFont,sans-serif;'>"
            "<div style='text-align:center;'>"
            "<div style='width:32px;height:32px;border:3px solid #E5E7EB;"
            "border-top-color:#4D6BFE;border-radius:50%;margin:0 auto 16px;'></div>"
            "<p style='color:#9CA3AF;font-size:13px;font-weight:500;'>Loading message...</p>"
            "</div></body></html>"
        )

    def _on_detail_body_ready(self, html_b: str, text_b: str,
                              attachments: list, inline_images: dict):
        self._show_attachments(attachments)
        if html_b:
            if inline_images:
                html_b = self._resolve_cid_images(html_b, inline_images)
            wrapped = (
                "<html><head><meta charset='utf-8'>"
                "<meta http-equiv='Content-Security-Policy' "
                "content=\"default-src https: http: 'unsafe-inline' 'unsafe-eval' data: blob:;\">"
                "<style>"
                "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; "
                "line-height: 1.6; color: #111827; padding: 8px 0; "
                "word-wrap: break-word; overflow-wrap: break-word; }"
                "a { color: #4D6BFE; }"
                "blockquote { border-left: 3px solid #E5E7EB; margin-left: 0; padding-left: 16px; "
                "color: #6B7280; }"
                "img { max-width: 100% !important; height: auto; }"
                "table { max-width: 100% !important; }"
                "pre, code { background: #F3F4F6; border-radius: 6px; padding: 2px 6px; "
                "font-family: 'Cascadia Code', 'JetBrains Mono', monospace; font-size: 13px; }"
                "pre { padding: 12px 16px; overflow-x: auto; }"
                "</style></head><body>"
                + html_b +
                "</body></html>"
            )
            self.detail_body.setHtml(wrapped, QUrl("http://localhost"))
        elif text_b:
            text = text_b.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            text = text.replace("\n", "<br>")
            self.detail_body.setHtml(
                "<html><body style='font-family:-apple-system,BlinkMacSystemFont,sans-serif;"
                "font-size:14px;line-height:1.6;color:#111827;padding:24px 28px;"
                "background:#F9FAFB;'>"
                f"<pre style='font-family:\"Cascadia Code\",\"JetBrains Mono\",monospace;"
                f"font-size:13px;white-space:pre-wrap;color:#111827;margin:0;'>{text}</pre>"
                "</body></html>"
            )
        else:
            self.detail_body.setHtml(
                "<html><body style='margin:0;background:#F9FAFB;display:flex;"
                "align-items:center;justify-content:center;height:100vh;"
                "font-family:-apple-system,BlinkMacSystemFont,sans-serif;'>"
                "<p style='color:#D1D5DB;font-size:14px;'>(Empty message)</p>"
                "</body></html>"
            )

    def _on_list_error(self, err: str):
        QMessageBox.critical(self, "Error", f"Failed to fetch emails:\n{err}")

    def _on_detail_error(self, err: str):
        self._attachments_box.setVisible(False)
        self.detail_body.setHtml(
            "<html><body style='margin:0;background:#F9FAFB;display:flex;"
            "align-items:center;justify-content:center;height:100vh;"
            "font-family:-apple-system,BlinkMacSystemFont,sans-serif;'>"
            "<p style='color:#EF4444;font-size:14px;font-weight:600;'>"
            "Failed to load message</p>"
            "</body></html>"
        )

    def _on_counts_updated(self, total: int, unread: int, visible: int):
        if self._ctrl.unread_only:
            self.list_count.setText(f"{visible}/{total}")
        else:
            self.list_count.setText(f"{total}")
        folder_label = "Sent" if self._ctrl.current_folder == FOLDER_SENT else "Inbox"
        self.status_bar.showMessage(
            f"{total} messages in {folder_label}  ({unread} unread)"
        )

    def _on_marked_read(self, msg_id: str):
        """Update visual unread indicator in list or tree."""
        if self._ctrl.is_grouped:
            self._mark_read_in_tree(msg_id)
        else:
            self._mark_read_in_list(msg_id)

    def _mark_read_in_list(self, msg_id: str):
        for i in range(self.email_list.count()):
            item = self.email_list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == msg_id:
                w = self.email_list.itemWidget(item)
                if w:
                    w.set_unread(False)
                break

    def _mark_read_in_tree(self, msg_id: str):
        for ti in range(self.email_tree.topLevelItemCount()):
            parent = self.email_tree.topLevelItem(ti)
            for ci in range(parent.childCount()):
                child = parent.child(ci)
                if child.data(0, Qt.ItemDataRole.UserRole) == msg_id:
                    cw = self.email_tree.itemWidget(child, 0)
                    if cw:
                        cw.set_unread(False)
                    pw = self.email_tree.itemWidget(parent, 0)
                    if pw:
                        pw.update_unread(-1)
                    return

    def _on_send_finished(self):
        if self._compose_dlg:
            self._compose_dlg.accept()
            self._compose_dlg = None

    def _on_send_error(self, err: str):
        if self._compose_dlg:
            self._compose_dlg.send_btn.setEnabled(True)
            self._compose_dlg.send_btn.setText("Send")
        QMessageBox.critical(self, "Send Failed", f"Could not send message:\n\n{err}")

    def _on_folder_reset(self, folder: str):
        """Controller-triggered UI reset (e.g., account switch)."""
        self.inbox_tab.setObjectName("folder_active" if folder == FOLDER_INBOX else "")
        self.inbox_tab.style().unpolish(self.inbox_tab)
        self.inbox_tab.style().polish(self.inbox_tab)
        self.sent_tab.setObjectName("folder_active" if folder == FOLDER_SENT else "")
        self.sent_tab.style().unpolish(self.sent_tab)
        self.sent_tab.style().polish(self.sent_tab)
        self._filter_pill.setVisible(folder == FOLDER_INBOX)
        self.group_btn.setVisible(folder == FOLDER_INBOX)
        self.group_btn.setObjectName("")
        self.search_input.clear()
        self.filter_btn.setText("All")
        self.detail_stack.setCurrentIndex(0)
        self.email_list.clear()
        self.email_tree.clear()

    # ==================================================================
    # Streaming render
    # ==================================================================

    def _stream_tick(self):
        batch = self._stream_queue[self._stream_offset:
                                   self._stream_offset + self.STREAM_BATCH]

        if self._ctrl.is_grouped:
            self._stream_grouped_tick(batch)
        else:
            self._stream_flat_tick(batch)

        self._stream_offset += self.STREAM_BATCH
        if self._stream_offset < len(self._stream_queue):
            QTimer.singleShot(5, self._stream_tick)
        else:
            self._stream_queue = []
            QTimer.singleShot(0, self._fix_item_widths)

    def _stream_flat_tick(self, batch):
        if self._stream_offset == 0:
            self.email_list.setUpdatesEnabled(False)
            self.email_list.clear()
            self._list_stack.setCurrentIndex(0)
        for em in batch:
            item = QListWidgetItem()
            widget = EmailItemWidget(em)
            widget.set_unread(em.get("unread", False))
            item.setSizeHint(widget.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, em["id"])
            self.email_list.addItem(item)
            self.email_list.setItemWidget(item, widget)
        if self._stream_offset + self.STREAM_BATCH >= len(self._stream_queue):
            self.email_list.setUpdatesEnabled(True)

    def _stream_grouped_tick(self, batch):
        if self._stream_offset == 0:
            self.email_tree.setUpdatesEnabled(False)
            self.email_tree.clear()
            self._list_stack.setCurrentIndex(1)
        for key, total, unread, emails in batch:
            parent = QTreeWidgetItem()
            parent.setData(0, Qt.ItemDataRole.UserRole, None)
            parent.setFlags(parent.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            folder_w = SenderFolderWidget(key, total, unread)
            self.email_tree.addTopLevelItem(parent)
            self.email_tree.setItemWidget(parent, 0, folder_w)
            parent.setSizeHint(0, folder_w.sizeHint())
            for em in emails:
                child = QTreeWidgetItem(parent)
                child.setData(0, Qt.ItemDataRole.UserRole, em["id"])
                child.setFlags(child.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                email_w = EmailItemWidget(em)
                email_w.set_unread(em.get("unread", False))
                child.setSizeHint(0, email_w.sizeHint())
                self.email_tree.setItemWidget(child, 0, email_w)
            parent.setExpanded(True)
        if self._stream_offset + self.STREAM_BATCH >= len(self._stream_queue):
            self.email_tree.setUpdatesEnabled(True)

    def _fix_item_widths(self):
        if self._ctrl.is_grouped:
            tree = self.email_tree
            vw = tree.viewport().width()
            if vw <= 80:
                return
            for ti in range(tree.topLevelItemCount()):
                parent = tree.topLevelItem(ti)
                pw = tree.itemWidget(parent, 0)
                if pw:
                    sh = pw.sizeHint()
                    sh.setWidth(vw)
                    parent.setSizeHint(0, sh)
                if not parent.isExpanded():
                    continue
                for ci in range(parent.childCount()):
                    child = parent.child(ci)
                    cw = tree.itemWidget(child, 0)
                    if cw:
                        sh = cw.sizeHint()
                        sh.setWidth(vw)
                        child.setSizeHint(0, sh)
            tree.scheduleDelayedItemsLayout()
        else:
            vw = self.email_list.viewport().width()
            if vw <= 80:
                return
            for i in range(self.email_list.count()):
                item = self.email_list.item(i)
                w = self.email_list.itemWidget(item)
                if w:
                    sh = w.sizeHint()
                    sh.setWidth(vw)
                    item.setSizeHint(sh)
            self.email_list.scheduleDelayedItemsLayout()

    # ==================================================================
    # Email selection (user → controller)
    # ==================================================================

    def _on_tree_clicked(self, item: QTreeWidgetItem, col: int):
        if item.childCount() > 0:
            item.setExpanded(not item.isExpanded())
            return
        msg_id = item.data(0, Qt.ItemDataRole.UserRole)
        if msg_id is not None:
            self._ctrl.select_email(msg_id)

    def _on_list_row_changed(self, row: int):
        if row < 0:
            return
        item = self.email_list.item(row)
        if item:
            msg_id = item.data(Qt.ItemDataRole.UserRole)
            if msg_id is not None:
                self._ctrl.select_email(msg_id)

    # ==================================================================
    # Attachments
    # ==================================================================

    def _show_attachments(self, attachments: list[dict]):
        while self._attachments_layout.count():
            child = self._attachments_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        if not attachments:
            self._attachments_box.setVisible(False)
            return
        self._attachments_box.setVisible(True)
        for att in attachments:
            lbl = QLabel(f"📎 {att['filename']}  ({att['size'] / 1024:.0f} KB)")
            lbl.setStyleSheet(
                "font-size: 12px; color: #4D6BFE; font-weight: 600; "
                "padding: 4px 8px;"
            )
            lbl.setCursor(Qt.CursorShape.PointingHandCursor)
            lbl.mousePressEvent = lambda e, a=att: self._save_attachment(a)
            self._attachments_layout.addWidget(lbl)

    def _save_attachment(self, att: dict):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Attachment", att["filename"]
        )
        if path:
            with open(path, "wb") as f:
                f.write(att["data"])

    @staticmethod
    def _resolve_cid_images(html: str, inline_images: dict[str, dict]) -> str:
        def _replace_cid(m: re.Match) -> str:
            cid = m.group(1)
            img = inline_images.get(cid)
            if img:
                b64 = base64.b64encode(img["data"]).decode()
                return f'data:{img["content_type"]};base64,{b64}'
            return m.group(0)
        html = re.sub(r'(src|url)\s*=\s*["\']cid:([^"\']+)["\']', _replace_cid, html)
        html = re.sub(r'(src|url)\s*=\s*cid:([a-zA-Z0-9@._-]+)', _replace_cid, html)
        html = re.sub(r'url\(["\']?\s*cid:([a-zA-Z0-9@._-]+)\s*["\']?\)', _replace_cid, html)
        html = re.sub(r'cid:([a-zA-Z0-9@._-]+)', _replace_cid, html)
        return html

    # ==================================================================
    # Compose / Send
    # ==================================================================

    def _on_compose(self):
        dlg = ComposeDialog(self)
        dlg.send_btn.clicked.connect(lambda: self._do_send(dlg))
        dlg.exec()

    def _do_send(self, dlg: ComposeDialog):
        to_addr = dlg.to_input.text().strip()
        if not to_addr:
            QMessageBox.warning(self, "Validation", "Please enter a recipient email address.")
            return
        dlg.send_btn.setEnabled(False)
        dlg.send_btn.setText("Sending...")
        self._compose_dlg = dlg
        self._ctrl.send_email(to_addr, dlg.subject_input.text(), dlg.body_input.toPlainText())

    # ==================================================================
    # Settings
    # ==================================================================

    def _update_account_btn_text(self):
        a = self._ctrl.cfg.accounts[self._ctrl.active_idx]
        label = a.name or a.email or "Unknown"
        self.account_switcher.setText(f"  {label}  ▾")

    def _show_account_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu {"
            "  background: #FFFFFF;"
            "  border: 1px solid #E8EAED;"
            "  border-radius: 10px;"
            "  padding: 6px;"
            "}"
            "QMenu::item {"
            "  padding: 8px 32px 8px 16px;"
            "  border-radius: 6px;"
            "  font-size: 12.5px;"
            "  color: #1F2937;"
            "}"
            "QMenu::item:selected {"
            "  background: #F0F1F4;"
            "  color: #111827;"
            "}"
        )
        accounts = self._ctrl.cfg.accounts
        for i, a in enumerate(accounts):
            label = a.name or a.email or "Unknown"
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(i == self._ctrl.active_idx)
            action.setData(i)
        action = menu.exec(self.account_switcher.mapToGlobal(
            self.account_switcher.rect().bottomLeft()))
        if action and action.data() is not None:
            self._ctrl.switch_account(action.data())
            self._update_account_btn_text()

    def _on_settings(self):
        dlg = SettingsDialog(self._ctrl.cfg, self)
        if dlg.exec() == SettingsDialog.DialogCode.Accepted and dlg.cfg:
            self._ctrl.apply_config(dlg.cfg)
            if hasattr(self, 'account_switcher'):
                self._update_account_btn_text()
