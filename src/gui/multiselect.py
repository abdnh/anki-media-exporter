from __future__ import annotations

from typing import cast

from aqt.qt import *


class ToggleAllCheckBox(QCheckBox):
    def nextCheckState(self) -> None:
        if self.checkState() in (
            Qt.CheckState.Unchecked,
            Qt.CheckState.PartiallyChecked,
        ):
            self.setCheckState(Qt.CheckState.Checked)
        else:
            self.setCheckState(Qt.CheckState.Unchecked)


class MultiSelect(QListWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setSpacing(2)
        item = QListWidgetItem(self)
        self.addItem(item)
        widget = ToggleAllCheckBox("All", self)
        qconnect(widget.stateChanged, self._on_check_all)
        self.setItemWidget(item, widget)

    def add_item(self, label: str) -> None:
        item = QListWidgetItem(self)
        self.addItem(item)
        widget = QCheckBox(label, self)
        qconnect(widget.stateChanged, self._on_item_state_changed)
        self.setItemWidget(item, widget)
        widget.setChecked(True)

    def _on_item_state_changed(self, state: int) -> None:
        checked_count = 0
        for i in range(1, self.count()):
            item = self.item(i)
            widget = cast(QCheckBox, self.itemWidget(item))
            if widget.isChecked():
                checked_count += 1
        if checked_count == 0:
            new_check_all_state = Qt.CheckState.Unchecked
        elif checked_count == self.count() - 1:
            new_check_all_state = Qt.CheckState.Checked
        else:
            new_check_all_state = Qt.CheckState.PartiallyChecked

        check_all_widget = cast(ToggleAllCheckBox, self.itemWidget(self.item(0)))
        check_all_widget.blockSignals(True)
        check_all_widget.setCheckState(new_check_all_state)
        check_all_widget.blockSignals(False)

    def _on_check_all(self, state: int) -> None:
        # FIXME: check if this works in Qt5
        check_state = Qt.CheckState(state)
        if check_state == Qt.CheckState.PartiallyChecked:
            return
        for i in range(1, self.count()):
            item = self.item(i)
            widget = cast(QCheckBox, self.itemWidget(item))
            widget.blockSignals(True)
            widget.setCheckState(check_state)
            widget.blockSignals(False)

    def set_checked(self, row: int, checked: bool) -> None:
        item = self.item(row)
        widget = cast(QCheckBox, self.itemWidget(item))
        widget.setChecked(checked)

    def label(self, row: int) -> str:
        item = self.item(row)
        widget = cast(QCheckBox, self.itemWidget(item))
        return widget.text()

    def selected_labels(self) -> list[str]:
        labels = []
        for i in range(1, self.count()):
            item = self.item(i)
            widget = cast(QCheckBox, self.itemWidget(item))
            if widget.isChecked():
                labels.append(widget.text())
        return labels
