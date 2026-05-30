import math
import random
import subprocess
import sys

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)


EC_PROBE_PATH = r"C:\Program Files (x86)\NoteBook FanControl\ec-probe.exe"


class FanDial(QWidget):
    def __init__(self, title, percent=0, parent=None):
        super().__init__(parent)
        self.title = title
        self.percent = percent
        self.rpm = self._rpm_from_percent(percent)
        self.spin_degrees = 0.0 if title == "CPU" else 18.0
        self.setFixedSize(220, 230)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.spin_timer = QTimer(self)
        self.spin_timer.timeout.connect(self._animate)
        self.spin_timer.start(45)

    def sizeHint(self):
        return QSize(220, 230)

    def set_percent(self, percent):
        self.percent = max(0, min(100, int(percent)))
        self.rpm = self._rpm_from_percent(self.percent)
        self.update()

    def _animate(self):
        if self.percent <= 0:
            return
        self.spin_degrees = (self.spin_degrees + 2.0 + self.percent * 0.28) % 360
        self.update()

    def _rpm_from_percent(self, percent):
        if percent <= 0:
            return 0
        return int(950 + (percent * 35))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        label_height = 42
        visual_height = self.height() - label_height
        side = min(self.width(), visual_height) - 18
        cx = self.width() / 2
        cy = visual_height / 2 + 2
        radius = side / 2

        blade_color = QColor(118, 118, 118, 135)
        active_blade = QColor(205, 17, 34, 185)
        for index in range(40):
            angle = (index * 9 + self.spin_degrees) * math.pi / 180
            inner = radius * 0.49
            outer = radius * 0.88
            x1 = cx + math.cos(angle) * inner
            y1 = cy + math.sin(angle) * inner
            x2 = cx + math.cos(angle + 0.09) * outer
            y2 = cy + math.sin(angle + 0.09) * outer
            painter.setPen(QPen(active_blade if index % 5 == 0 else blade_color, 3))
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        ring_rect = QRectF(cx - radius * 0.56, cy - radius * 0.56, radius * 1.12, radius * 1.12)
        painter.setPen(QPen(QColor(145, 10, 20, 210), 3))
        painter.setBrush(QColor(18, 18, 18))
        painter.drawEllipse(ring_rect)

        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Segoe UI", 25, QFont.Weight.Bold))
        painter.drawText(ring_rect.adjusted(0, 24, 0, -28), Qt.AlignmentFlag.AlignCenter, str(self.rpm))

        painter.setPen(QColor(118, 118, 118))
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Normal))
        painter.drawText(ring_rect.adjusted(0, 78, 0, -14), Qt.AlignmentFlag.AlignCenter, "RPM")

        painter.setPen(QColor(245, 245, 245))
        painter.setFont(QFont("Segoe UI", 15, QFont.Weight.Medium))
        painter.drawText(
            QRectF(0, self.height() - 36, self.width(), 28),
            Qt.AlignmentFlag.AlignCenter,
            self.title,
        )


