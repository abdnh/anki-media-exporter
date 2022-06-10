"""
Initialize the add-on, and adds a menu item under the gears icon in the deck list screen
to export media from a target deck.
"""

from concurrent.futures import Future

from aqt import editor, gui_hooks, mw
from aqt.qt import *
from aqt.utils import tooltip

from .exporter import MediaExporter

ADDON_NAME = "Media Exporter"


def on_deck_browser_will_show_options_menu(menu: QMenu, did: int) -> None:
    """Adds a menu item under the gears icon to export a deck's media files."""

    def export_media():
        folder = QFileDialog.getExistingDirectory(
            mw, caption="Choose the folder where you want to export the files to"
        )

        config = mw.addonManager.getConfig(__name__)
        exts = set(editor.audio) if config.get("audio_only", False) else None
        field = config.get("search_in_field", None)
        want_cancel = False

        def export_task() -> int:
            exporter = MediaExporter(mw.col, did, field)
            note_count = mw.col.decks.card_count([did], include_subdecks=True)
            progress_step = min(2500, max(2500, note_count))
            media_i = 0
            for notes_i, (media_i, _) in enumerate(exporter.export(folder, exts)):
                if notes_i % progress_step == 0:
                    mw.taskman.run_on_main(
                        lambda notes_i=notes_i + 1, media_i=media_i: update_progress(
                            notes_i, note_count, media_i
                        )
                    )
                    if want_cancel:
                        break
            return media_i

        def update_progress(notes_i: int, note_count: int, media_i: int):
            nonlocal want_cancel
            mw.progress.update(
                label=f"Processed {notes_i} notes and exported {media_i} files",
                max=note_count,
                value=notes_i,
            )
            want_cancel = mw.progress.want_cancel()

        def on_done(future: Future):
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


gui_hooks.deck_browser_will_show_options_menu.append(
    on_deck_browser_will_show_options_menu
)
