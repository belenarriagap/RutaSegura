"""Tema visual de la aplicación: colores, letra y hoja de estilos (QSS).

Todo es local: usa las fuentes del sistema (Segoe UI en Windows) y no descarga nada.
Los widgets eligen variantes con propiedades dinámicas, por ejemplo
``button.setProperty("primary", True)`` o ``frame.setProperty("kind", "error")``.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

# Paleta
BACKGROUND = "#f4f6f9"
SURFACE = "#ffffff"
BORDER = "#d9dee5"
TEXT = "#1f2933"
MUTED = "#5f6b7a"
PRIMARY = "#1d5fbf"
PRIMARY_HOVER = "#174f9f"
PRIMARY_SOFT = "#e7effb"
SIDEBAR = "#18324f"
SIDEBAR_TEXT = "#dbe5f1"
SUCCESS = "#2e7d32"
SUCCESS_SOFT = "#e7f4e8"
WARNING = "#a85d00"
WARNING_SOFT = "#fff3df"
ERROR = "#c62828"
ERROR_SOFT = "#fdeceb"
INFO = PRIMARY
INFO_SOFT = PRIMARY_SOFT

KIND_COLORS: dict[str, tuple[str, str]] = {
    "success": (SUCCESS, SUCCESS_SOFT),
    "warning": (WARNING, WARNING_SOFT),
    "error": (ERROR, ERROR_SOFT),
    "info": (INFO, INFO_SOFT),
}

BASE_POINT_SIZE = 10


def _kind_rules() -> str:
    rules = []
    for kind, (strong, soft) in KIND_COLORS.items():
        rules.append(
            f'QFrame#banner[kind="{kind}"] {{ background: {soft}; border: 1px solid {strong};'
            f" border-left: 5px solid {strong}; border-radius: 6px; }}\n"
            f'QFrame#banner[kind="{kind}"] QLabel#bannerIcon {{ color: {strong}; }}\n'
            f'QFrame#card[kind="{kind}"] {{ border-top: 4px solid {strong}; }}\n'
            f'QFrame#card[kind="{kind}"] QLabel#cardValue {{ color: {strong}; }}\n'
        )
    return "".join(rules)


STYLESHEET = f"""
QWidget {{ color: {TEXT}; }}
QMainWindow, QDialog {{ background: {BACKGROUND}; }}
QToolTip {{ background: {TEXT}; color: white; border: none; padding: 6px; }}

QLabel#pageTitle {{ font-size: {BASE_POINT_SIZE + 7}pt; font-weight: 600; color: {TEXT}; }}
QLabel#pageHelp {{ color: {MUTED}; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#sectionTitle {{ font-size: {BASE_POINT_SIZE + 2}pt; font-weight: 600; }}

