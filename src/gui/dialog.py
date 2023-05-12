from __future__ import annotations

import functools
import time
from concurrent.futures import Future
from typing import List, Optional

import aqt
import aqt.editor
from aqt.main import AnkiQt
from aqt.qt import *
from aqt.utils import showWarning, tooltip

from .. import consts
from ..exporter import MediaExporter
from .multiselect import MultiSelect

ExporterFactory = Callable[[Optional[List[str]], Optional[set]], MediaExporter]


class ExportDialog(QDialog):
    def __init__(
        self, mw: AnkiQt, parent: QWidget, exporter_factory: ExporterFactory
    ) -> None:
        super().__init__(parent)
        self.mw = mw
        self._parent = parent
        self.exporter_factory = exporter_factory
        self.setup_ui()

    def export_folder_profile_key(self) -> str:
        return f"{consts.ADDON_MODULE}Directory"

    def default_export_folder(self) -> str:
        return self.mw.pm.profile.get(self.export_folder_profile_key(), "")

    def set_default_export_folder(self, folder: str) -> None:
        self.mw.pm.profile[self.export_folder_profile_key()] = folder

    def setup_ui(self) -> None:
        self.setWindowTitle(consts.ADDON_NAME)
        self.setMinimumSize(600, 500)

        layout = QGridLayout(self)
        self.setLayout(layout)

        self.folder_lineedit = QLineEdit(self.default_export_folder(), self)
        folder_button = QPushButton("...", self)
        qconnect(folder_button.clicked, self.on_folder_button)
        layout.addWidget(QLabel("Folder"), 0, 0)
        layout.addWidget(self.folder_lineedit, 0, 1, 1, 3)
        layout.addWidget(folder_button, 0, 4)

        self.field_selector = MultiSelect(self)
        layout.addWidget(QLabel("Included fields"), 1, 0)
        layout.addWidget(self.field_selector, 1, 2, 1, 3)

        exporter = self.exporter_factory(None, None)
        for field in exporter.all_fields():
            self.field_selector.add_item(field)

        self.ext_selector = MultiSelect(self)
        groupbox = QWidget(self)
        self.custom_exts = QRadioButton("Custom", self)
        self.custom_exts.setChecked(True)
        self.image_exts = QRadioButton("Images", self)
        qconnect(self.image_exts.toggled, self.on_image_exts)
        self.sound_exts = QRadioButton("Sounds", self)
        qconnect(self.sound_exts.toggled, self.on_sound_exts)
        groupbox_layout = QVBoxLayout(self)
        groupbox_layout.addWidget(self.custom_exts)
        groupbox_layout.addWidget(self.image_exts)
        groupbox_layout.addWidget(self.sound_exts)
        groupbox.setLayout(groupbox_layout)

        layout.addWidget(QLabel("Included extensions"), 2, 0)
        layout.addWidget(groupbox, 2, 1)
        layout.addWidget(self.ext_selector, 2, 2, 1, 3)

        for ext in exporter.all_extensions():
            self.ext_selector.add_item(ext)

        export_button = QPushButton("Export", self)
        qconnect(export_button.clicked, self.on_export)
        layout.addWidget(export_button, 3, 2, 1, 3)

    def on_folder_button(self) -> None:
        default_folder = self.default_export_folder()
        folder = QFileDialog.getExistingDirectory(
            self,
            caption="Choose the folder where you want to export the files to",
            directory=default_folder,
        )
        if folder:
            self.folder_lineedit.setText(folder)
            self.set_default_export_folder(folder)

    def on_image_exts(self, toggled: bool) -> None:
        if not toggled:
            return
        for i in range(1, self.ext_selector.count()):
            checked = False
            if self.ext_selector.label(i) in aqt.editor.pics:
                checked = True
            self.ext_selector.set_checked(i, checked)

    def on_sound_exts(self, toggled: bool) -> None:
        if not toggled:
            return
        for i in range(1, self.ext_selector.count()):
            checked = False
            if self.ext_selector.label(i) in aqt.editor.audio:
                checked = True
            self.ext_selector.set_checked(i, checked)

    def on_export(self) -> None:
        fields = self.field_selector.selected_labels()
        exts = self.ext_selector.selected_labels()
        folder = self.folder_lineedit.text()
        exporter = self.exporter_factory(fields, set(exts))
        note_count = len(exporter.notes)

        if not folder:
            showWarning("No folder set", self, title=consts.ADDON_NAME)
            return

        self.accept()

        want_cancel = False

        def export_task() -> int:
            last_progress = 0.0
            media_i = 0
            for notes_i, (media_i, _) in enumerate(exporter.export(folder)):
                if time.time() - last_progress >= 0.1:
                    last_progress = time.time()
                    self.mw.taskman.run_on_main(
                        functools.partial(
                            update_progress,
                            notes_i=notes_i,
                            note_count=note_count,
                            media_i=media_i,
                        )
                    )
                    if want_cancel:
                        break
            return media_i

        def update_progress(notes_i: int, note_count: int, media_i: int) -> None:
            nonlocal want_cancel
            self.mw.progress.update(
                label=f"Processed {notes_i+1} notes and exported {media_i} files",
                max=note_count,
                value=notes_i + 1,
            )
            want_cancel = self.mw.progress.want_cancel()

        def on_done(future: Future) -> None:
            try:
                count = future.result()
            finally:
                self.mw.progress.finish()
            tooltip(f"Exported {count} media files", parent=self._parent)

        self.mw.progress.start(label="Exporting media...", parent=self._parent)
        self.mw.progress.set_title(consts.ADDON_NAME)
        self.mw.taskman.run_in_background(export_task, on_done=on_done)