class GraphWidget(QWidget):
    def __init__(self, name, accent, temp_base, load_base, parent=None):
        super().__init__(parent)
        self.name = name
        self.accent = QColor(accent)
        self.values = self._seed_series(temp_base, 5, 70)
        self.load = self._seed_series(load_base, 9, 100)
        self.setMinimumHeight(118)
        self.setMaximumHeight(135)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(900)

    def _seed_series(self, base, spread, limit):
        return [
            max(0, min(limit, int(base + math.sin(index / 8) * spread + random.randint(-spread, spread))))
            for index in range(86)
        ]

    def _tick(self):
        self.values = self.values[1:] + [max(30, min(96, self.values[-1] + random.randint(-2, 3)))]
        self.load = self.load[1:] + [max(5, min(100, self.load[-1] + random.randint(-5, 6)))]
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(0, 0, -1, -1)

        gradient = QLinearGradient(0, rect.top(), 0, rect.bottom())
        gradient.setColorAt(0, QColor(18, 18, 18))
        gradient.setColorAt(1, QColor(24, 14, 14))
        painter.fillRect(rect, gradient)

        plot_rect = rect.adjusted(70, 16, -142, -14)
        painter.setPen(QPen(QColor(116, 20, 28, 70), 1))
        for x in range(int(plot_rect.left()), int(plot_rect.right()), 42):
            painter.drawLine(x, plot_rect.top(), x, plot_rect.bottom())
        for y in range(int(plot_rect.top()), int(plot_rect.bottom()), 26):
            painter.drawLine(plot_rect.left(), y, plot_rect.right(), y)

        painter.setPen(QColor(250, 250, 250))
        painter.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        painter.drawText(QRectF(18, 0, 48, rect.height()), Qt.AlignmentFlag.AlignVCenter, self.name)

        self._draw_series(painter, plot_rect, self.values, QColor(218, 24, 39), 2.3)
        self._draw_series(painter, plot_rect, self.load, self.accent, 1.9)

        temp = self.values[-1]
        load = self.load[-1]
        painter.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        painter.setPen(QColor(226, 20, 38))
        painter.drawText(QRectF(rect.right() - 120, 22, 105, 34), Qt.AlignmentFlag.AlignRight, f"{temp}C")
        painter.setPen(self.accent)
        painter.drawText(QRectF(rect.right() - 120, 66, 105, 34), Qt.AlignmentFlag.AlignRight, f"{load}%")

    def _draw_series(self, painter, rect, values, color, width):
        if len(values) < 2:
            return

        step = rect.width() / (len(values) - 1)
        points = []

        for index, value in enumerate(values):
            x = rect.left() + index * step
            y = rect.bottom() - (value / 100) * rect.height()
            points.append(QPointF(x, y))

        painter.setPen(QPen(color, width))
        for index in range(1, len(points)):
            painter.drawLine(points[index - 1], points[index])


