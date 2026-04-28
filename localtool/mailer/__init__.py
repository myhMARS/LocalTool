import os
import sys

from localtool.core import BaseTool
from localtool.mailer.config import CONFIG_FILE, unlock_config
from localtool.mailer.style import STYLE


def _make_icon():
    from PyQt6.QtCore import Qt, QRectF
    from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QPixmap, QIcon, QFont

    px = QPixmap(64, 64)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # envelope body
    p.setPen(QPen(QColor("#4D6BFE"), 2.5))
    p.setBrush(QBrush(QColor("#EEF2FF")))
    rect = QRectF(8, 16, 48, 34)
    p.drawRoundedRect(rect, 6, 6)

    # envelope flap
    path = [
        (8, 16), (32, 38), (56, 16),
    ]
    from PyQt6.QtGui import QPolygonF
    from PyQt6.QtCore import QPointF
    poly = QPolygonF([QPointF(x, y) for x, y in path])
    p.setBrush(QBrush(QColor("#FFFFFF")))
    p.drawPolygon(poly)
    p.setPen(QPen(QColor("#4D6BFE"), 2.5))
    p.drawLine(8, 16, 32, 38)
    p.drawLine(56, 16, 32, 38)

    # mail emoji label in center
    p.setPen(QColor("#4D6BFE"))
    font = QFont()
    font.setPixelSize(20)
    font.setBold(True)
    p.setFont(font)
    p.drawText(QRectF(0, 10, 64, 64), Qt.AlignmentFlag.AlignCenter, "✉")

    p.end()
    return QIcon(px)


class EmailTool(BaseTool):
    name = "email"
    help = "email client (GUI)"

    def run(self, args: list[str] | None = None) -> int:
        from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox
        from localtool.mailer.dialogs import LoginDialog, SettingsDialog
        from localtool.mailer.window import MainWindow

        app = QApplication(sys.argv)
        app.setWindowIcon(_make_icon())
        app.setStyleSheet(STYLE)

        cfg = unlock_config()
        if cfg is None:
            if not os.path.exists(CONFIG_FILE):
                QMessageBox.information(None, "Welcome",
                    "No account configured yet.\n\nPlease set up your email account.")
                dlg = SettingsDialog(None)
                if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.cfg:
                    return 0
                cfg = dlg.cfg
            else:
                dlg = LoginDialog()
                result = dlg.exec()
                if result == QDialog.DialogCode.Rejected:
                    return 0
                if result == 2:
                    dlg2 = SettingsDialog(None)
                    if dlg2.exec() != QDialog.DialogCode.Accepted or not dlg2.cfg:
                        return 0
                    cfg = dlg2.cfg
                else:
                    cfg = dlg.cfg

        window = MainWindow(cfg)
        window.show()
        return app.exec()


run = EmailTool.entry_point
