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
CONFIG = mw.addonManager.getConfig(__name__)


def on_deck_browser_will_show_options_menu(menu: QMenu, did: int) -> None:
    """Adds a menu item under the gears icon to export a deck's media files."""

    def export_media():
        folder = QFileDialog.getExistingDirectory(
            mw, caption="Choose the folder where you want to export the files to"
        )
        want_cancel = False
        exts = set(editor.audio) if CONFIG.get("audio_only", False) else None

        def export_task() -> int:
            exporter = MediaExporter(mw.col, did)
            i = 0
            for _ in exporter.export(folder, exts):
                if i % 50 == 0:
                    mw.taskman.run_on_main(lambda i=i: update_progress(i))
                    if want_cancel:
                        break
                i += 1
            return i

        def update_progress(i: int):
            nonlocal want_cancel
            mw.progress.update(label=f"Exported {i+1} files")
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