class ModeButton(QPushButton):
    def __init__(self, title, subtitle, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setText(f"{title}\n{subtitle}")
        self.setMinimumHeight(64)
        self.setStyleSheet(
            """
            QPushButton {
                background: rgba(255, 255, 255, 0.015);
                border: 0;
                border-bottom: 1px solid rgba(255, 255, 255, 0.055);
                color: #747474;
                font: 14px "Segoe UI";
                padding: 9px 16px;
                text-align: left;
            }
            QPushButton:hover {
                background: rgba(210, 18, 34, 0.10);
                color: #d7d7d7;
            }
            QPushButton:checked {
                background: rgba(210, 18, 34, 0.16);
                border-left: 4px solid #d41124;
                color: #ff2539;
                font-weight: 700;
            }
            """
        )


class ForcaNitroApp(QWidget):
    def __init__(self):
        super().__init__()
        self.mode = "Auto"
        self.cpu_percent = 45
        self.gpu_percent = 45
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("ForcaNitro - Controle Termico")
        self.resize(1280, 760)
        self.setMinimumSize(1120, 700)
        self.setStyleSheet(
            """
            QWidget {
                background-color: #111111;
                color: #f4f4f4;
                font-family: "Segoe UI";
            }
            QLabel {
                background: transparent;
            }
            QFrame#Panel {
                background-color: #151515;
                border: 1px solid #2b2b2b;
                border-radius: 8px;
            }
            QFrame#ModeColumn {
                background-color: rgba(0, 0, 0, 0.22);
                border: 1px solid rgba(255, 255, 255, 0.035);
                border-radius: 6px;
            }
            QFrame#ControlCard {
                background-color: #1b1b1b;
                border: 1px solid #2d2d2d;
                border-radius: 7px;
            }
            QFrame#TitlePill {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #686868, stop:0.55 #333333, stop:1 #151515);
                border: 1px solid #303030;
                border-radius: 7px;
            }
            QPushButton#AccentButton {
                background-color: #c81023;
                color: white;
                border: 0;
                border-radius: 6px;
                font-weight: 700;
                padding: 13px 18px;
            }
            QPushButton#AccentButton:hover {
                background-color: #e1172d;
            }
            QSlider::groove:horizontal {
                height: 7px;
                background: #2d2d2d;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #c81023;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                width: 20px;
                margin: -7px 0;
                border-radius: 10px;
                background: #f4f4f4;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 20)
        root.setSpacing(16)

        root.addLayout(self._build_header())
        root.addWidget(self._build_fan_panel(), 0)
        root.addLayout(self._build_bottom_area(), 1)

        self._refresh_visuals()

    def _build_header(self):
        header = QHBoxLayout()
        header.setSpacing(18)

        brand = QLabel("FORCANITRO")
        brand.setFont(QFont("Segoe UI", 20, QFont.Weight.Black))
        brand.setStyleSheet("color: #d9d9d9;")

        title = QLabel("N I T R O   P A I N E L")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Segoe UI", 23, QFont.Weight.Bold))
        title.setStyleSheet("color: #d3d3d3;")

        self.status_label = QLabel("Pronto")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.status_label.setMinimumWidth(330)
        self.status_label.setStyleSheet("color: #a3a3a3; font-size: 13px;")

        header.addWidget(brand, 1)
        header.addWidget(title, 2)
        header.addWidget(self.status_label, 1)
        return header

    def _build_fan_panel(self):
        panel = self._panel("Fan Control")
        panel.setMinimumHeight(340)
        panel.setMaximumHeight(360)
        body = QHBoxLayout()
        body.setContentsMargins(18, 14, 18, 16)
        body.setSpacing(28)

        modes = QFrame()
        modes.setObjectName("ModeColumn")
        modes.setFixedWidth(255)
        modes_layout = QVBoxLayout(modes)
        modes_layout.setContentsMargins(0, 8, 0, 8)
        modes_layout.setSpacing(3)

        self.mode_group = QButtonGroup(self)
        self.auto_button = self._add_mode_button(modes_layout, "Auto", "Controle da BIOS")
        self.max_button = self._add_mode_button(modes_layout, "Max", "CPU/GPU 100%")
        self.quiet_button = self._add_mode_button(modes_layout, "Fixo", "CPU/GPU 40%")
        self.custom_button = self._add_mode_button(modes_layout, "Custom", "CPU/GPU juntos")
        self.auto_button.setChecked(True)
        modes_layout.addStretch()

        self.auto_button.clicked.connect(self.set_auto)
        self.max_button.clicked.connect(self.set_max)
        self.quiet_button.clicked.connect(self.set_quiet)
        self.custom_button.clicked.connect(lambda: self._set_status("Ajuste a barra e aplique o perfil custom."))

        gauges = QHBoxLayout()
        gauges.setSpacing(54)
        self.cpu_dial = FanDial("CPU", self.cpu_percent)
        self.gpu_dial = FanDial("GPU", self.gpu_percent)
        gauges.addStretch()
        gauges.addWidget(self.cpu_dial)
        gauges.addWidget(self.gpu_dial)
        gauges.addStretch()

        right = QVBoxLayout()
        right.setSpacing(8)
        coolboost = QLabel("CoolBoost  ON")
        coolboost.setAlignment(Qt.AlignmentFlag.AlignRight)
        coolboost.setStyleSheet("color: #f0f0f0; font-size: 17px; font-weight: 700;")
        right.addWidget(coolboost)
        right.addStretch()
        right.addLayout(gauges)
        right.addStretch()

        body.addWidget(modes)
        body.addLayout(right, 1)
        panel.layout().addLayout(body)
        return panel

    def _build_bottom_area(self):
        bottom = QHBoxLayout()
        bottom.setSpacing(18)
        bottom.addWidget(self._build_custom_panel(), 1)
        bottom.addWidget(self._build_monitoring_panel(), 2)
        return bottom

    def _build_custom_panel(self):
        panel = self._panel("Controle Manual")
        panel.setMinimumWidth(350)
        body = QVBoxLayout()
        body.setContentsMargins(20, 14, 20, 18)
        body.setSpacing(14)

        label = QLabel("Velocidade custom")
        label.setStyleSheet("color: #a5a5a5; font-size: 15px;")
        body.addWidget(label)

        self.custom_slider, self.custom_value = self._slider_row("CPU/GPU", 40)
        body.addWidget(self._slider_card("CPU + GPU", self.custom_slider, self.custom_value))

        self.custom_slider.valueChanged.connect(self._preview_custom_speed)

        apply_custom = QPushButton("Aplicar Custom")
        apply_custom.setObjectName("AccentButton")
        apply_custom.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_custom.clicked.connect(self.set_custom)
        body.addWidget(apply_custom)
        body.addStretch()

        panel.layout().addLayout(body)
        return panel

    def _build_monitoring_panel(self):
        panel = self._panel("Monitoring")
        body = QVBoxLayout()
        body.setContentsMargins(20, 14, 20, 18)
        body.setSpacing(12)

        subtitle = QLabel("Temperatura (C) / Loading (%)")
        subtitle.setStyleSheet("color: #898989; font-size: 15px;")
        body.addWidget(subtitle)
        body.addWidget(GraphWidget("CPU", "#ff8a22", 55, 38))
        body.addWidget(GraphWidget("GPU", "#ff8a22", 44, 28))

        panel.layout().addLayout(body)
        return panel

    def _panel(self, title):
        panel = QFrame()
        panel.setObjectName("Panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_bar = QFrame()
        title_bar.setObjectName("TitlePill")
        title_bar.setFixedHeight(42)
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(16, 0, 16, 0)
        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 15, QFont.Weight.Medium))
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        layout.addWidget(title_bar)
        return panel

    def _add_mode_button(self, layout, title, subtitle):
        button = ModeButton(title, subtitle)
        self.mode_group.addButton(button)
        layout.addWidget(button)
        return button

    def _slider_row(self, name, initial):
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(30, 100)
        slider.setValue(initial)
        value = QLabel(f"{initial}%")
        value.setMinimumWidth(44)
        value.setAlignment(Qt.AlignmentFlag.AlignRight)
        value.setStyleSheet("font-weight: 700; color: #f4f4f4;")
        return slider, value

    def _slider_card(self, title, slider, value_label):
        card = QFrame()
        card.setObjectName("ControlCard")
        row = QGridLayout(card)
        row.setContentsMargins(16, 12, 16, 14)
        row.setHorizontalSpacing(12)
        row.setVerticalSpacing(10)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 14px; font-weight: 800; color: #e7e7e7;")
        row.addWidget(title_label, 0, 0)
        row.addWidget(value_label, 0, 1)
        row.addWidget(slider, 1, 0, 1, 2)
        return card

    def _refresh_visuals(self):
        self.cpu_dial.set_percent(self.cpu_percent)
        self.gpu_dial.set_percent(self.gpu_percent)

    def _set_status(self, message):
        self.status_label.setText(message)

    def _preview_custom_speed(self, value):
        self.custom_value.setText(f"{value}%")
        if self.custom_button.isChecked():
            self.cpu_percent = value
            self.gpu_percent = value
            self._refresh_visuals()

    def percent_to_hex(self, percent):
        percent = max(0, min(100, int(percent)))
        return f"0x{percent:02X}"

    def run_command(self, address, value):
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        try:
            subprocess.run(
                [EC_PROBE_PATH, "write", address, value],
                creationflags=flags,
                check=True,
            )
            return True
        except FileNotFoundError:
            self._set_status("ec-probe.exe nao foi encontrado.")
        except subprocess.CalledProcessError:
            self._set_status(f"Falha ao escrever {value} em {address}.")
        return False

    def unlock_ec(self):
        return (
            self.run_command("0x03", "0x11")
            and self.run_command("0x22", "0x0C")
            and self.run_command("0x21", "0x30")
        )

    def apply_manual_fans(self, cpu_percent, gpu_percent, mode_name):
        self.cpu_percent = int(cpu_percent)
        self.gpu_percent = int(gpu_percent)
        self._refresh_visuals()

        if not self.unlock_ec():
            return

        cpu_ok = self.run_command("0x37", self.percent_to_hex(cpu_percent))
        gpu_ok = self.run_command("0x3A", self.percent_to_hex(gpu_percent))

        if cpu_ok and gpu_ok:
            self.mode = mode_name
            self._set_status(f"{mode_name}: CPU {cpu_percent}% / GPU {gpu_percent}% aplicado.")

    def set_max(self):
        self.apply_manual_fans(100, 100, "Max")

    def set_quiet(self):
        self.apply_manual_fans(40, 40, "Fixo")

    def set_custom(self):
        self.custom_button.setChecked(True)
        value = self.custom_slider.value()
        self.apply_manual_fans(value, value, "Custom")

    def set_auto(self):
        auto_ok = self.run_command("0x22", "0x04") and self.run_command("0x21", "0x10")
        if auto_ok:
            self.mode = "Auto"
            self.cpu_percent = 45
            self.gpu_percent = 45
            self._refresh_visuals()
            self._set_status("Auto: controle devolvido para a BIOS.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = ForcaNitroApp()
    ex.show()
    sys.exit(app.exec())
