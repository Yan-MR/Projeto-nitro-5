import json
import math
import ctypes
import os
import re
import shutil
import subprocess
import sys
import threading

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, QSignalBlocker, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
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
CPU_TEMP_REGISTER = 0xA7
CPU_RPM_REGISTER = 0x13
GPU_RPM_REGISTER = 0x15
WINDOW_TITLE = "ForcaNitro - Controle Termico"
SINGLE_INSTANCE_MUTEX = r"Local\ForcaNitro.SingleInstance"


def acquire_single_instance():
    if sys.platform != "win32":
        return True, None

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_bool

    ctypes.set_last_error(0)
    handle = kernel32.CreateMutexW(None, False, SINGLE_INSTANCE_MUTEX)
    if not handle:
        return True, None

    if ctypes.get_last_error() == 183:
        kernel32.CloseHandle(handle)
        return False, None

    return True, handle


def focus_existing_instance():
    if sys.platform != "win32":
        return

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
    user32.FindWindowW.restype = ctypes.c_void_p
    user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    user32.ShowWindow.restype = ctypes.c_bool
    user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
    user32.SetForegroundWindow.restype = ctypes.c_bool

    window = user32.FindWindowW(None, WINDOW_TITLE)
    if window:
        user32.ShowWindow(window, 9)
        user32.SetForegroundWindow(window)


def release_single_instance(handle):
    if handle and sys.platform == "win32":
        kernel32 = ctypes.WinDLL("kernel32")
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_bool
        kernel32.CloseHandle(handle)


class AcerProfileController:
    PROFILE_NAMES = {
        0: "Silencioso",
        1: "Balanced",
        4: "Desempenho",
        5: "Turbo",
    }
    ALLOWED_PROFILES = {1, 4}
    TESTED_MODEL_TOKEN = "AN515-58"

    READ_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$gaming = Get-CimInstance -Namespace root\wmi -ClassName AcerGamingFunction -ErrorAction Stop | Select-Object -First 1
