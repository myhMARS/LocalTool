from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QScrollArea, QTextEdit, QVBoxLayout, QWidget,
)

from localtool.mailer.config import cache_session_key, load_config, save_config
from localtool.mailer.style import STYLE


class LoginDialog(QDialog):
    """Polished unlock screen with centered card layout."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Email")
        self.setFixedSize(420, 340)
        self.setStyleSheet(STYLE)
        self.cfg = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 36, 48, 36)
        layout.setSpacing(0)

        icon = QLabel("✉")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-size: 36px; color: #4D6BFE; margin-bottom: 8px;")
        layout.addWidget(icon)

        title = QLabel("Email")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "font-size: 24px; font-weight: 800; color: #111827; "
            "letter-spacing: -0.5px; margin-bottom: 4px;"
        )
        layout.addWidget(title)

        subtitle = QLabel("Unlock with your master password")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(
            "font-size: 13px; color: #9CA3AF; font-weight: 500; margin-bottom: 24px;"
        )
        layout.addWidget(subtitle)

        self.pwd_input = QLineEdit()
        self.pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwd_input.setPlaceholderText("Master password")
        self.pwd_input.returnPressed.connect(self._unlock)
        self.pwd_input.setMinimumHeight(44)
        layout.addWidget(self.pwd_input)

        self.error_label = QLabel("")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setStyleSheet(
            "color: #EF4444; font-size: 12px; font-weight: 600; margin-top: 8px;"
        )
        self.error_label.setMinimumHeight(20)
        layout.addWidget(self.error_label)

        layout.addSpacing(8)

        unlock_btn = QPushButton("Unlock")
        unlock_btn.setObjectName("primary_btn")
        unlock_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        unlock_btn.clicked.connect(self._unlock)
        unlock_btn.setMinimumHeight(44)
        layout.addWidget(unlock_btn)

        layout.addSpacing(12)

        setup_btn = QPushButton("First time? Set up account")
        setup_btn.setObjectName("text_btn")
        setup_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        setup_btn.clicked.connect(self._setup)
        setup_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #4D6BFE; "
            "font-size: 12.5px; font-weight: 600; padding: 6px 12px; }"
            "QPushButton:hover { color: #3F5CE5; }"
        )
        layout.addWidget(setup_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def _unlock(self):
        pwd = self.pwd_input.text()
        if not pwd:
            self.error_label.setText("Please enter your password")
            return
        result = load_config(pwd)
        if result:
            cache_session_key(pwd)
            self.cfg = result
            self.accept()
        else:
            self.error_label.setText("Invalid password")

    def _setup(self):
        self.cfg = None
        self.done(2)


class SettingsDialog(QDialog):
    """Account settings with card-style grouped sections."""

    def __init__(self, cfg: dict | None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Account Settings")
        self.setMinimumSize(520, 560)
        self.setStyleSheet(STYLE)
        self.cfg = cfg

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # header
        header = QWidget()
        header.setStyleSheet(
            "background: #FFFFFF; border-bottom: 1px solid #E5E7EB; "
            "padding: 24px 32px 20px 32px;"
        )
        hh = QVBoxLayout(header)
        hh.setContentsMargins(0, 0, 0, 0)
        hh.setSpacing(4)

        title = QLabel("Account Settings")
        title.setStyleSheet(
            "font-size: 20px; font-weight: 800; color: #111827; letter-spacing: -0.3px;"
        )
        hh.addWidget(title)

        desc = QLabel("Configure your email server and master password")
        desc.setStyleSheet("font-size: 13px; color: #9CA3AF; font-weight: 500;")
        hh.addWidget(desc)
        root.addWidget(header)

        # scrollable body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        body.setStyleSheet("background: #F9FAFB;")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(32, 24, 32, 24)
        body_layout.setSpacing(16)

        body_layout.addWidget(_card(
            icon="👤", title="Identity",
            form_items=[
                ("Email address", "you@example.com",
                 cfg.get("email", "") if cfg else "", False, None),
            ],
            target=self, field_names=["email_input"],
        ))

        body_layout.addWidget(_card(
            icon="📥", title="Incoming mail — IMAP",
            form_items=[
                ("Host", "imap.example.com",
                 cfg.get("imap_host", "") if cfg else "", False, None),
                ("Port", "993",
                 str(cfg.get("imap_port", "993")) if cfg else "993", False, 100),
            ],
            target=self, field_names=["imap_host", "imap_port"],
        ))

        body_layout.addWidget(_card(
            icon="📤", title="Outgoing mail — SMTP",
            form_items=[
                ("Host", "smtp.example.com",
                 cfg.get("smtp_host", "") if cfg else "", False, None),
                ("Port", "587",
                 str(cfg.get("smtp_port", "587")) if cfg else "587", False, 100),
            ],
            target=self, field_names=["smtp_host", "smtp_port"],
        ))

        body_layout.addWidget(_card(
            icon="🔑", title="Credentials",
            form_items=[
                ("Email password", None,
                 cfg.get("password", "") if cfg else "", True, None),
            ],
            target=self, field_names=["email_pwd"],
        ))

        body_layout.addWidget(_card(
            icon="🔒", title="Master password",
            subtitle="Encrypts your account configuration on disk",
            form_items=[
                ("Password", "Set or change master password", "", True, None),
                ("Confirm", "Re-enter master password", "", True, None),
            ],
            target=self, field_names=["master_pwd", "master_confirm"],
        ))

        body_layout.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        # footer
        footer = QWidget()
        footer.setStyleSheet(
            "background: #FFFFFF; border-top: 1px solid #E5E7EB; padding: 16px 32px;"
        )
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(12)
        fl.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setMinimumHeight(40)
        cancel_btn.setMinimumWidth(90)
        fl.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setObjectName("primary_btn")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._save)
        save_btn.setMinimumHeight(40)
        save_btn.setMinimumWidth(120)
        fl.addWidget(save_btn)

        root.addWidget(footer)

    def _save(self):
        if self.master_pwd.text() != self.master_confirm.text():
            QMessageBox.warning(self, "Error", "Master passwords do not match")
            return
        data = {
            "email": self.email_input.text(),
            "imap_host": self.imap_host.text(),
            "imap_port": int(self.imap_port.text()),
            "smtp_host": self.smtp_host.text(),
            "smtp_port": int(self.smtp_port.text()),
            "password": self.email_pwd.text(),
        }
        save_config(self.master_pwd.text(), data)
        cache_session_key(self.master_pwd.text())
        self.cfg = data
        self.accept()


class ComposeDialog(QDialog):
    """Polished compose window with monospace body and clear action buttons."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Message")
        self.setMinimumSize(580, 500)
        self.setStyleSheet(STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(0)

        title = QLabel("New Message")
        title.setStyleSheet(
            "font-size: 20px; font-weight: 800; color: #111827; "
            "letter-spacing: -0.3px; margin-bottom: 16px;"
        )
        layout.addWidget(title)

        to_label = QLabel("To")
        to_label.setStyleSheet(
            "font-size: 12px; font-weight: 700; color: #6B7280; "
            "text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;"
        )
        layout.addWidget(to_label)
        self.to_input = QLineEdit()
        self.to_input.setPlaceholderText("recipient@example.com")
        self.to_input.setMinimumHeight(42)
        layout.addWidget(self.to_input)

        layout.addSpacing(12)

        subj_label = QLabel("Subject")
        subj_label.setStyleSheet(
            "font-size: 12px; font-weight: 700; color: #6B7280; "
            "text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;"
        )
        layout.addWidget(subj_label)
        self.subject_input = QLineEdit()
        self.subject_input.setPlaceholderText("Subject")
        self.subject_input.setMinimumHeight(42)
        layout.addWidget(self.subject_input)

        layout.addSpacing(12)

        body_label = QLabel("Message")
        body_label.setStyleSheet(
            "font-size: 12px; font-weight: 700; color: #6B7280; "
            "text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;"
        )
        layout.addWidget(body_label)
        self.body_input = QTextEdit()
        self.body_input.setPlaceholderText("Write your message...")
        self.body_input.setStyleSheet(
            "QTextEdit { font-family: 'Cascadia Code', 'JetBrains Mono', 'Consolas', monospace; "
            "font-size: 13px; line-height: 1.5; }"
        )
        layout.addWidget(self.body_input, 1)

        layout.addSpacing(16)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addStretch()

        discard_btn = QPushButton("Discard")
        discard_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        discard_btn.clicked.connect(self.reject)
        discard_btn.setMinimumHeight(40)
        discard_btn.setMinimumWidth(90)
        btn_layout.addWidget(discard_btn)

        self.send_btn = QPushButton("Send")
        self.send_btn.setObjectName("primary_btn")
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.setMinimumHeight(40)
        self.send_btn.setMinimumWidth(100)
        btn_layout.addWidget(self.send_btn)
        layout.addLayout(btn_layout)


# ── shared helpers ──

def divider() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet("background: #E5E7EB; margin: 0;")
    f.setFixedHeight(1)
    return f


def _card(*, icon: str, title: str, subtitle: str = "",
          form_items: list[tuple[str, str | None, str, bool, int | None]],
          target, field_names: list[str]) -> QWidget:
    """Build a card-style section with icon, header, and stacked label+input rows."""
    card = QWidget()
    card.setStyleSheet(
        "QWidget#card { background: #FFFFFF; border: 1px solid #E5E7EB; "
        "border-radius: 14px; }"
    )
    card.setObjectName("card")
    cl = QVBoxLayout(card)
    cl.setContentsMargins(20, 18, 20, 18)
    cl.setSpacing(14)

    # card header
    hdr = QHBoxLayout()
    hdr.setSpacing(10)

    ico = QLabel(icon)
    ico.setStyleSheet("font-size: 18px;")
    hdr.addWidget(ico)

    tt = QLabel(title)
    tt.setStyleSheet("font-size: 14px; font-weight: 700; color: #111827;")
    hdr.addWidget(tt)

    if subtitle:
        sub = QLabel(subtitle)
        sub.setStyleSheet("font-size: 11px; color: #9CA3AF; font-weight: 500;")
        hdr.addWidget(sub)

    hdr.addStretch()
    cl.addLayout(hdr)

    # form rows
    for idx, (label, placeholder, value, is_password, max_w) in enumerate(form_items):
        row = QVBoxLayout()
        row.setSpacing(4)

        lbl = QLabel(label.upper())
        lbl.setStyleSheet(
            "font-size: 11px; font-weight: 700; color: #9CA3AF; "
            "letter-spacing: 0.8px; margin-left: 2px;"
        )
        row.addWidget(lbl)

        inp = QLineEdit(value)
        if placeholder:
            inp.setPlaceholderText(placeholder)
        if is_password:
            inp.setEchoMode(QLineEdit.EchoMode.Password)
        inp.setMinimumHeight(40)
        if max_w:
            inp.setMaximumWidth(max_w)
        row.addWidget(inp)

        setattr(target, field_names[idx], inp)
        cl.addLayout(row)

    return card
