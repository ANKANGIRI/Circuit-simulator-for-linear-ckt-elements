import sys
import math
import re
import os
import numpy as np
import subprocess
# --- NEW IMPORTS FOR THREADING ---
from PyQt6.QtCore import Qt, QRectF, QPointF, QLineF, QThread, QObject, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene,
    QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QToolBar,
    QMessageBox, QFileDialog, QInputDialog, QLabel, QGraphicsItem,
    QGraphicsPathItem, QSplitter, QGraphicsTextItem,
    QDialog, QLineEdit, QComboBox, QDialogButtonBox, QTabWidget, QFormLayout
)
from PyQt6.QtGui import QPen, QColor, QBrush, QPainter, QPainterPath, QFont, QLinearGradient

# ---------- NEW: SIMULATION WORKER THREAD ----------

class SimulationWorker(QObject):
    """
    Runs the simulation in a separate thread to keep the GUI responsive.
    """
    # Signals to emit back to the main thread
    finished = pyqtSignal(str, str) # stdout, stderr
    error = pyqtSignal(str)         # Python exception string
    
    def __init__(self, cmd):
        super().__init__()
        self.cmd = cmd

    @pyqtSlot()
    def run(self):
        """Execute the simulation command."""
        try:
            # Run the subprocess
            result = subprocess.run(
                self.cmd,
                capture_output=True,
                text=True,
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            # Emit the results
            self.finished.emit(result.stdout, result.stderr)
            
        except subprocess.CalledProcessError as e:
            # The backend script failed (non-zero exit code)
            self.finished.emit(e.stdout, e.stderr)
        except FileNotFoundError as e:
            self.error.emit(
                "Error: Backend script not found.\n"
                "Make sure 'ckt_sim_backend.py' is in the same directory.\n"
                f"{e}"
            )
        except Exception as e:
            # Other Python error
            self.error.emit(f"An unexpected error occurred:\n{e}")

# ---------- (GridGraphicsView class is UNCHANGED) ----------
class GridGraphicsView(QGraphicsView):
    """A QGraphicsView that draws a dotted grid background."""
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.grid_size = 30
        self.grid_color = QColor("#A5A9AC")

    def drawBackground(self, painter, rect):
        """Override to draw the grid."""
        super().drawBackground(painter, rect)
        
        # Get the visible area
        left = int(rect.left())
        right = int(rect.right())
        top = int(rect.top())
        bottom = int(rect.bottom())

        # Find the first grid lines
        first_left = left - (left % self.grid_size)
        first_top = top - (top % self.grid_size)

        # Create a QPen for the grid
        pen = QPen(self.grid_color)
        pen.setWidth(2)
        painter.setPen(pen)

        # Draw dots
        points = []
        for x in range(first_left, right, self.grid_size):
            for y in range(first_top, bottom, self.grid_size):
                points.append(QPointF(x, y))
        
        if points:
            painter.drawPoints(points)

# ---------- (ComponentValueDialog class is UNCHANGED) ----------
class ComponentValueDialog(QDialog):
    """Custom dialog for setting R, L, C values with multipliers."""
    def __init__(self, current_value, unit, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Set Component Value ({unit})")
        self.unit = unit
        
        self.multipliers = {
            "p (pico, 1e-12)": 1e-12,
            "n (nano, 1e-9)": 1e-9,
            "µ (micro, 1e-6)": 1e-6,
            "m (milli, 1e-3)": 1e-3,
            " (none)": 1.0,
            "k (kilo, 1e3)": 1e3,
            "M (Mega, 1e6)": 1e6,
            "G (Giga, 1e9)": 1e9
        }
        
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        self.value_edit = QLineEdit()
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(self.multipliers.keys())
        
        # Try to parse the current value
        try:
            val_float = float(current_value)
            if val_float == 0:
                mult_key = " (none)"
            elif abs(val_float) >= 1e9: mult_key = "G (Giga, 1e9)"
            elif abs(val_float) >= 1e6: mult_key = "M (Mega, 1e6)"
            elif abs(val_float) >= 1e3: mult_key = "k (kilo, 1e3)"
            elif abs(val_float) >= 1: mult_key = " (none)"
            elif abs(val_float) >= 1e-3: mult_key = "m (milli, 1e-3)"
            elif abs(val_float) >= 1e-6: mult_key = "µ (micro, 1e-6)"
            elif abs(val_float) >= 1e-9: mult_key = "n (nano, 1e-9)"
            else: mult_key = "p (pico, 1e-12)"
            
            self.value_edit.setText(f"{val_float / self.multipliers[mult_key]:.4g}")
            self.unit_combo.setCurrentText(mult_key)
        except ValueError:
            self.value_edit.setText("1") # Default
            self.unit_combo.setCurrentText("k (kilo, 1e3)" if unit == "Ω" else " (none)")

        form_layout.addRow("Value:", self.value_edit)
        form_layout.addRow("Multiplier:", self.unit_combo)
        layout.addLayout(form_layout)
        
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_values(self):
        try:
            val = float(self.value_edit.text())
            mult_key = self.unit_combo.currentText()
            multiplier = self.multipliers[mult_key]
            
            base_value = val * multiplier
            display_mult = mult_key.split(' ')[0]
            if display_mult == "(none)": display_mult = ""
            
            display_value = f"{self.value_edit.text()}{display_mult}{self.unit}"
            base_value_str = f"{base_value:.12g}" 
            
            return base_value_str, display_value
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter a valid number.")
            return None, None

# ---------- (SourceValueDialog class is UNCHANGED) ----------
class SourceValueDialog(QDialog):
    """Custom dialog for setting V, I values (DC or advanced function)."""
    def __init__(self, current_value, unit, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Set Source Value ({unit})")
        self.unit = unit
        
        self.multipliers = {
            "p (pico, 1e-12)": 1e-12,
            "n (nano, 1e-9)": 1e-9,
            "µ (micro, 1e-6)": 1e-6,
            "m (milli, 1e-3)": 1e-3,
            " (none)": 1.0,
            "k (kilo, 1e3)": 1e3,
            "M (Mega, 1e6)": 1e6,
            "G (Giga, 1e9)": 1e9
        }
        
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        
        # --- DC Tab ---
        dc_widget = QWidget()
        dc_layout = QFormLayout(dc_widget)
        self.value_edit = QLineEdit()
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(self.multipliers.keys())
        dc_layout.addRow("DC Value:", self.value_edit)
        dc_layout.addRow("Multiplier:", self.unit_combo)
        self.tabs.addTab(dc_widget, "Simple (DC)")

        # --- Advanced Tab ---
        adv_widget = QWidget()
        adv_layout = QVBoxLayout(adv_widget)
        adv_layout.addWidget(QLabel("Enter function of time 't':"))
        self.func_edit = QLineEdit()
        self.func_edit.setPlaceholderText("e.g., 5*sin(2*pi*10*t) - 0.1*t^2")
        font = self.func_edit.font()
        font.setPointSize(12)
        self.func_edit.setFont(font)
        adv_layout.addWidget(self.func_edit)
        self.tabs.addTab(adv_widget, "Advanced (Function)")
        
        layout.addWidget(self.tabs)
        
        if any(c in current_value for c in 't*+-/()') and not current_value.replace('.','',1).replace('e-','',1).replace('e+','',1).isdigit():
            self.tabs.setCurrentIndex(1)
            self.func_edit.setText(current_value)
            self.value_edit.setText("0")
            self.unit_combo.setCurrentText(" (none)")
        else:
            try:
                val_float = float(current_value)
                if val_float == 0:
                    mult_key = " (none)"
                elif abs(val_float) >= 1e9: mult_key = "G (Giga, 1e9)"
                elif abs(val_float) >= 1e6: mult_key = "M (Mega, 1e6)"
                elif abs(val_float) >= 1e3: mult_key = "k (kilo, 1e3)"
                elif abs(val_float) >= 1: mult_key = " (none)"
                elif abs(val_float) >= 1e-3: mult_key = "m (milli, 1e-3)"
                elif abs(val_float) >= 1e-6: mult_key = "µ (micro, 1e-6)"
                elif abs(val_float) >= 1e-9: mult_key = "n (nano, 1e-9)"
                else: mult_key = "p (pico, 1e-12)"
                
                self.value_edit.setText(f"{val_float / self.multipliers[mult_key]:.4g}")
                self.unit_combo.setCurrentText(mult_key)
            except ValueError:
                self.value_edit.setText(current_value)
                self.unit_combo.setCurrentText(" (none)")
            self.tabs.setCurrentIndex(0)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_values(self):
        if self.tabs.currentIndex() == 0: # DC Tab
            try:
                val = float(self.value_edit.text())
                mult_key = self.unit_combo.currentText()
                multiplier = self.multipliers[mult_key]
                
                base_value = val * multiplier
                display_mult = mult_key.split(' ')[0]
                if display_mult == "(none)": display_mult = ""
                
                display_value = f"{self.value_edit.text()}{display_mult}{self.unit}"
                base_value_str = f"{base_value:.12g}"
                
                return base_value_str, display_value
            except ValueError:
                QMessageBox.warning(self, "Invalid Input", "Please enter a valid number for DC value.")
                return None, None
        else: # Advanced Tab
            func_str = self.func_edit.text()
            if not func_str:
                QMessageBox.warning(self, "Invalid Input", "Function string cannot be empty.")
                return None, None
            return func_str, func_str

# ---------- (BaseComponent class is UNCHANGED) ----------
class BaseComponent(QGraphicsPathItem):
    def __init__(self):
        super().__init__()
        self.component_type = "Base"
        self.value = ""
        self.display_value = ""
        self.component_id = None
        self.terminals = []
        self.rotation_angle = 0
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.hovered = False
        self.parent_simulator = None
        
        # store default pen
        self.default_pen = QPen(QColor("#2C3E50"), 2)

    def hoverEnterEvent(self, event):
        self.hovered = True
        super().setPen(QPen(QColor("#FF6B35"), 3))
        self.update()
        
    def hoverLeaveEvent(self, event):
        self.hovered = False
        self.update_pen_color()
    
    def setPen(self, pen):
        if not self.hovered:
            self.default_pen = pen
        super().setPen(pen)

    def update_pen_color(self):
        if hasattr(self, 'default_pen'):
            super().setPen(self.default_pen)
        else:
            super().setPen(QPen(QColor("#2C3E50"), 2))

    def mousePressEvent(self, event):
        if self.parent_simulator and self.parent_simulator.wiring_mode:
            event.accept()
        else:
            super().mousePressEvent(event)
    
    def mouseDoubleClickEvent(self, event):
        if self.component_type in ["Ground", "Voltage Probe", "Current Probe"]:
            return
            
        dialog = None
        if self.component_type in ["Resistor", "Capacitor", "Inductor"]:
            unit_map = {"Resistor": "Ω", "Capacitor": "F", "Inductor": "H"}
            dialog = ComponentValueDialog(self.value, unit_map[self.component_type], self.parent_simulator)
        
        elif self.component_type in ["Voltage Source", "Current Source"]:
            unit_map = {"Voltage Source": "V", "Current Source": "A"}
            dialog = SourceValueDialog(self.value, unit_map[self.component_type], self.parent_simulator)

        if dialog and dialog.exec() == QDialog.DialogCode.Accepted:
            base_value, display_value = dialog.get_values()
            if base_value is not None:
                self.value = base_value
                self.display_value = display_value
                self.update_label()
    
    def rotate_component(self):
        self.rotation_angle = (self.rotation_angle + 90) % 360
        self.setRotation(self.rotation_angle)
        
    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            if self.scene():
                for item in list(self.scene().items()):
                    if isinstance(item, WireItem):
                        if item.start_component == self or item.end_component == self:
                            item.update_path()
        return super().itemChange(change, value)

    def update_label(self):
        pass

# ---------- (ResistorItem class is UNCHANGED) ----------
class ResistorItem(BaseComponent):
    def __init__(self):
        super().__init__()
        self.component_type = "Resistor"
        self.value = "1000"
        self.display_value = "1kΩ"
        self.width = 100
        self.height = 40
        
        path = QPainterPath()
        path.moveTo(0, 20); path.lineTo(15, 20)
        points = [(20, 10), (30, 30), (40, 10), (50, 30), (60, 10), (70, 30), (80, 10), (85, 20)]
        for x, y in points: path.lineTo(x, y)
        path.lineTo(100, 20)
        
        self.setPath(path)
        self.setPen(QPen(QColor("#2C3E50"), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        
        self.text_item = QGraphicsTextItem("R = 1kΩ", self)
        self.text_item.setPos(25, -25)
        self.text_item.setDefaultTextColor(QColor("#2C3E50"))
        font = QFont("Arial", 10, QFont.Weight.Bold)
        self.text_item.setFont(font)
        
        self.terminals = [QPointF(0, 20), QPointF(100, 20)]
    
    def update_label(self):
        self.text_item.setPlainText(f"R{self.component_id} = {self.display_value}")

    def hoverLeaveEvent(self, event):
        self.hovered = False
        self.setPen(QPen(QColor("#2C3E50"), 2.5))
        self.update()

# ---------- (CapacitorItem class is UNCHANGED) ----------
class CapacitorItem(BaseComponent):
    def __init__(self):
        super().__init__()
        self.component_type = "Capacitor"
        self.value = "10e-6"
        self.display_value = "10µF"
        
        path = QPainterPath()
        path.moveTo(0, 30); path.lineTo(35, 30)
        path.moveTo(35, 10); path.lineTo(35, 50)
        path.moveTo(45, 10); path.lineTo(45, 50)
        path.moveTo(45, 30); path.lineTo(80, 30)
        
        self.setPath(path)
        self.setPen(QPen(QColor("#2C3E50"), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        
        self.text_item = QGraphicsTextItem("C = 10µF", self)
        self.text_item.setPos(10, -25)
        self.text_item.setDefaultTextColor(QColor("#2C3E50"))
        font = QFont("Arial", 10, QFont.Weight.Bold)
        self.text_item.setFont(font)
        
        self.terminals = [QPointF(0, 30), QPointF(80, 30)]
    
    def update_label(self):
        self.text_item.setPlainText(f"C{self.component_id} = {self.display_value}")

    def hoverLeaveEvent(self, event):
        self.hovered = False
        self.setPen(QPen(QColor("#2C3E50"), 2.5))
        self.update()

# ---------- (InductorItem class is UNCHANGED) ----------
class InductorItem(BaseComponent):
    def __init__(self):
        super().__init__()
        self.component_type = "Inductor"
        self.value = "10e-3"
        self.display_value = "10mH"
        
        path = QPainterPath()
        path.moveTo(0, 25); path.lineTo(15, 25)
        for i in range(4):
            x_start = 15 + i * 15
            path.arcTo(x_start, 10, 15, 30, 180, -180)
        path.lineTo(90, 25)
        
        self.setPath(path)
        self.setPen(QPen(QColor("#2C3E50"), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        
        self.text_item = QGraphicsTextItem("L = 10mH", self)
        self.text_item.setPos(20, -25)
        self.text_item.setDefaultTextColor(QColor("#2C3E50"))
        font = QFont("Arial", 10, QFont.Weight.Bold)
        self.text_item.setFont(font)
        
        self.terminals = [QPointF(0, 25), QPointF(90, 25)]
    
    def update_label(self):
        self.text_item.setPlainText(f"L{self.component_id} = {self.display_value}")

    def hoverLeaveEvent(self, event):
        self.hovered = False
        self.setPen(QPen(QColor("#2C3E50"), 2.5))
        self.update()

# ---------- (VoltageSourceItem class is UNCHANGED) ----------
class VoltageSourceItem(BaseComponent):
    def __init__(self):
        super().__init__()
        self.component_type = "Voltage Source"
        self.value = "5"
        self.display_value = "5V"
        
        path = QPainterPath()
        path.addEllipse(20, 10, 40, 40)
        path.moveTo(35, 30); path.lineTo(45, 30)
        path.moveTo(40, 25); path.lineTo(40, 35)
        path.moveTo(35, 45); path.lineTo(45, 45)
        path.moveTo(40, 0); path.lineTo(40, 10)
        path.moveTo(40, 50); path.lineTo(40, 60)
        
        self.setPath(path)
        self.setPen(QPen(QColor("#8E44AD"), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        
        self.text_item = QGraphicsTextItem("V = 5V", self)
        self.text_item.setPos(10, -20)
        self.text_item.setDefaultTextColor(QColor("#8E44AD"))
        font = QFont("Arial", 10, QFont.Weight.Bold)
        self.text_item.setFont(font)
        
        self.terminals = [QPointF(40, 0), QPointF(40, 60)]
    
    def update_label(self):
        self.text_item.setPlainText(f"V{self.component_id} = {self.display_value}")

    def hoverLeaveEvent(self, event):
        self.hovered = False
        self.setPen(QPen(QColor("#8E44AD"), 2.5))
        self.update()

# ---------- (CurrentSourceItem class is UNCHANGED) ----------
class CurrentSourceItem(BaseComponent):
    def __init__(self):
        super().__init__()
        self.component_type = "Current Source"
        self.value = "1"
        self.display_value = "1A"
        
        path = QPainterPath()
        path.addEllipse(20, 10, 40, 40)
        path.moveTo(40, 25); path.lineTo(40, 45)
        path.moveTo(35, 38); path.lineTo(40, 45); path.lineTo(45, 38)
        path.moveTo(40, 0); path.lineTo(40, 10)
        path.moveTo(40, 50); path.lineTo(40, 60)
        
        self.setPath(path)
        self.setPen(QPen(QColor("#E74C3C"), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        
        self.text_item = QGraphicsTextItem("I = 1A", self)
        self.text_item.setPos(10, -20)
        self.text_item.setDefaultTextColor(QColor("#E74C3C"))
        font = QFont("Arial", 10, QFont.Weight.Bold)
        self.text_item.setFont(font)
        
        self.terminals = [QPointF(40, 0), QPointF(40, 60)]
    
    def update_label(self):
        self.text_item.setPlainText(f"I{self.component_id} = {self.display_value}")

    def hoverLeaveEvent(self, event):
        self.hovered = False
        self.setPen(QPen(QColor("#E74C3C"), 2.5))
        self.update()

# ---------- (GroundItem class is UNCHANGED) ----------
class GroundItem(BaseComponent):
    def __init__(self):
        super().__init__()
        self.component_type = "Ground"
        self.value = "GND"; self.display_value = "GND"
        
        path = QPainterPath()
        path.moveTo(30, 0); path.lineTo(30, 20)
        path.moveTo(10, 20); path.lineTo(50, 20)
        path.moveTo(17, 28); path.lineTo(43, 28)
        path.moveTo(24, 36); path.lineTo(36, 36)
        
        self.setPath(path)
        self.setPen(QPen(QColor("#16A085"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        
        self.text_item = QGraphicsTextItem("GND", self)
        self.text_item.setPos(5, 40)
        self.text_item.setDefaultTextColor(QColor("#16A085"))
        font = QFont("Arial", 9, QFont.Weight.Bold)
        self.text_item.setFont(font)
        
        self.terminals = [QPointF(30, 0)]
        
    def update_label(self):
        self.text_item.setPlainText(f"GND")

    def hoverLeaveEvent(self, event):
        self.hovered = False
        self.setPen(QPen(QColor("#16A085"), 3))
        self.update()

# ---------- (VoltageProbeItem class is UNCHANGED) ----------
class VoltageProbeItem(BaseComponent):
    def __init__(self):
        super().__init__()
        self.component_type = "Voltage Probe"
        self.value = "V_PROBE"; self.display_value = "V?"
        
        path = QPainterPath()
        path.moveTo(30, 0)
        path.lineTo(30, 10)
        path.addEllipse(10, 10, 40, 40)
        
        text_font = QFont("Arial", 16, QFont.Weight.Bold)
        text_path = QPainterPath()
        text_path.addText(18, 39, text_font, "V?")
        path.addPath(text_path)
        
        path.moveTo(30, 50)
        path.lineTo(30, 60)
        
        self.setPath(path)
        self.setPen(QPen(QColor("#3498DB"), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        
        self.text_item = QGraphicsTextItem("V_P", self)
        self.text_item.setPos(5, -20)
        self.text_item.setDefaultTextColor(QColor("#3498DB"))
        font = QFont("Arial", 10, QFont.Weight.Bold)
        self.text_item.setFont(font)
        
        self.terminals = [QPointF(30, 0), QPointF(30, 60)]
        
    def update_label(self):
        self.text_item.setPlainText(f"VP{self.component_id}")

    def hoverLeaveEvent(self, event):
        self.hovered = False
        self.setPen(QPen(QColor("#3498DB"), 2.5))
        self.update()

# ---------- (CurrentProbeItem class is UNCHANGED) ----------
class CurrentProbeItem(BaseComponent):
    def __init__(self):
        super().__init__()
        self.component_type = "Current Probe"
        self.value = "A_PROBE"; self.display_value = "A?"
        
        path = QPainterPath()
        path.moveTo(0, 30); path.lineTo(10, 30)
        path.addEllipse(10, 10, 40, 40)
        
        text_font = QFont("Arial", 16, QFont.Weight.Bold)
        text_path = QPainterPath()
        text_path.addText(21, 38, text_font, "A")
        path.addPath(text_path)
        
        path.moveTo(50, 30)
        path.lineTo(60, 30)
        
        self.setPath(path)
        self.setPen(QPen(QColor("#F39C12"), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        
        self.text_item = QGraphicsTextItem("A_P", self)
        self.text_item.setPos(5, -20)
        self.text_item.setDefaultTextColor(QColor("#F39C12"))
        font = QFont("Arial", 10, QFont.Weight.Bold)
        self.text_item.setFont(font)
        
        self.terminals = [QPointF(0, 30), QPointF(60, 30)]
        
    def update_label(self):
        self.text_item.setPlainText(f"AP{self.component_id}")

    def hoverLeaveEvent(self, event):
        self.hovered = False
        self.setPen(QPen(QColor("#F39C12"), 2.5))
        self.update()

# ---------- (WireItem class is UNCHANGED) ----------
class WireItem(QGraphicsPathItem):
    def __init__(self, start_component=None, start_terminal=None, end_component=None, end_terminal=None):
        super().__init__()
        self.component_type = "Wire"
        self.start_component = start_component
        self.start_terminal = start_terminal
        self.end_component = end_component
        self.end_terminal = end_terminal
        self.temp_end_point = None
        self.path = QPainterPath()
        self.routing_style = 0 
        
        self.setPen(QPen(QColor("#2C3E50"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        self.setZValue(-1)
        self.setAcceptHoverEvents(True)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.routing_style = (self.routing_style + 1) % 2
            self.update_path()
            event.accept()
        else:
            super().mousePressEvent(event)
            
    def hoverEnterEvent(self, event):
        self.setPen(QPen(QColor("#FF6B35"), 4))
        self.update()
        
    def hoverLeaveEvent(self, event):
        self.setPen(QPen(QColor("#2C3E50"), 3))
        self.update()

    def get_terminal_scene_pos(self, component, terminal_index):
        if not component:
            return QPointF()
        terminal_point = component.terminals[terminal_index]
        return component.mapToScene(
            component.mapFromItem(component, terminal_point)
        )

    def update_path(self):
        self.path = QPainterPath()
        
        if not (self.start_component and self.start_terminal is not None):
            return
        
        start_pos = self.get_terminal_scene_pos(self.start_component, self.start_terminal)
            
        if self.end_component and self.end_terminal is not None:
            end_pos = self.get_terminal_scene_pos(self.end_component, self.end_terminal)
        elif self.temp_end_point:
            end_pos = self.temp_end_point
        else:
            return
        
        self.path.moveTo(start_pos)
        
        if self.routing_style == 0: # HV
            self.path.lineTo(end_pos.x(), start_pos.y())
        else: # VH
            self.path.lineTo(start_pos.x(), end_pos.y())
            
        self.path.lineTo(end_pos)
        self.setPath(self.path)
    
    def set_temp_end(self, point):
        self.temp_end_point = point
        self.update_path()
    
    def finalize(self, end_component, end_terminal):
        self.end_component = end_component
        self.end_terminal = end_terminal
        self.temp_end_point = None
        self.update_path()

# ---------- MAIN APPLICATION (MODIFIED) ----------
class CircuitSimulator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Advanced Circuit Simulator - Professional Edition")
        self.setGeometry(50, 50, 1400, 900)
        self.setStyleSheet("""
            QMainWindow { background-color: #ECF0F1; }
            QPushButton {
                background-color: #3498DB; color: white; border: none;
                padding: 8px 15px; border-radius: 5px;
                font-size: 12px; font-weight: bold;
            }
            QPushButton:hover { background-color: #2980B9; }
            QPushButton:pressed { background-color: #21618C; }
            QPushButton:disabled { background-color: #95A5A6; }
            QToolBar { background-color: #34495E; spacing: 5px; padding: 5px; }
            QLabel { color: #2C3E50; font-size: 11px; }
            QDialog { background-color: #ECF0F1; }
            QLineEdit { padding: 5px; border: 1px solid #BDC3C7; border-radius: 3px; font-size: 12px; }
            QComboBox { padding: 5px; border: 1px solid #BDC3C7; border-radius: 3px; font-size: 12px; }
            QTabWidget::pane { border-top: 2px solid #3498DB; }
            QTabBar::tab {
                background: #ECF0F1; border: 1px solid #BDC3C7; padding: 8px 15px;
                border-top-left-radius: 4px; border-top-right-radius: 4px;
            }
            QTabBar::tab:selected { background: #3498DB; color: white; font-weight: bold; }
        """)
        
        # Wiring state
        self.wiring_mode = False
        self.current_wire = None
        self.wire_start_component = None
        self.wire_start_terminal = None
        self.wiring_button = None
        self.highlighted_terminal_item = None
        self.highlighted_terminal = None
        
        # --- NEW: Threading members ---
        self.simulation_thread = None
        self.simulation_worker = None
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        left_panel = self.create_component_panel()
        splitter.addWidget(left_panel)
        
        # Center - Canvas
        canvas_widget = QWidget()
        canvas_layout = QVBoxLayout(canvas_widget)
        
        self.create_toolbar()
        
        self.scene = QGraphicsScene()
        self.scene.setSceneRect(0, 0, 1200, 800)
        self.scene.setBackgroundBrush(QBrush(QColor("#FFFFFF")))
        
        self.view = GridGraphicsView(self.scene, canvas_widget)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.view.setStyleSheet("border: 2px solid #BDC3C7; background-color: #FFFFFF;")
        self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        
        self.view.setMouseTracking(True)
        self.view.viewport().installEventFilter(self)
        
        canvas_layout.addWidget(self.view)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        clear_btn = QPushButton("🗑️ Clear All")
        clear_btn.clicked.connect(self.clear_scene)
        clear_btn.setStyleSheet("background-color: #E74C3C;")
        button_layout.addWidget(clear_btn)
        
        delete_btn = QPushButton("❌ Delete Component")
        delete_btn.clicked.connect(self.delete_selected)
        delete_btn.setStyleSheet("background-color: #E67E22;")
        button_layout.addWidget(delete_btn)
        
        button_layout.addStretch()
        
        sim_label = QLabel("Simulate for:")
        sim_label.setStyleSheet("font-size: 12px; margin-right: 5px;")
        button_layout.addWidget(sim_label)
        
        self.sim_time_edit = QLineEdit("10")
        self.sim_time_edit.setFixedWidth(60)
        self.sim_time_edit.setStyleSheet("padding: 6px; font-size: 12px; border: 1px solid #BDC3C7; border-radius: 4px;")
        button_layout.addWidget(self.sim_time_edit)
        
        self.sim_time_unit = QComboBox()
        self.sim_time_unit.addItems(["s", "ms", "µs"])
        self.sim_time_unit.setStyleSheet("padding: 5px; font-size: 12px; border: 1px solid #BDC3C7; border-radius: 4px;")
        button_layout.addWidget(self.sim_time_unit)
        
        sim_step_label = QLabel("Step:")
        sim_step_label.setStyleSheet("font-size: 12px; margin-left: 10px; margin-right: 5px;")
        button_layout.addWidget(sim_step_label)
        
        self.sim_step_edit = QLineEdit("1e-5")
        self.sim_step_edit.setFixedWidth(60)
        self.sim_step_edit.setStyleSheet("padding: 6px; font-size: 12px; border: 1px solid #BDC3C7; border-radius: 4px;")
        button_layout.addWidget(self.sim_step_edit)

        sim_step_unit_label = QLabel("s")
        sim_step_unit_label.setStyleSheet("font-size: 12px; margin-right: 5px;")
        button_layout.addWidget(sim_step_unit_label)
        
        # --- MODIFIED: Store simulate_btn as a class member ---
        self.simulate_btn = QPushButton("⚡ Simulate")
        self.simulate_btn.clicked.connect(self.run_simulation)
        self.simulate_btn.setStyleSheet("background-color: #3498DB; margin-left: 10px;")
        button_layout.addWidget(self.simulate_btn)

        # --- NEW: Update Files button (single new UI element) ---
        self.update_files_btn = QPushButton("💾 Update Files")
        self.update_files_btn.clicked.connect(self.update_files)
        self.update_files_btn.setStyleSheet("background-color: #1ABC9C; margin-left: 5px;")
        button_layout.addWidget(self.update_files_btn)
        
        button_layout.addStretch()
        
        export_btn = QPushButton("📄 Export Netlist")
        export_btn.clicked.connect(self.export_netlist)
        export_btn.setStyleSheet("background-color: #27AE60;")
        button_layout.addWidget(export_btn)
        
        canvas_layout.addLayout(button_layout)
        
        splitter.addWidget(canvas_widget)
        main_layout.addWidget(splitter)
        
        self.component_counter = {}
    
    # ---------- (create_component_panel class is UNCHANGED) ----------
    def create_component_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        title = QLabel("📦 Component Library")
        title.setStyleSheet("""
            font-size: 14px; 
            font-weight: bold; 
            color: #ECF0F1; 
            padding: 10px;
            background-color: #2C3E50;
            border-radius: 5px;
        """)
        layout.addWidget(title)
        
        components = [
            ("Resistor", "🔲"),
            ("Capacitor", "⚡"),
            ("Inductor", "🌀"),
            ("Voltage Source", "⚡"),
            ("Current Source", "🔌"),
            ("Ground", "⏚"),
            ("Voltage Probe", "Ⓥ"),
            ("Current Probe", "Ⓐ"),
        ]
        
        for comp_name, icon in components:
            btn = QPushButton(f"{icon} {comp_name}")
            btn.clicked.connect(lambda checked, c=comp_name.lower().replace(" ", "_"): self.add_component(c))
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #34495E;
                    color: #ECF0F1;
                    border: 1px solid #5D6D7E;
                    padding: 10px;
                    border-radius: 5px;
                    text-align: left;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #4A6A8B;
                    border: 1px solid #7F8C8D;
                }
                QPushButton:pressed {
                    background-color: #2C3E50;
                }
            """)
            layout.addWidget(btn)
        
        self.wiring_button = QPushButton("🔌 Wire Mode (OFF)")
        self.wiring_button.clicked.connect(self.toggle_wiring_mode)
        self.wiring_button.setStyleSheet("""
            QPushButton {
                background-color: #95A5A6; color: #ECF0F1; border: 2px solid #7F8C8D;
                padding: 10px; border-radius: 5px; text-align: left;
                font-size: 12px; font-weight: bold;
            }
            QPushButton:hover { background-color: #7F8C8D; }
        """)
        layout.addWidget(self.wiring_button)
        
        layout.addStretch()
        panel.setMaximumWidth(250)
        panel.setStyleSheet("background-color: #2C3E50; padding: 5px;")
        return panel
    
    # ---------- (create_toolbar class is UNCHANGED) ----------
    def create_toolbar(self):
        toolbar = QToolBar("Tools")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        zoom_in = QPushButton("🔍+ Zoom In")
        zoom_in.clicked.connect(lambda: self.view.scale(1.2, 1.2))
        toolbar.addWidget(zoom_in)
        
        zoom_out = QPushButton("🔍− Zoom Out")
        zoom_out.clicked.connect(lambda: self.view.scale(0.8, 0.8))
        toolbar.addWidget(zoom_out)
        
        reset_view = QPushButton("🎯 Reset View")
        reset_view.clicked.connect(lambda: self.view.resetTransform())
        toolbar.addWidget(reset_view)
        
        toolbar.addSeparator()
        
        rotate_btn = QPushButton("🔄 Rotate Component")
        rotate_btn.clicked.connect(self.rotate_selected)
        rotate_btn.setStyleSheet("background-color: #9B59B6;")
        toolbar.addWidget(rotate_btn)
    
    # ---------- (add_component class is UNCHANGED) ----------
    def add_component(self, component_type):
        component = None
        
        if component_type == "resistor": component = ResistorItem()
        elif component_type == "capacitor": component = CapacitorItem()
        elif component_type == "inductor": component = InductorItem()
        elif component_type == "voltage_source": component = VoltageSourceItem()
        elif component_type == "current_source": component = CurrentSourceItem()
        elif component_type == "ground": component = GroundItem()
        elif component_type == "voltage_probe": component = VoltageProbeItem()
        elif component_type == "current_probe": component = CurrentProbeItem()
        
        if component:
            component.parent_simulator = self
            
            num_items = len([item for item in self.scene.items() if isinstance(item, BaseComponent)])
            row = num_items // 5
            col = num_items % 5
            x = 100 + col * 150
            y = 100 + row * 120
            
            component.setPos(x, y)
            
            comp_type = component.component_type
            if comp_type not in self.component_counter:
                self.component_counter[comp_type] = 0
            self.component_counter[comp_type] += 1
            component.component_id = self.component_counter[comp_type]
            
            component.update_label()
            self.scene.addItem(component)
    
    # ---------- (toggle_wiring_mode class is UNCHANGED) ----------
    def toggle_wiring_mode(self):
        self.wiring_mode = not self.wiring_mode
        if self.wiring_mode:
            self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.view.setCursor(Qt.CursorShape.CrossCursor)
            self.wiring_button.setText("🔌 Wire Mode (ON)")
            self.wiring_button.setStyleSheet("""
                QPushButton {
                    background-color: #27AE60; color: #ECF0F1; border: 2px solid #229954;
                    padding: 10px; border-radius: 5px; text-align: left;
                    font-size: 12px; font-weight: bold;
                }
                QPushButton:hover { background-color: #229954; }
            """)
            QMessageBox.information(self, "Wiring Mode", 
                                  "✓ Wiring Mode Activated!\n\n"
                                  "1. Click near a component's terminal to start a wire.\n"
                                  "2. Move your mouse to the destination.\n"
                                  "3. Click near another terminal to connect.\n\n"
                                  "• Click in empty space or press ESC to cancel.\n"
                                  "• Toggle the button to exit wiring mode.")
        else:
            self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            self.view.setCursor(Qt.CursorShape.ArrowCursor)
            self.wiring_button.setText("🔌 Wire Mode (OFF)")
            self.wiring_button.setStyleSheet("""
                QPushButton {
                    background-color: #95A5A6; color: #ECF0F1; border: 2px solid #7F8C8D;
                    padding: 10px; border-radius: 5px; text-align: left;
                    font-size: 12px; font-weight: bold;
                }
                QPushButton:hover { background-color: #7F8C8D; }
            """)
            if self.current_wire:
                self.scene.removeItem(self.current_wire)
                self.current_wire = None
            self.wire_start_component = None
            self.clear_terminal_highlight()

    # ---------- (clear_terminal_highlight class is UNCHANGED) ----------
    def clear_terminal_highlight(self):
        if self.highlighted_terminal_item:
            self.scene.removeItem(self.highlighted_terminal_item)
            self.highlighted_terminal_item = None
            self.highlighted_terminal = None

    # ---------- (find_closest_terminal class is UNCHANGED) ----------
    def find_closest_terminal(self, scene_pos, tolerance=35):
        closest_terminal_info = None
        min_distance = tolerance
        all_components = [item for item in self.scene.items() if isinstance(item, BaseComponent)]
        
        for comp in all_components:
            for i, terminal_point in enumerate(comp.terminals):
                terminal_pos = comp.mapToScene(
                    comp.mapFromItem(comp, terminal_point)
                )
                distance = (terminal_pos - scene_pos).manhattanLength()
                
                if distance < min_distance:
                    min_distance = distance
                    closest_terminal_info = (comp, i, terminal_pos)
        
        return closest_terminal_info

    # ---------- (handle_component_click_by_terminal class is UNCHANGED) ----------
    def handle_component_click_by_terminal(self, component, closest_terminal):
        if not self.wire_start_component:
            self.wire_start_component = component
            self.wire_start_terminal = closest_terminal
            self.current_wire = WireItem(component, closest_terminal)
            self.scene.addItem(self.current_wire)
        else:
            self.current_wire.finalize(component, closest_terminal)
            self.wire_start_component = None
            self.current_wire = None
            self.clear_terminal_highlight()

    # ---------- (eventFilter class is UNCHANGED) ----------
    def eventFilter(self, obj, event):
        if obj == self.view.viewport() and self.wiring_mode:
            if event.type() == event.Type.MouseMove:
                pos = self.view.mapToScene(event.pos())
                
                closest_term_info = self.find_closest_terminal(pos)
                if closest_term_info:
                    component, term_index, term_pos = closest_term_info
                    if self.highlighted_terminal != (component, term_index):
                        self.clear_terminal_highlight()
                        
                        self.highlighted_terminal = (component, term_index)
                        self.highlighted_terminal_item = self.scene.addEllipse(
                            term_pos.x() - 6, term_pos.y() - 6, 12, 12,
                            QPen(QColor(0, 150, 255, 200), 3),
                            QBrush(QColor(0, 150, 255, 100))
                        )
                        self.highlighted_terminal_item.setZValue(10)
                else:
                    self.clear_terminal_highlight()

                if self.current_wire:
                    self.current_wire.set_temp_end(pos)
                return True
                
            elif event.type() == event.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    
                    pos = self.view.mapToScene(event.pos())
                    closest_term_info = self.find_closest_terminal(pos, 35)
                    
                    if closest_term_info:
                        comp, term_idx, _ = closest_term_info
                        self.handle_component_click_by_terminal(comp, term_idx)
                    else:
                        if self.current_wire:
                            self.scene.removeItem(self.current_wire)
                            self.current_wire = None
                            self.wire_start_component = None
                            
                    return True
        
        if obj == self.view.viewport() and not self.wiring_mode:
            if event.type() == event.Type.MouseMove:
                self.clear_terminal_highlight()
                
        return super().eventFilter(obj, event)

    # ---------- (keyPressEvent class is UNCHANGED) ----------
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if self.wiring_mode:
                if self.current_wire:
                    self.scene.removeItem(self.current_wire)
                    self.current_wire = None
                self.wire_start_component = None
                self.toggle_wiring_mode()
            elif self.scene.selectedItems():
                for item in self.scene.selectedItems():
                    item.setSelected(False)
    
    # ---------- (rotate_selected class is UNCHANGED) ----------
    def rotate_selected(self):
        selected_items = self.scene.selectedItems()
        if not selected_items:
            return
        
        all_items = list(self.scene.items())
        
        for item in selected_items:
            if hasattr(item, 'rotate_component'):
                item.rotate_component()
                
                for scene_item in all_items:
                    if isinstance(scene_item, WireItem):
                        if scene_item.start_component == item or scene_item.end_component == item:
                            scene_item.update_path()
    
    # ---------- (delete_selected class is UNCHANGED) ----------
    def delete_selected(self):
        selected_items = self.scene.selectedItems()
        for item in selected_items:
            if item in self.scene.items():
                self.scene.removeItem(item)
    
    # ---------- (clear_scene class is UNCHANGED) ----------
    def clear_scene(self):
        reply = QMessageBox.question(
            self, 
            'Clear Circuit', 
            'Are you sure you want to clear all components?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.scene.clear()
            self.component_counter = {}
            QMessageBox.information(self, "Cleared", "All components cleared!")

    # --- NEW: Update Files handler (writes netlist, probes, time) ---
    def update_files(self):
        """
        Generate/overwrite netlist.txt, probes.txt, and time.txt
        using the current circuit and simulation settings.
        """
        # 1. Read and convert simulation time and step
        try:
            time_val = float(self.sim_time_edit.text())
            time_unit = self.sim_time_unit.currentText()
            time_step = float(self.sim_step_edit.text())
        except ValueError:
            QMessageBox.warning(
                self, "Invalid Time",
                "Please enter valid numbers for simulation time and step."
            )
            return

        # Convert end time to seconds according to unit
        t_end = time_val
        if time_unit == "ms":
            t_end = time_val * 1e-3
        elif time_unit == "µs":
            t_end = time_val * 1e-6

        # 2. Export netlist and probes (silent)
        success, has_probes = self.export_netlist(silent=True)
        if not success:
            # Errors such as "No Ground" are already shown inside export_netlist
            return

        # 3. Write time.txt
        try:
            with open("time.txt", "w") as f:
                # Simple format: two lines – t_end and time_step (both in seconds)
                f.write(f"{t_end}\n")
                f.write(f"{time_step}\n")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save time.txt:\n{e}")
            return

        # 4. Inform the user
        msg = (
            "Configuration files updated successfully:\n"
            "• netlist.txt\n"
            "• probes.txt\n"
            "• time.txt\n\n"
            f"Simulation time (t_end): {t_end} s\n"
            f"Time step (dt): {time_step} s"
        )
        if not has_probes:
            msg += (
                "\n\nWarning: No probes were found in the circuit.\n"
                "Simulation may run but produce no plotted outputs."
            )
        QMessageBox.information(self, "Files Updated", msg)
    
    # --- MODIFIED: Simulation function (now only runs backend, no config args) ---
    def run_simulation(self):
        """Runs the backend simulation using existing config files."""
        # Prevent starting a new simulation if one is already running
        if self.simulation_thread is not None:
            QMessageBox.warning(
                self,
                "Simulation in Progress",
                "Please wait for the current simulation to finish."
            )
            return

        # Ensure configuration files exist
        missing = []
        for fname in ("netlist.txt", "probes.txt", "time.txt"):
            if not os.path.exists(fname):
                missing.append(fname)

        if missing:
            QMessageBox.warning(
                self,
                "Configuration Missing",
                "The following configuration files are missing:\n"
                + "\n".join(f"• {m}" for m in missing)
                + "\n\nPlease click '💾 Update Files' before running the simulation."
            )
            return

        # 2. Prepare the backend command (no configuration arguments now)
        backend_script = "ckt_sim_backend.py"
        cmd = [sys.executable, backend_script]
            
        # 3. Set up the worker thread
        self.simulation_thread = QThread()
        self.simulation_worker = SimulationWorker(cmd)
        self.simulation_worker.moveToThread(self.simulation_thread)
        
        # 4. Connect signals and slots
        self.simulation_thread.started.connect(self.simulation_worker.run)
        self.simulation_worker.finished.connect(self.on_simulation_finished)
        self.simulation_worker.error.connect(self.on_simulation_error)
        
        # Clean up thread
        self.simulation_worker.finished.connect(self.simulation_thread.quit)
        self.simulation_worker.finished.connect(self.simulation_worker.deleteLater)
        self.simulation_thread.finished.connect(self.simulation_thread.deleteLater)
        self.simulation_thread.finished.connect(self.clear_simulation_thread) # Custom slot to clear members
        
        # 5. Start the thread and update the button
        self.simulation_thread.start()
        
        self.simulate_btn.setText("⏳ Simulating...")
        self.simulate_btn.setEnabled(False)
        self.simulate_btn.setStyleSheet("background-color: #F39C12; margin-left: 10px;") # Orange "working" color

    # --- NEW: Slot for simulation finishing successfully ---
    def on_simulation_finished(self, stdout, stderr):
        """Handle the 'finished' signal from the simulation worker."""
        print("Backend STDOUT:", stdout)
        self.reset_simulate_button()
        
        if stderr:
            print("Backend STDERR:", stderr)
            QMessageBox.critical(self, "Backend Error", f"Simulation script failed:\n{stderr}")
        else:
            QMessageBox.information(
                self,
                "Simulation Complete",
                "Simulation finished successfully.\n"
                "The backend has now displayed the plot (if any)."
            )
    
    # --- NEW: Slot for simulation error (Python exception) ---
    def on_simulation_error(self, error_message):
        """Handle the 'error' signal from the simulation worker."""
        self.reset_simulate_button()
        QMessageBox.critical(self, "Simulation Error", f"An unexpected error occurred:\n{error_message}")

    # --- NEW: Slot to clean up thread variables ---
    @pyqtSlot()
    def clear_simulation_thread(self):
        """Clear the thread and worker variables."""
        self.simulation_thread = None
        self.simulation_worker = None

    # --- NEW: Helper function to reset the simulate button ---
    def reset_simulate_button(self):
        """Resets the simulate button to its default state."""
        self.simulate_btn.setText("⚡ Simulate")
        self.simulate_btn.setEnabled(True)
        self.simulate_btn.setStyleSheet("background-color: #3498DB; margin-left: 10px;")

    # ---------- (build_adjacency_list class is UNCHANGED) ----------
    def build_adjacency_list(self, wires):
        adj = {}
        for wire in wires:
            if not (wire.start_component and wire.end_component):
                continue
            term1 = (wire.start_component, wire.start_terminal)
            term2 = (wire.end_component, wire.end_terminal)
            adj.setdefault(term1, []).append(term2)
            adj.setdefault(term2, []).append(term1)
        return adj

    # ---------- (build_node_map class is UNCHANGED) ----------
    def build_node_map(self, components, wires):
        adj = self.build_adjacency_list(wires)
        terminal_to_node_map = {}
        visited = set()
        
        ground_terminals = []
        for c in components:
            if c.component_type == "Ground":
                ground_terminals.append((c, 0))
        
        if not ground_terminals:
            if not self.sender() or self.sender().text() != "⚡ Simulate":
                 QMessageBox.warning(
                     self,
                     "Netlist Error",
                     "No Ground (GND) component found.\n"
                     "Netlist generation requires a ground reference (Node 0)."
                 )
            return None

        node_counter = 0
        queue = list(ground_terminals)
        visited.update(ground_terminals)
        
        for term in ground_terminals:
            terminal_to_node_map[term] = node_counter
        
        q_idx = 0
        while q_idx < len(queue):
            current_term = queue[q_idx]
            q_idx += 1
            
            if current_term in adj:
                for neighbor in adj[current_term]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        terminal_to_node_map[neighbor] = node_counter
                        queue.append(neighbor)
        
        node_counter = 1
        for comp in components:
            if comp.component_type == "Ground":
                continue 
                
            for term_idx in range(len(comp.terminals)):
                terminal = (comp, term_idx)
                if terminal not in visited:
                    queue = [terminal]
                    visited.add(terminal)
                    terminal_to_node_map[terminal] = node_counter
                    
                    q_idx = 0
                    while q_idx < len(queue):
                        current_term = queue[q_idx]
                        q_idx += 1
                        
                        if current_term in adj:
                            for neighbor in adj[current_term]:
                                if neighbor not in visited:
                                    visited.add(neighbor)
                                    terminal_to_node_map[neighbor] = node_counter
                                    queue.append(neighbor)
                    
                    node_counter += 1
                    
        return terminal_to_node_map

    # --- MODIFIED: export_netlist now returns (bool, bool) ---
    def export_netlist(self, silent=False):
        """
        Exports the netlist and probes.
        Returns: (success: bool, has_probes: bool)
        """
        all_components = [item for item in self.scene.items() if isinstance(item, BaseComponent)]
        wires = [item for item in self.scene.items() if isinstance(item, WireItem)]
        
        if not all_components:
            if not silent: 
                QMessageBox.warning(self, "Empty Circuit", "No components to export!")
            return False, False # (success, has_probes)
            
        terminal_map = self.build_node_map(all_components, wires)
        if terminal_map is None:
            # Error (No Ground) already shown by build_node_map
            return False, False

        netlist_lines = []
        probe_lines = []
        unconnected_nodes = []
        
        def sort_key(comp):
            prefix = comp.component_type[0].upper()
            if comp.component_type == "Current Probe": prefix = "VA"
            prefix_order = {'V': 1, 'I': 2, 'R': 3, 'L': 4, 'C': 5, 'V': 6}
            order = prefix_order.get(prefix, 99)
            return (order, comp.component_id)

        components_for_netlist = sorted(
            [c for c in all_components if c.component_type not in ["Ground", "Voltage Probe"]], 
            key=sort_key
        )

        # 1. BUILD NETLIST (netlist.txt)
        for item in components_for_netlist:
            comp_name = ""
            if item.component_type == "Current Probe":
                comp_name = f"VA{item.component_id}"
                item.value = "0"
            else:
                comp_name = f"{item.component_type[0].upper()}{item.component_id}"
            
            node1 = terminal_map.get((item, 0), "UNCONNECTED")
            node2 = terminal_map.get((item, 1), "UNCONNECTED")
            
            if node1 == "UNCONNECTED": unconnected_nodes.append(f"{comp_name} terminal 1")
            if node2 == "UNCONNECTED": unconnected_nodes.append(f"{comp_name} terminal 2")
            
            netlist_lines.append(f"{comp_name} {node1} {node2} {item.value}")
        
        # 2. BUILD PROBE LIST (probes.txt)
        for item in all_components:
            if item.component_type == "Voltage Probe":
                comp_name = f"VP{item.component_id}"
                node1 = terminal_map.get((item, 0), "UNCONNECTED")
                node2 = terminal_map.get((item, 1), "UNCONNECTED")
                
                if node1 == "UNCONNECTED": unconnected_nodes.append(f"{comp_name} terminal 1 (pos)")
                if node2 == "UNCONNECTED": unconnected_nodes.append(f"{comp_name} terminal 2 (neg)")
                
                probe_lines.append(f"{comp_name} {node1} {node2}")

            elif item.component_type == "Current Probe":
                comp_name = f"AP{item.component_id}"
                ammeter_name = f"VA{item.component_id}"
                
                probe_lines.append(f"{comp_name} {ammeter_name}")

        if unconnected_nodes and not silent:
            QMessageBox.warning(
                self,
                "Unconnected Terminals",
                "Warning: The following terminals are not connected:\n\n" +
                "\n".join(unconnected_nodes)
            )
        
        netlist_content = "\n".join(netlist_lines)
        probe_content = "\n".join(probe_lines)
        
        # --- MODIFIED: Check if probes exist ---
        has_probes = len(probe_lines) > 0
        
        netlist_file_path = "netlist.txt"
        probe_file_path = "probes.txt"
        
        try:
            with open(netlist_file_path, 'w') as f:
                f.write(netlist_content)
            
            with open(probe_file_path, 'w') as f:
                f.write(probe_content)
            
            if not silent:
                save_copy, _ = QFileDialog.getSaveFileName(
                    self,
                    "Save Netlist Copy As...",
                    "my_circuit.txt",
                    "Text Files (*.txt);;Netlist Files (*.net);;All Files (*)"
                )
                if save_copy:
                    import shutil
                    shutil.copy(netlist_file_path, save_copy)
                    shutil.copy(probe_file_path, save_copy.replace(".txt", "_probes.txt"))
                
                success_message = f"✓ Netlist exported successfully!\n"
                success_message += f"Netlist: {netlist_file_path} ({len(netlist_lines)} components)\n"
                success_message += f"Probes:  {probe_file_path} ({len(probe_lines)} probes)"
                
                QMessageBox.information(self, "Success", success_message)
            
            return True, has_probes # (success, has_probes)
            
        except Exception as e:
            if not silent: 
                QMessageBox.critical(self, "Error", f"Failed to save files:\n{str(e)}")
            return False, False

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = CircuitSimulator()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
