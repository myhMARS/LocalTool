from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QPushButton, QSizePolicy, QSplitter,
    QStackedWidget, QStatusBar, QVBoxLayout, QWidget,
)

from localtool.mailer.dialogs import ComposeDialog, SettingsDialog
from localtool.mailer.style import avatar_color, STYLE
from localtool.mailer.widgets import AvatarWidget, EmailItemWidget, SpinnerWidget
from localtool.mailer.workers import (
    FOLDER_INBOX, FOLDER_SENT, FetchBodyWorker, FetchListWorker, SendWorker,
)


class MainWindow(QMainWindow):
    def __init__(self, cfg: dict):
        super().__init__()
        self.cfg = cfg
        self.emails: list[dict] = []
        self._sent_emails: list[dict] = []
        self._current_folder = FOLDER_INBOX
        self._unread_only = False
        self._fetch_worker: FetchListWorker | None = None
        self._body_worker: FetchBodyWorker | None = None
        self._send_worker: SendWorker | None = None

        self.setWindowTitle("Email")
        self.setMinimumSize(960, 580)
        self.resize(1140, 740)
        self.setStyleSheet(STYLE)

        self._setup_ui()
        self._refresh_list()

    # ==================================================================
    # UI setup
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
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(24, 14, 24, 14)
        layout.setSpacing(12)

        brand = QLabel("Email")
        brand.setObjectName("toolbar_title")
        layout.addWidget(brand)

        addr = self.cfg.get("email", "")
        if addr:
            badge = QLabel(addr)
            badge.setObjectName("toolbar_subtitle")
            badge.setStyleSheet(
                "font-size: 11px; color: #9CA3AF; font-weight: 500; "
                "background: #F3F4F6; border-radius: 6px; padding: 2px 10px;"
            )
            layout.addWidget(badge)

        layout.addStretch()

        compose_btn = QPushButton("Compose")
        compose_btn.setObjectName("primary_btn")
        compose_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        compose_btn.clicked.connect(self._on_compose)
        layout.addWidget(compose_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("tool_btn")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self._refresh_list)
        layout.addWidget(refresh_btn)

        settings_btn = QPushButton("Settings")
        settings_btn.setObjectName("tool_btn")
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.clicked.connect(self._on_settings)
        layout.addWidget(settings_btn)

        root.addWidget(bar)

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
        self.inbox_tab.clicked.connect(lambda: self._switch_folder(FOLDER_INBOX))
        ft_layout.addWidget(self.inbox_tab)

        self.sent_tab = QPushButton("Sent")
        self.sent_tab.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sent_tab.clicked.connect(lambda: self._switch_folder(FOLDER_SENT))
        ft_layout.addWidget(self.sent_tab)

        row1.addWidget(folder_tabs)
        row1.addStretch()

        # filter + count grouped pill
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
        self.filter_btn.clicked.connect(self._toggle_filter)
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
        self._search_text = ""
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMaximumHeight(30)
        self.search_input.setStyleSheet(
            "QLineEdit { background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px; "
            "padding: 5px 10px; font-size: 12px; color: #111827; }"
            "QLineEdit:focus { border: 1.5px solid #4D6BFE; }"
        )
        self.search_input.textChanged.connect(self._on_search_changed)
        hv.addWidget(self.search_input)

        layout.addWidget(header)

        self.email_list = QListWidget()
        self.email_list.setFrameShape(QFrame.Shape.NoFrame)
        self.email_list.setSpacing(0)
        self.email_list.setIconSize(QSize(40, 40))
        self.email_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.email_list.currentRowChanged.connect(self._on_select_email)
        self.email_list.setCursor(Qt.CursorShape.PointingHandCursor)
        self.email_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.email_list.installEventFilter(self)
        layout.addWidget(self.email_list)

        return panel

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if obj is self.email_list and event.type() == QEvent.Type.Resize:
            self._fix_item_widths()
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
        self.detail_body.setStyleSheet("background: #F9FAFB;")
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
    # Refresh
    # ==================================================================

    def _switch_folder(self, folder: str):
        if self._current_folder == folder:
            return
        self._current_folder = folder
        self._unread_only = False
        self._search_text = ""
        self.search_input.clear()
        self.filter_btn.setText("All")
        # update tab styles
        self.inbox_tab.setObjectName("folder_active" if folder == FOLDER_INBOX else "")
        self.inbox_tab.style().unpolish(self.inbox_tab)
        self.inbox_tab.style().polish(self.inbox_tab)
        self.sent_tab.setObjectName("folder_active" if folder == FOLDER_SENT else "")
        self.sent_tab.style().unpolish(self.sent_tab)
        self.sent_tab.style().polish(self.sent_tab)
        # hide filter pill for Sent (no unread concept)
        self._filter_pill.setVisible(folder == FOLDER_INBOX)
        self.detail_stack.setCurrentIndex(0)
        cached = self._sent_emails if folder == FOLDER_SENT else self.emails
        if cached:
            self._apply_filter()
        else:
            self._refresh_list()

    def _active_emails(self) -> list[dict]:
        return self._sent_emails if self._current_folder == FOLDER_SENT else self.emails

    def _refresh_list(self):
        folder = FOLDER_SENT if self._current_folder == FOLDER_SENT else FOLDER_INBOX
        self.status_bar.showMessage(f"Refreshing {folder.lower()}...")
        self._count_stack.setCurrentIndex(0)
        self._spinner.start()
        self._fetch_worker = FetchListWorker(self.cfg, folder)
        self._fetch_worker.finished.connect(self._on_list_fetched)
        self._fetch_worker.error.connect(self._on_list_error)
        self._fetch_worker.start()

    def _on_list_fetched(self, emails: list[dict], status: str):
        if self._current_folder == FOLDER_SENT:
            self._sent_emails = emails
        else:
            self.emails = emails
        self._spinner.stop()
        self._count_stack.setCurrentIndex(1)
        self._apply_filter()
        self.email_list.setEnabled(True)
        self.status_bar.showMessage(status)

    def _on_search_changed(self, text: str):
        self._search_text = text.strip().lower()
        self._apply_filter()

    def _toggle_filter(self):
        if self._current_folder == FOLDER_SENT:
            return
        self._unread_only = not self._unread_only
        self.filter_btn.setText("Unread" if self._unread_only else "All")
        self._apply_filter()

    def _apply_filter(self):
        self.email_list.clear()
        src = self._active_emails()
        visible = [e for e in src if not self._unread_only or e.get("unread", False)]
        if self._search_text:
            visible = [
                e for e in visible
                if self._search_text in e.get("display", "").lower()
                or self._search_text in e.get("subject", "").lower()
            ]
        for em in visible:
            item = QListWidgetItem()
            widget = EmailItemWidget(em)
            widget.set_unread(em.get("unread", False))
            item.setSizeHint(widget.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, em["id"])
            self.email_list.addItem(item)
            self.email_list.setItemWidget(item, widget)
        total = len(self._active_emails())
        shown = len(visible)
        if self._unread_only:
            self.list_count.setText(f"{shown}/{total}")
        else:
            self.list_count.setText(f"{total}")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._fix_item_widths)

    def _fix_item_widths(self):
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

    def _on_list_error(self, err: str):
        self._spinner.stop()
        self._count_stack.setCurrentIndex(1)
        self.email_list.setEnabled(True)
        self.status_bar.showMessage(f"Error: {err}")
        QMessageBox.critical(self, "Error", f"Failed to fetch emails:\n{err}")

    # ==================================================================
    # Select email
    # ==================================================================

    def _on_select_email(self, row: int):
        if row < 0:
            return
        item = self.email_list.item(row)
        if item is None:
            return
        msg_id = item.data(Qt.ItemDataRole.UserRole)
        em = next((e for e in self._active_emails() if e["id"] == msg_id), None)
        if em is None:
            return

        is_sent = self._current_folder == FOLDER_SENT
        self.detail_subject.setText(em["subject"])
        self.detail_date.setText(em["date"])

        if is_sent:
            self.detail_from.setText(f"to {em.get('to', '')}" if em.get('to') else "")
            self.detail_to.setText(f"from {self.cfg.get('email', 'me')}")
            display_name = em.get("display", em.get("to", ""))
            self.avatar_widget._name = display_name
            self.avatar_widget._bg = QColor(avatar_color(display_name))
        else:
            self.detail_from.setText(em["from"])
            self.detail_to.setText(f"to {self.cfg.get('email', 'me')}")
            self.avatar_widget._name = em["from"]
            self.avatar_widget._bg = QColor(avatar_color(em["from"]))
        self.avatar_widget.update()

        self._show_loading_skeleton()
        self.detail_stack.setCurrentIndex(1)

        folder = FOLDER_SENT if is_sent else FOLDER_INBOX
        self._body_worker = FetchBodyWorker(self.cfg, em["id"], folder)
        self._body_worker.finished.connect(self._on_body_fetched)
        self._body_worker.error.connect(self._on_body_error)
        self._body_worker.start()

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

    def _on_body_fetched(self, html_b: str, text_b: str, attachments: list | None = None):
        self._show_attachments(attachments or [])
        if html_b:
            wrapped = (
                "<html><head><meta charset='utf-8'><style>"
                "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; "
                "line-height: 1.6; color: #111827; padding: 8px 0; }"
                "a { color: #4D6BFE; }"
                "blockquote { border-left: 3px solid #E5E7EB; margin-left: 0; padding-left: 16px; "
                "color: #6B7280; }"
                "img { max-width: 100%; height: auto; }"
                "pre, code { background: #F3F4F6; border-radius: 6px; padding: 2px 6px; "
                "font-family: 'Cascadia Code', 'JetBrains Mono', monospace; font-size: 13px; }"
                "pre { padding: 12px 16px; overflow-x: auto; }"
                "</style></head><body>"
                + html_b +
                "</body></html>"
            )
            self.detail_body.setHtml(wrapped)
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

    def _show_attachments(self, attachments: list[dict]):
        # clear previous
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

    def _on_body_error(self, err: str):
        self._attachments_box.setVisible(False)
        self.detail_body.setHtml(
            "<html><body style='margin:0;background:#F9FAFB;display:flex;"
            "align-items:center;justify-content:center;height:100vh;"
            "font-family:-apple-system,BlinkMacSystemFont,sans-serif;'>"
            f"<p style='color:#EF4444;font-size:14px;font-weight:600;'>"
            f"Failed to load message</p>"
            "</body></html>"
        )

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
        self._send_worker = SendWorker(
            self.cfg, to_addr, dlg.subject_input.text(), dlg.body_input.toPlainText()
        )
        self._send_worker.finished.connect(lambda: self._on_sent(dlg))
        self._send_worker.error.connect(lambda e: self._on_send_error(e, dlg))
        self._send_worker.start()

    def _on_sent(self, dlg: ComposeDialog):
        dlg.accept()
        self.status_bar.showMessage("Message sent")
        self._refresh_list()

    def _on_send_error(self, err: str, dlg: ComposeDialog):
        dlg.send_btn.setEnabled(True)
        dlg.send_btn.setText("Send")
        QMessageBox.critical(self, "Send Failed", f"Could not send message:\n\n{err}")

    # ==================================================================
    # Settings
    # ==================================================================

    def _on_settings(self):
        dlg = SettingsDialog(self.cfg, self)
        if dlg.exec() == SettingsDialog.DialogCode.Accepted and dlg.cfg:
            self.cfg = dlg.cfg
            self._refresh_list()