if (-not $gaming) { throw 'AcerGamingFunction nao foi encontrado.' }
$model = (Get-CimInstance -ClassName Win32_ComputerSystem -ErrorAction Stop).Model
$read = Invoke-CimMethod -InputObject $gaming -MethodName GetGamingMiscSetting -Arguments @{ gmInput = [UInt32]0x0B } -ErrorAction Stop
$raw = [UInt64]$read.gmOutput
[ordered]@{
    model = $model
    profile = [int](($raw -shr 8) -band 0xFF)
    raw = $raw
} | ConvertTo-Json -Compress
"""

    WRITE_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$profileValue = [int]$env:FORCANITRO_ACER_PROFILE
if ($profileValue -notin @(1, 4)) { throw 'Perfil Acer fora da lista permitida.' }
$model = (Get-CimInstance -ClassName Win32_ComputerSystem -ErrorAction Stop).Model
if ($model -notmatch 'AN515-58') { throw "Troca de perfil WMI ainda nao validada para o modelo $model." }
$gaming = Get-CimInstance -Namespace root\wmi -ClassName AcerGamingFunction -ErrorAction Stop | Select-Object -First 1
if (-not $gaming) { throw 'AcerGamingFunction nao foi encontrado.' }
$beforeRead = Invoke-CimMethod -InputObject $gaming -MethodName GetGamingMiscSetting -Arguments @{ gmInput = [UInt32]0x0B } -ErrorAction Stop
$beforeRaw = [UInt64]$beforeRead.gmOutput
$beforeProfile = [int](($beforeRaw -shr 8) -band 0xFF)
$payload = [UInt64](0x0B + ($profileValue * 256))
try {
    $write = Invoke-CimMethod -InputObject $gaming -MethodName SetGamingMiscSetting -Arguments @{ gmInput = $payload } -ErrorAction Stop
    Start-Sleep -Milliseconds 350
    $read = Invoke-CimMethod -InputObject $gaming -MethodName GetGamingMiscSetting -Arguments @{ gmInput = [UInt32]0x0B } -ErrorAction Stop
    $raw = [UInt64]$read.gmOutput
    $confirmedProfile = [int](($raw -shr 8) -band 0xFF)
    if ($confirmedProfile -ne $profileValue) {
        throw "A Acer nao confirmou o perfil solicitado."
    }
}
catch {
    if ($beforeProfile -in @(0, 1, 4, 5)) {
        $rollbackPayload = [UInt64](0x0B + ($beforeProfile * 256))
        Invoke-CimMethod -InputObject $gaming -MethodName SetGamingMiscSetting -Arguments @{ gmInput = $rollbackPayload } -ErrorAction SilentlyContinue | Out-Null
    }
    throw
}
[ordered]@{
    model = $model
    beforeProfile = $beforeProfile
    requestedProfile = $profileValue
    profile = $confirmedProfile
    raw = $raw
    writeReturn = $write.ReturnValue
} | ConvertTo-Json -Compress
"""

    def read_profile(self):
        return self._normalize_result(self._run_powershell(self.READ_SCRIPT))

    def set_profile(self, profile):
        profile = int(profile)
        if profile not in self.ALLOWED_PROFILES:
            return {"ok": False, "error": "Perfil Acer nao permitido."}

        return self._normalize_result(
            self._run_powershell(
                self.WRITE_SCRIPT,
                {"FORCANITRO_ACER_PROFILE": str(profile)},
            ),
            expected_profile=profile,
        )

    def _normalize_result(self, result, expected_profile=None):
        if not result.get("ok"):
            return result

        profile = int(result.get("profile", -1))
        model = str(result.get("model", "")).strip()
        result["profile"] = profile
        result["profile_name"] = self.PROFILE_NAMES.get(profile, f"Desconhecido ({profile})")
        result["tested_model"] = self.TESTED_MODEL_TOKEN in model.upper()

        if expected_profile is not None and profile != expected_profile:
            result["ok"] = False
            result["error"] = (
                f"A Acer recebeu o comando, mas confirmou o perfil "
                f"{result['profile_name']} em vez do solicitado."
            )
        return result

    def _run_powershell(self, script, extra_environment=None):
        if sys.platform != "win32":
            return {"ok": False, "error": "Perfil Acer WMI disponivel somente no Windows."}

        environment = os.environ.copy()
        if extra_environment:
            environment.update(extra_environment)

        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        try:
            result = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    script,
                ],
                capture_output=True,
                text=True,
                timeout=8.0,
                creationflags=flags,
                env=environment,
            )
        except FileNotFoundError:
            return {"ok": False, "error": "PowerShell nao foi encontrado."}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "A leitura do perfil Acer excedeu o tempo limite."}

        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            if "Acesso negado" in detail or "Access denied" in detail:
                detail = "Execute o ForcaNitro como administrador para trocar o perfil Acer."
            else:
                detail = next(
                    (line.strip() for line in detail.splitlines() if line.strip()),
                    "Falha desconhecida no Acer WMI.",
                )
            return {"ok": False, "error": detail or "Falha desconhecida no Acer WMI."}

        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if not lines:
            return {"ok": False, "error": "Acer WMI nao retornou uma resposta."}

        try:
            parsed = json.loads(lines[-1])
        except json.JSONDecodeError:
            return {"ok": False, "error": "Resposta inesperada recebida do Acer WMI."}

        parsed["ok"] = True
        return parsed


class FILETIME(ctypes.Structure):
    _fields_ = [
        ("dwLowDateTime", ctypes.c_ulong),
        ("dwHighDateTime", ctypes.c_ulong),
    ]


