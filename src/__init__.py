"""
Initialize the add-on, and adds a menu item under the gears icon in the deck list screen
to export media from a target deck.
"""

from __future__ import annotations

from concurrent.futures import Future

import aqt
from anki.decks import DeckId
from aqt import gui_hooks, mw
from aqt.editor import Editor
from aqt.qt import *
from aqt.utils import tooltip

from .exporter import DeckMediaExporter, NoteMediaExporter

ADDON_NAME = "Media Exporter"
ADDON_DIR = os.path.dirname(__file__)
AUDIO_EXTS = aqt.editor.audio


def get_export_folder() -> str:
    "Get the export folder from the user."
    return QFileDialog.getExistingDirectory(
        mw, caption="Choose the folder where you want to export the files to"
    )


def on_deck_browser_will_show_options_menu(menu: QMenu, did: int) -> None:
    """Adds a menu item under the gears icon to export a deck's media files."""

    def export_media() -> None:
        folder = get_export_folder()
        config = mw.addonManager.getConfig(__name__)
        exts = set(AUDIO_EXTS) if config.get("audio_only", False) else None
        field = config.get("search_in_field", None)
        want_cancel = False

        def export_task() -> int:
            exporter = DeckMediaExporter(mw.col, DeckId(did), field)
            note_count = mw.col.decks.card_count([DeckId(did)], include_subdecks=True)
            last_progress = 0.0
            media_i = 0
            for notes_i, (media_i, _) in enumerate(exporter.export(folder, exts)):
                if time.time() - last_progress >= 0.1:
                    last_progress = time.time()
                    mw.taskman.run_on_main(
                        lambda notes_i=notes_i + 1, media_i=media_i: update_progress(
                            notes_i, note_count, media_i
                        )
                    )
                    if want_cancel:
                        break
            return media_i

        def update_progress(notes_i: int, note_count: int, media_i: int) -> None:
            nonlocal want_cancel
            mw.progress.update(
                label=f"Processed {notes_i} notes and exported {media_i} files",
                max=note_count,
                value=notes_i,
            )
            want_cancel = mw.progress.want_cancel()

        def on_done(future: Future) -> None:
            try:
                count = future.result()
            finally:
                mw.progress.finish()
            tooltip(f"Exported {count} media files", parent=mw)

        mw.progress.start(label="Exporting media...", parent=mw)
        mw.progress.set_title(ADDON_NAME)
        mw.taskman.run_in_background(export_task, on_done=on_done)

    action = menu.addAction("Export Media")
    qconnect(action.triggered, export_media)


def add_editor_button(buttons: list[str], editor: Editor) -> None:
    "Add an editor button to export media from the current note."

    def on_clicked(editor: Editor) -> None:
        config = mw.addonManager.getConfig(__name__)
        exts = set(AUDIO_EXTS) if config.get("audio_only", False) else None
        field = config.get("search_in_field", None)
        folder = get_export_folder()
        exporter = NoteMediaExporter(mw.col, [editor.note], field)
        media_tuple = list(exporter.export(folder, exts))[0]
        tooltip(f"Exported {media_tuple[0]} media files", parent=editor.widget)

    button = editor.addButton(
        icon=os.path.join(ADDON_DIR, "icons", "editor-icon.svg"),
        cmd="media_exporter",
        func=on_clicked,
        tip="Export Media",
    )
    buttons.append(button)


gui_hooks.deck_browser_will_show_options_menu.append(
    on_deck_browser_will_show_options_menu
)
gui_hooks.editor_did_init_buttons.append(add_editor_button)