QPushButton {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 6px;
    padding: 6px 14px; min-height: 22px;
}}
QPushButton:hover {{ background: {PRIMARY_SOFT}; border-color: {PRIMARY}; }}
QPushButton:pressed {{ background: #d6e3f7; }}
QPushButton:checked {{ background: {PRIMARY_SOFT}; border-color: {PRIMARY}; color: {PRIMARY}; }}
QPushButton:disabled {{ color: #a3acb8; background: #eef1f5; border-color: #e1e5ea; }}
QPushButton[primary="true"] {{
    background: {PRIMARY}; color: white; border: 1px solid {PRIMARY}; font-weight: 600;
}}
QPushButton[primary="true"]:hover {{ background: {PRIMARY_HOVER}; }}
QPushButton[primary="true"]:disabled {{ background: #9bb5dd; border-color: #9bb5dd; }}
QPushButton[flat="true"] {{ background: transparent; border: none; padding: 2px 6px; }}
QPushButton#bannerClose {{ background: transparent; border: none; padding: 0 6px;
    font-size: {BASE_POINT_SIZE + 3}pt; color: {MUTED}; }}
QPushButton#bannerClose:hover {{ color: {TEXT}; }}

QLineEdit {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 5px; padding: 4px 6px;
    min-height: 22px;
}}
QLineEdit:focus {{ border-color: {PRIMARY}; }}
QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit, QTimeEdit {{ min-height: 24px; }}
QGroupBox {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px;
    margin-top: 14px; padding: 10px 8px 8px 8px; font-weight: 600;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}
QGroupBox QCheckBox {{ font-weight: normal; }}

QTableWidget, QTableView, QListWidget, QTreeWidget {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 6px;
    alternate-background-color: #f8fafc; gridline-color: #e8ecf1;
    selection-background-color: {PRIMARY_SOFT}; selection-color: {TEXT};
}}
QHeaderView::section {{
    background: #eef2f7; border: none; border-bottom: 1px solid {BORDER};
    padding: 6px; font-weight: 600;
}}
QProgressBar {{
    background: #e6ebf1; border: none; border-radius: 6px; text-align: center; min-height: 14px;
}}
QProgressBar::chunk {{ background: {PRIMARY}; border-radius: 6px; }}
QToolBar {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px; padding: 3px;
    spacing: 2px;
}}
QToolBar QToolButton {{ border: 1px solid transparent; border-radius: 6px; padding: 4px 5px; }}
QToolBar QToolButton:hover {{ background: {PRIMARY_SOFT}; }}
QToolBar QToolButton:checked {{
    background: {PRIMARY_SOFT}; border-color: {PRIMARY}; color: {PRIMARY}; font-weight: 600;
}}
QToolBar QToolButton:disabled {{ color: #a3acb8; }}
QGraphicsView {{ border: 1px solid {BORDER}; border-radius: 6px; }}
QSplitter::handle {{ background: transparent; }}
QStatusBar {{ background: {SURFACE}; border-top: 1px solid {BORDER}; color: {MUTED}; }}
QMenuBar {{ background: {SURFACE}; border-bottom: 1px solid {BORDER}; }}
QMenu {{ background: {SURFACE}; border: 1px solid {BORDER}; padding: 4px; }}
QMenu::item {{ padding: 6px 22px 6px 12px; border-radius: 4px; }}
QMenu::item:selected {{ background: {PRIMARY_SOFT}; color: {TEXT}; }}
QMenu::item:disabled {{ color: #a3acb8; }}

QWidget#sidebar {{ background: {SIDEBAR}; }}
QLabel#sidebarTitle {{ color: white; font-size: {BASE_POINT_SIZE + 5}pt; font-weight: 700; }}
QLabel#sidebarSubtitle {{ color: #9fb3cc; }}
QListWidget#wizardSteps {{
    background: transparent; border: none; color: {SIDEBAR_TEXT}; outline: none;
}}
QListWidget#wizardSteps::item {{ padding: 9px 8px; border-radius: 6px; margin: 1px 0; }}
QListWidget#wizardSteps::item:hover {{ background: #22446a; }}
QListWidget#wizardSteps::item:selected {{ background: {PRIMARY}; color: white; }}
QListWidget#wizardSteps::item:disabled {{ color: #6f84a0; }}

QWidget#floorBar, QWidget#navBar {{ background: {SURFACE}; border: 1px solid {BORDER};
    border-radius: 8px; }}
QLabel#navStep {{ color: {MUTED}; }}

QFrame#banner QLabel {{ background: transparent; border: none; }}
QLabel#bannerIcon {{ font-size: {BASE_POINT_SIZE + 4}pt; font-weight: 700; }}

QFrame#card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px; }}
QFrame#card QLabel {{ border: none; background: transparent; }}
QLabel#cardTitle {{ color: {MUTED}; }}
QLabel#cardValue {{ font-size: {BASE_POINT_SIZE + 10}pt; font-weight: 700; }}
QLabel#cardNote {{ color: {MUTED}; }}

QFrame#welcomeCard {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px; }}
QFrame#welcomeCard QLabel {{ background: transparent; }}
QLabel#welcomeTitle {{ font-size: {BASE_POINT_SIZE + 12}pt; font-weight: 700; }}
QFrame#legend QLabel {{ font-weight: normal; }}
{_kind_rules()}
"""


def _palette() -> QPalette:
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: BACKGROUND,
        QPalette.ColorRole.WindowText: TEXT,
        QPalette.ColorRole.Base: SURFACE,
        QPalette.ColorRole.AlternateBase: "#f8fafc",
        QPalette.ColorRole.Text: TEXT,
        QPalette.ColorRole.Button: SURFACE,
        QPalette.ColorRole.ButtonText: TEXT,
        QPalette.ColorRole.Highlight: PRIMARY,
        QPalette.ColorRole.HighlightedText: "#ffffff",
        QPalette.ColorRole.ToolTipBase: TEXT,
        QPalette.ColorRole.ToolTipText: "#ffffff",
        QPalette.ColorRole.PlaceholderText: MUTED,
        QPalette.ColorRole.Link: PRIMARY,
    }
    for role, color in roles.items():
        palette.setColor(role, QColor(color))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#a3acb8"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#a3acb8"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor("#a3acb8"))
    return palette


def apply_theme(app: QApplication) -> None:
    """Aplica el estilo Fusion, la paleta clara, la letra base y la hoja de estilos."""
    app.setStyle("Fusion")
    app.setPalette(_palette())
    font = QFont(app.font())  # la del sistema (Segoe UI en Windows), un poco más grande
    font.setPointSize(BASE_POINT_SIZE)
    app.setFont(font)
    app.setStyleSheet(STYLESHEET)


def set_primary(button: QPushButton, primary: bool = True) -> QPushButton:
    """Marca el botón como acción principal del paso (azul)."""
    button.setProperty("primary", primary)
    repolish(button)
    return button


def repolish(widget: QWidget) -> None:
    """Vuelve a aplicar la hoja de estilos tras cambiar una propiedad dinámica."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()
