from __future__ import annotations

import sys

from anki.decks import DeckId
from aqt import gui_hooks, mw
from aqt.editor import Editor

try:
    from aqt.browser.browser import Browser
except ImportError:
    from aqt.browser import Browser

from aqt.qt import *

sys.path.append(os.path.join(os.path.dirname(__file__), "vendor"))

from .consts import consts
from .exporter import DeckMediaExporter, NoteMediaExporter
from .gui.dialog import ExportDialog


def on_deck_browser_will_show_options_menu(menu: QMenu, did: int) -> None:
    def export_media() -> None:
        def exporter_factory(
            fields: list[str] | None = None, exts: set | None = None
        ) -> DeckMediaExporter:
            return DeckMediaExporter(mw.col, DeckId(did), fields, exts)

        dialog = ExportDialog(mw, mw, exporter_factory)
        dialog.exec()

    action = menu.addAction("Export Media")
    qconnect(action.triggered, export_media)


def add_editor_button(buttons: list[str], editor: Editor) -> None:
    def on_clicked(editor: Editor) -> None:
        def exporter_factory(
            fields: list[str] | None = None, exts: set | None = None
        ) -> NoteMediaExporter:
            return NoteMediaExporter(mw.col, [editor.note], fields, exts)

        dialog = ExportDialog(mw, editor.parentWindow, exporter_factory)
        dialog.exec()

    button = editor.addButton(
        icon=os.path.join(consts.dir, "icons", "editor-icon.svg"),
        cmd="media_exporter",
        func=on_clicked,
        tip="Export Media",
    )
    buttons.append(button)


def add_browser_menu_item(browser: Browser) -> None:
    def export_selected() -> None:
        selected_notes = [mw.col.get_note(nid) for nid in browser.selected_notes()]

        def exporter_factory(
            fields: list[str] | None = None, exts: set | None = None
        ) -> NoteMediaExporter:
            return NoteMediaExporter(mw.col, selected_notes, fields, exts)

        dialog = ExportDialog(mw, browser, exporter_factory)
        dialog.exec()

    action = QAction("Export Media", browser)
    qconnect(action.triggered, export_selected)
    browser.form.menu_Notes.addAction(action)


gui_hooks.deck_browser_will_show_options_menu.append(
    on_deck_browser_will_show_options_menu
)
gui_hooks.editor_did_init_buttons.append(add_editor_button)
gui_hooks.browser_menus_did_init.append(add_browser_menu_item)