class SystemMonitor:
    def __init__(self):
        self._previous_cpu_times = self._read_cpu_times()
        self._nvidia_smi = shutil.which("nvidia-smi")

    def read(self):
        ec_values = self._read_ec_dump()
        gpu_temp, gpu_load = self._read_nvidia_gpu()
        return {
            "cpu_temp": self._read_ec_temperature(ec_values, CPU_TEMP_REGISTER),
            "cpu_load": self._read_cpu_load(),
            "gpu_temp": gpu_temp,
            "gpu_load": gpu_load,
            "cpu_rpm": self._read_ec_word(ec_values, CPU_RPM_REGISTER),
            "gpu_rpm": self._read_ec_word(ec_values, GPU_RPM_REGISTER),
            "fan_state": self._read_fan_state(ec_values),
        }

    def _read_ec_dump(self):
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        try:
            result = subprocess.run(
                [EC_PROBE_PATH, "dump"],
                capture_output=True,
                text=True,
                timeout=2.0,
                creationflags=flags,
                check=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return {}

        values = {}
        for line in result.stdout.splitlines():
            match = re.match(r"^([0-9A-Fa-f]{2})\s*\|\s*(.*)$", line.strip())
            if not match:
                continue

            base_address = int(match.group(1), 16)
            for offset, raw_value in enumerate(match.group(2).split()[:16]):
                try:
                    values[base_address + offset] = int(raw_value, 16)
                except ValueError:
                    continue

        return values

    def _read_fan_state(self, values):
        if not values:
            return None

        control_21 = values.get(0x21)
        control_22 = values.get(0x22)
        cpu_target = values.get(0x37)
        gpu_target = values.get(0x3A)

        if control_21 == 0x10 and control_22 == 0x04:
            mode = "Auto"
        elif cpu_target == 100 and gpu_target == 100:
            mode = "Max"
        elif cpu_target == 40 and gpu_target == 40:
            mode = "Fixo"
        elif (
            control_21 == 0x30
            and control_22 == 0x0C
            and cpu_target is not None
            and gpu_target is not None
        ):
            mode = "Custom"
        else:
            mode = "Desconhecido"

        return {
            "mode": mode,
            "cpu_target": cpu_target if cpu_target is not None and 0 <= cpu_target <= 100 else None,
            "gpu_target": gpu_target if gpu_target is not None and 0 <= gpu_target <= 100 else None,
            "control_21": control_21,
            "control_22": control_22,
        }

    def _read_ec_temperature(self, values, address):
        value = values.get(address)
        if value is None or value < 20 or value > 105:
            return None
        return value

    def _read_ec_word(self, values, address):
        low = values.get(address)
        high = values.get(address + 1)
        if low is None or high is None:
            return None

        rpm = (high << 8) | low
        if rpm < 0 or rpm > 12000:
            return None
        return rpm

    def _read_cpu_times(self):
        if sys.platform != "win32":
            return None

        idle = FILETIME()
        kernel = FILETIME()
        user = FILETIME()
        ok = ctypes.windll.kernel32.GetSystemTimes(
            ctypes.byref(idle),
            ctypes.byref(kernel),
            ctypes.byref(user),
        )
        if not ok:
            return None

        return (
            self._filetime_to_int(idle),
            self._filetime_to_int(kernel),
            self._filetime_to_int(user),
        )

    def _read_cpu_load(self):
        current = self._read_cpu_times()
        previous = self._previous_cpu_times
        self._previous_cpu_times = current

        if not current or not previous:
            return None

        idle_delta = current[0] - previous[0]
        kernel_delta = current[1] - previous[1]
        user_delta = current[2] - previous[2]
        total_delta = kernel_delta + user_delta
        if total_delta <= 0:
            return None

        busy_delta = max(0, total_delta - idle_delta)
        return max(0, min(100, round((busy_delta / total_delta) * 100)))

    def _read_nvidia_gpu(self):
        if not self._nvidia_smi:
            return None, None

        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        try:
            result = subprocess.run(
                [
                    self._nvidia_smi,
                    "--query-gpu=temperature.gpu,utilization.gpu",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=1.5,
                creationflags=flags,
                check=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return None, None

        first_line = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
        parts = [part.strip() for part in first_line.split(",")]
        if len(parts) < 2:
            return None, None

        return self._parse_number(parts[0]), self._parse_number(parts[1])

    def _parse_number(self, value):
        try:
            return max(0, min(100, round(float(value))))
        except ValueError:
            return None

    def _filetime_to_int(self, filetime):
        return (filetime.dwHighDateTime << 32) + filetime.dwLowDateTime


class FanDial(QWidget):
    def __init__(self, title, percent=0, parent=None):
        super().__init__(parent)
        self.title = title
        self.percent = percent
        self.rpm = None
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
        self.update()

    def set_rpm(self, rpm):
        self.rpm = rpm
        self.update()

    def _animate(self):
        if self.percent <= 0:
            return
        self.spin_degrees = (self.spin_degrees + 2.0 + self.percent * 0.28) % 360
        self.update()

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
        primary_text = f"{self.rpm}" if self.rpm is not None else f"{self.percent}%"
        painter.drawText(ring_rect.adjusted(0, 24, 0, -28), Qt.AlignmentFlag.AlignCenter, primary_text)

        painter.setPen(QColor(118, 118, 118))
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Normal))
        painter.drawText(
            ring_rect.adjusted(0, 78, 0, -14),
            Qt.AlignmentFlag.AlignCenter,
            "RPM" if self.rpm is not None else "TARGET",
        )

        painter.setPen(QColor(245, 245, 245))
        painter.setFont(QFont("Segoe UI", 15, QFont.Weight.Medium))
        painter.drawText(
            QRectF(0, self.height() - 36, self.width(), 28),
            Qt.AlignmentFlag.AlignCenter,
            self.title,
        )


class GraphWidget(QWidget):
    def __init__(self, name, accent, parent=None):
        super().__init__(parent)
        self.name = name
        self.accent = QColor(accent)
        self.values = [None for _ in range(86)]
        self.load = [None for _ in range(86)]
        self.setMinimumHeight(118)
        self.setMaximumHeight(135)

    def update_sample(self, temp, load):
        self.values = self.values[1:] + [self._normalize(temp)]
        self.load = self.load[1:] + [self._normalize(load)]
        self.update()

    def _normalize(self, value):
        if value is None:
            return None
        return max(0, min(100, int(value)))

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
        painter.drawText(QRectF(rect.right() - 120, 22, 105, 34), Qt.AlignmentFlag.AlignRight, self._format_temp(temp))
        painter.setPen(self.accent)
        painter.drawText(QRectF(rect.right() - 120, 66, 105, 34), Qt.AlignmentFlag.AlignRight, self._format_load(load))

    def _draw_series(self, painter, rect, values, color, width):
        if len(values) < 2:
            return

        step = rect.width() / (len(values) - 1)
        points = []

        for index, value in enumerate(values):
            if value is None:
                points.append(None)
                continue
            x = rect.left() + index * step
            y = rect.bottom() - (value / 100) * rect.height()
            points.append(QPointF(x, y))

        painter.setPen(QPen(color, width))
        for index in range(1, len(points)):
            if points[index - 1] is None or points[index] is None:
                continue
            painter.drawLine(points[index - 1], points[index])

    def _format_temp(self, value):
        return "--C" if value is None else f"{value}C"

    def _format_load(self, value):
        return "--%" if value is None else f"{value}%"


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
    telemetry_ready = pyqtSignal(dict)
    profile_ready = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.mode = "Detectando"
        self.cpu_percent = 45
        self.gpu_percent = 45
        self.syncing_sliders = False
        self.telemetry_busy = False
        self.fan_state_initialized = False
        self.profile_busy = False
        self.current_acer_profile = None
        self.acer_profile_supported = False
        self.monitor = SystemMonitor()
        self.profile_controller = AcerProfileController()
        self.init_ui()
        self.telemetry_ready.connect(self._apply_telemetry)
        self.profile_ready.connect(self._apply_profile_result)

        self.telemetry_timer = QTimer(self)
        self.telemetry_timer.timeout.connect(self._request_telemetry)
        self.telemetry_timer.start(2500)
        self._request_telemetry()
        QTimer.singleShot(150, self._request_profile_read)

    def init_ui(self):
        self.setWindowTitle(WINDOW_TITLE)
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
        self.custom_button = self._add_mode_button(modes_layout, "Custom", "Ajuste manual")
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
        right.addLayout(self._build_profile_selector())
        right.addStretch()
        right.addLayout(gauges)
        right.addStretch()

        body.addWidget(modes)
        body.addLayout(right, 1)
        panel.layout().addLayout(body)
        return panel

    def _build_profile_selector(self):
        row = QHBoxLayout()
        row.setSpacing(0)
        row.addStretch()

        label = QLabel("Perfil Acer")
        label.setStyleSheet("color: #9d9d9d; font-size: 13px; margin-right: 10px;")
        row.addWidget(label)

        self.profile_group = QButtonGroup(self)
        self.profile_group.setExclusive(True)
        self.balanced_profile_button = self._profile_button("Balanced")
        self.performance_profile_button = self._profile_button("Desempenho")
        self.profile_group.addButton(self.balanced_profile_button)
        self.profile_group.addButton(self.performance_profile_button)
        row.addWidget(self.balanced_profile_button)
        row.addWidget(self.performance_profile_button)

        self.balanced_profile_button.clicked.connect(lambda: self._request_profile_change(1))
        self.performance_profile_button.clicked.connect(lambda: self._request_profile_change(4))
        self._set_profile_buttons_enabled(False)
        return row

    def _profile_button(self, text):
        button = QPushButton(text)
        button.setCheckable(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedHeight(32)
        button.setMinimumWidth(96)
        button.setStyleSheet(
            """
            QPushButton {
                background-color: #1d1d1d;
                border: 1px solid #3a3a3a;
                color: #9f9f9f;
                padding: 5px 11px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                color: #f0f0f0;
                border-color: #686868;
            }
            QPushButton:checked {
                background-color: #c81023;
                border-color: #e12639;
                color: white;
            }
            QPushButton:disabled {
                background-color: #181818;
                border-color: #292929;
                color: #555555;
            }
            """
        )
        return button

    def _set_profile_buttons_enabled(self, enabled):
        self.balanced_profile_button.setEnabled(enabled)
        self.performance_profile_button.setEnabled(enabled)

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

        self.link_checkbox = QCheckBox("Vincular CPU/GPU")
        self.link_checkbox.setChecked(True)
        self.link_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.link_checkbox.setStyleSheet(
            """
            QCheckBox {
                color: #e6e6e6;
                font-size: 14px;
                font-weight: 700;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:checked {
                background-color: #c81023;
                border: 2px solid #f4f4f4;
            }
            QCheckBox::indicator:unchecked {
                background-color: #222222;
                border: 2px solid #777777;
            }
            """
        )
        self.link_checkbox.stateChanged.connect(self._toggle_linked_fans)
        body.addWidget(self.link_checkbox)

        self.cpu_slider, self.cpu_value = self._slider_row("CPU", 40)
        self.gpu_slider, self.gpu_value = self._slider_row("GPU", 40)
        body.addWidget(self._slider_card("CPU Fan", self.cpu_slider, self.cpu_value))
        body.addWidget(self._slider_card("GPU Fan", self.gpu_slider, self.gpu_value))

        self.cpu_slider.valueChanged.connect(lambda value: self._preview_custom_speed("cpu", value))
        self.gpu_slider.valueChanged.connect(lambda value: self._preview_custom_speed("gpu", value))

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

        subtitle = QLabel("Temperatura real quando disponivel / Uso (%)")
        subtitle.setStyleSheet("color: #898989; font-size: 15px;")
        body.addWidget(subtitle)
        self.cpu_graph = GraphWidget("CPU", "#ff8a22")
        self.gpu_graph = GraphWidget("GPU", "#ff8a22")
        body.addWidget(self.cpu_graph)
        body.addWidget(self.gpu_graph)

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
        value.setFixedSize(64, 24)
        value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value.setStyleSheet(
            """
            background-color: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 4px;
            font-weight: 800;
            color: #f4f4f4;
            """
        )
        return slider, value

    def _slider_card(self, title, slider, value_label):
        card = QFrame()
        card.setObjectName("ControlCard")
        card.setMinimumHeight(74)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 12, 18, 14)
        layout.setSpacing(9)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 14px; font-weight: 800; color: #e7e7e7;")
        header.addWidget(title_label)
        header.addWidget(value_label)
        header.addStretch()

        layout.addLayout(header)
        layout.addWidget(slider)
        return card

    def _refresh_visuals(self):
        self.cpu_dial.set_percent(self.cpu_percent)
        self.gpu_dial.set_percent(self.gpu_percent)

    def _set_status(self, message):
        self.status_label.setText(message)

    def _preview_custom_speed(self, source, value):
        if self.syncing_sliders:
            return

        if self.link_checkbox.isChecked():
            self.syncing_sliders = True
            target_slider = self.gpu_slider if source == "cpu" else self.cpu_slider
            blocker = QSignalBlocker(target_slider)
            target_slider.setValue(value)
            del blocker
            self.syncing_sliders = False

        self._update_slider_labels()
        if self.custom_button.isChecked():
            self.cpu_percent = self.cpu_slider.value()
            self.gpu_percent = self.gpu_slider.value()
            self._refresh_visuals()

    def _toggle_linked_fans(self, _state=None):
        if self.link_checkbox.isChecked():
            blocker = QSignalBlocker(self.gpu_slider)
            self.gpu_slider.setValue(self.cpu_slider.value())
            del blocker
        self._update_slider_labels()
        mode = "vinculado" if self.link_checkbox.isChecked() else "separado"
        self._set_status(f"Custom: controle {mode}.")

    def _update_slider_labels(self):
        self.cpu_value.setText(f"{self.cpu_slider.value()}%")
        self.gpu_value.setText(f"{self.gpu_slider.value()}%")

    def _request_telemetry(self):
        if self.telemetry_busy:
            return

        self.telemetry_busy = True
        worker = threading.Thread(target=self._read_telemetry_background, daemon=True)
        worker.start()

    def _read_telemetry_background(self):
        data = self.monitor.read()
        self.telemetry_ready.emit(data)

    def _apply_telemetry(self, data):
        self.telemetry_busy = False
        self.cpu_graph.update_sample(data["cpu_temp"], data["cpu_load"])
        self.gpu_graph.update_sample(data["gpu_temp"], data["gpu_load"])
        self.cpu_dial.set_rpm(data["cpu_rpm"])
        self.gpu_dial.set_rpm(data["gpu_rpm"])
        self._sync_fan_state(data.get("fan_state"))

    def _sync_fan_state(self, fan_state):
        if self.fan_state_initialized or not fan_state or fan_state["mode"] == "Desconhecido":
            return

        mode = fan_state["mode"]
        buttons = {
            "Auto": self.auto_button,
            "Max": self.max_button,
            "Fixo": self.quiet_button,
            "Custom": self.custom_button,
        }
        selected_button = buttons.get(mode)

        blockers = [
            QSignalBlocker(self.auto_button),
            QSignalBlocker(self.max_button),
            QSignalBlocker(self.quiet_button),
            QSignalBlocker(self.custom_button),
        ]
        self.mode_group.setExclusive(False)
        for button in buttons.values():
            button.setChecked(button is selected_button)
        self.mode_group.setExclusive(True)
        del blockers

        cpu_target = fan_state.get("cpu_target")
        gpu_target = fan_state.get("gpu_target")
        if mode != "Auto" and cpu_target is not None and gpu_target is not None:
            cpu_blocker = QSignalBlocker(self.cpu_slider)
            gpu_blocker = QSignalBlocker(self.gpu_slider)
            self.cpu_slider.setValue(max(self.cpu_slider.minimum(), cpu_target))
            self.gpu_slider.setValue(max(self.gpu_slider.minimum(), gpu_target))
            del cpu_blocker
            del gpu_blocker
            self._update_slider_labels()
            self.cpu_percent = cpu_target
            self.gpu_percent = gpu_target
            self._refresh_visuals()

        self.mode = mode
        self.fan_state_initialized = True

    def _request_profile_read(self):
        self._request_profile_operation(None)

    def _request_profile_change(self, profile):
        if self.profile_busy:
            return
        if profile == self.current_acer_profile:
            profile_name = self.profile_controller.PROFILE_NAMES.get(profile, str(profile))
            self._set_status(f"Perfil Acer ja esta em {profile_name}.")
            return
        self._set_status("Aplicando perfil Acer...")
        self._request_profile_operation(profile)

    def _request_profile_operation(self, profile):
        if self.profile_busy:
            return

        self.profile_busy = True
        self._set_profile_buttons_enabled(False)
        worker = threading.Thread(
            target=self._run_profile_operation_background,
            args=(profile,),
            daemon=True,
        )
        worker.start()

    def _run_profile_operation_background(self, profile):
        if profile is None:
            result = self.profile_controller.read_profile()
            result["operation"] = "read"
        else:
            result = self.profile_controller.set_profile(profile)
            result["operation"] = "write"
        self.profile_ready.emit(result)

    def _apply_profile_result(self, result):
        self.profile_busy = False
        tested_model = bool(result.get("tested_model"))

        if not result.get("ok"):
            self._set_profile_buttons_enabled(self.acer_profile_supported)
            self._select_profile_button(self.current_acer_profile)
            self._set_status(result.get("error", "Falha ao acessar o perfil Acer."))
            return

        profile = result["profile"]
        self.current_acer_profile = profile
        self.acer_profile_supported = tested_model
        self._set_profile_buttons_enabled(tested_model)
        self._select_profile_button(profile)

        if not tested_model:
            self._set_status(
                f"Perfil Acer detectado: {result['profile_name']}. "
                "Troca ainda nao validada neste modelo."
            )
            return

        if result.get("operation") == "write":
            self._set_status(f"Perfil Acer: {result['profile_name']} aplicado e confirmado.")
        else:
            self._set_status(f"Perfil Acer atual: {result['profile_name']}.")

    def _select_profile_button(self, profile):
        blocker_balanced = QSignalBlocker(self.balanced_profile_button)
        blocker_performance = QSignalBlocker(self.performance_profile_button)
        self.balanced_profile_button.setChecked(profile == 1)
        self.performance_profile_button.setChecked(profile == 4)
        del blocker_balanced
        del blocker_performance

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
        self.apply_manual_fans(self.cpu_slider.value(), self.gpu_slider.value(), "Custom")

    def set_auto(self):
        auto_ok = self.run_command("0x22", "0x04") and self.run_command("0x21", "0x10")
        if auto_ok:
            self.mode = "Auto"
            self.cpu_percent = 45
            self.gpu_percent = 45
            self._refresh_visuals()
            self._set_status("Auto: controle devolvido para a BIOS.")


if __name__ == "__main__":
    is_primary_instance, instance_mutex = acquire_single_instance()
    if not is_primary_instance:
        focus_existing_instance()
        sys.exit(0)

    try:
        app = QApplication(sys.argv)
        ex = ForcaNitroApp()
        ex.show()
        exit_code = app.exec()
    finally:
        release_single_instance(instance_mutex)

    sys.exit(exit_code)
