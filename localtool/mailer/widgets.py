from PyQt6.QtCore import QSize, Qt, QRectF, QTimer
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QTreeWidget, QVBoxLayout, QWidget, QFrame,
)

from localtool.mailer.style import avatar_color, avatar_initials


class AvatarWidget(QWidget):
    """Circular avatar with initials and a subtle ring border."""

    def __init__(self, name: str, size: int = 40, parent=None):
        super().__init__(parent)
        self._name = name
        self._size = size
        self._bg = QColor(avatar_color(name))
        self.setFixedSize(size + 4, size + 4)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        margin = 2
        draw_size = self._size - 4

        # subtle ring
        p.setPen(QPen(QColor("#E5E7EB"), 1.5))
        p.setBrush(QBrush(self._bg))
        p.drawEllipse(margin, margin, draw_size, draw_size)

        # initials
        p.setPen(QColor("#FFFFFF"))
        font = QFont()
        font.setPixelSize(int(draw_size * 0.44))
        font.setBold(True)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.5)
        p.setFont(font)
        initials = avatar_initials(self._name)
        p.drawText(margin, margin, draw_size, draw_size,
                   Qt.AlignmentFlag.AlignCenter, initials)


class EmailItemWidget(QWidget):
    """Rich email list item with avatar, sender, subject, date, and unread dot."""

    def __init__(self, em: dict, parent=None):
        super().__init__(parent)
        self.msg_id = em["id"]

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 14, 12)
        root.setSpacing(12)

        # unread indicator
        self.unread_dot = QWidget()
        self.unread_dot.setFixedSize(8, 8)
        self.unread_dot.setStyleSheet(
            "background: #4D6BFE; border-radius: 4px;"
        )
        self.unread_dot.hide()
        root.addWidget(self.unread_dot)
        root.setAlignment(self.unread_dot, Qt.AlignmentFlag.AlignVCenter)

        # avatar
        avatar = AvatarWidget(em.get("display", em["from"]), 42)
        root.addWidget(avatar)

        # text column
        text_col = QVBoxLayout()
        text_col.setSpacing(3)

        # top row: sender + date
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self._sender_full = em.get("display", em["from"])
        self.sender = QLabel(self._sender_full)
        self.sender.setStyleSheet(
            "font-weight: 700; font-size: 13px; color: #111827;"
        )
        self.sender.setTextFormat(Qt.TextFormat.PlainText)
        top_row.addWidget(self.sender, 1)

        self.date_lbl = QLabel(em["date"])
        self.date_lbl.setStyleSheet(
            "font-size: 11px; color: #9CA3AF; font-weight: 500;"
        )
        self.date_lbl.setTextFormat(Qt.TextFormat.PlainText)
        self.date_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.date_lbl.setFixedWidth(100)
        top_row.addWidget(self.date_lbl)
        text_col.addLayout(top_row)

        # subject line
        self._subject_full = em["subject"].replace("\n", " ").replace("\r", "")
        self.subject = QLabel(self._subject_full)
        self.subject.setStyleSheet(
            "font-size: 12.5px; color: #6B7280; font-weight: 400;"
        )
        self.subject.setMaximumHeight(17)
        self.subject.setTextFormat(Qt.TextFormat.PlainText)
        text_col.addWidget(self.subject)

        root.addLayout(text_col, 1)

    def sizeHint(self):
        if hasattr(self, '_cached_sh'):
            return self._cached_sh
        sh = super().sizeHint()
        p = self.parent()
        while p and not isinstance(p, (QListWidget, QTreeWidget)):
            p = p.parent()
        if p:
            vw = p.viewport().width()
            if vw > 80 and sh.width() > vw:
                sh = QSize(vw, sh.height())
        self._cached_sh = sh
        return sh

    def resizeEvent(self, event):
        if hasattr(self, '_cached_sh'):
            del self._cached_sh
        super().resizeEvent(event)
        w = self.width()
        text_w = w - 26 - 12 - 8 - 12 - 46 - 12 - 100 - 8
        if text_w < 60:
            text_w = 60
        fm = self.sender.fontMetrics()
        self.sender.setText(
            fm.elidedText(self._sender_full, Qt.TextElideMode.ElideRight, text_w)
        )
        fm2 = self.subject.fontMetrics()
        self.subject.setText(
            fm2.elidedText(self._subject_full, Qt.TextElideMode.ElideRight, text_w)
        )

    def set_unread(self, unread: bool):
        self.unread_dot.setVisible(unread)


class SpinnerWidget(QWidget):
    """Rotating arc spinner for loading states."""

    def __init__(self, size: int = 14, parent=None):
        super().__init__(parent)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        self.setFixedSize(size, size)

    def _rotate(self):
        self._angle = (self._angle + 36) % 360
        self.update()

    def start(self):
        self.show()
        self._timer.start(42)

    def stop(self):
        self._timer.stop()
        self.hide()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#4D6BFE"), 1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        r = QRectF(2.5, 2.5, self.width() - 5, self.height() - 5)
        p.drawArc(r, self._angle * 16, 270 * 16)


class SenderFolderWidget(QWidget):
    """Sender folder header for grouped tree view."""

    def __init__(self, sender_name: str, total: int, unread: int, parent=None):
        super().__init__(parent)
        self._sender = sender_name
        self._total = total
        self._unread = unread

        self.setObjectName("sender_folder")
        self.setStyleSheet(
            "QWidget#sender_folder { background: #F3F4F6; border-bottom: 1px solid #E5E7EB; }"
        )

        root = QHBoxLayout(self)
        root.setContentsMargins(10, 8, 16, 8)
        root.setSpacing(10)

        name = QLabel(sender_name)
        name.setStyleSheet("font-size: 12.5px; font-weight: 700; color: #111827;")
        name.setTextFormat(Qt.TextFormat.PlainText)
        root.addWidget(name, 1)

        self._badge = QLabel(str(unread) if unread > 0 else "")
        self._badge.setStyleSheet(
            "font-size: 10px; font-weight: 700; color: #FFFFFF; "
            "background: #4D6BFE; border-radius: 8px; padding: 1px 7px;"
        )
        self._badge.setVisible(unread > 0)
        root.addWidget(self._badge)

        total_lbl = QLabel(str(total))
        total_lbl.setStyleSheet("font-size: 11px; color: #9CA3AF; font-weight: 500;")
        root.addWidget(total_lbl)

    def update_unread(self, delta: int):
        self._unread = max(0, self._unread + delta)
        self._badge.setText(str(self._unread) if self._unread > 0 else "")
        self._badge.setVisible(self._unread > 0)
