"""Diálogos para crear y abrir proyectos."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rutasegura.domain.enums import UseType
from rutasegura.domain.project import Project
from rutasegura.resources.texts import TEXTS, ProjectTexts


class NewProjectDialog(QDialog):
    """Nombre, tipo de local y dirección."""

    def __init__(self, texts: ProjectTexts = TEXTS.project, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._texts = texts
        self.setWindowTitle(texts.new_title)
        self.name_edit = QLineEdit()
        self.use_combo = QComboBox()
        for value, label in texts.use_labels:
            self.use_combo.addItem(label, value)
        self.address_edit = QLineEdit()
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #c0392b;")
        form = QFormLayout()
        form.addRow(texts.name, self.name_edit)
        form.addRow(texts.use, self.use_combo)
        form.addRow(texts.address, self.address_edit)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.error_label)
        layout.addWidget(buttons)

    def accept(self) -> None:
        """Valida antes de cerrar."""
        if not self.name_edit.text().strip():
            self.error_label.setText(self._texts.name_required)
            self.name_edit.setFocus()
            return
        super().accept()

    def values(self) -> tuple[str, UseType, str]:
        """(nombre, uso, dirección)."""
        return (
            self.name_edit.text().strip(),
            UseType(self.use_combo.currentData()),
            self.address_edit.text().strip(),
        )


class OpenProjectDialog(QDialog):
    """Lista de proyectos guardados."""

    def __init__(
        self,
        projects: list[tuple[int, Project]],
        texts: ProjectTexts = TEXTS.project,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(texts.open_title)
        self.resize(480, 360)
        labels = dict(texts.use_labels)
        self.list_widget = QListWidget()
        for project_id, project in projects:
            date = project.created_at.strftime("%d/%m/%Y") if project.created_at else ""
            item = QListWidgetItem(f"{project.name} — {labels.get(project.use.value, '')} {date}")
            item.setData(Qt.ItemDataRole.UserRole, project_id)
            self.list_widget.addItem(item)
        if projects:
            self.list_widget.setCurrentRow(0)
        self.list_widget.itemDoubleClicked.connect(lambda _item: self.accept())
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Open | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Open).setEnabled(bool(projects))
        layout = QVBoxLayout(self)
        if not projects:
            layout.addWidget(QLabel(texts.no_projects))
        layout.addWidget(self.list_widget)
        layout.addWidget(buttons)

    def selected_id(self) -> int | None:
        """Id del proyecto elegido."""
        item = self.list_widget.currentItem()
        return None if item is None else int(item.data(Qt.ItemDataRole.UserRole))
