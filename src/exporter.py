"""Media Exporter"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Generator, List, Optional, Set, Tuple

from anki.collection import Collection, SearchNode
from anki.decks import DeckId


class MediaExporter:
    "Deck Media Exporter"

    def __init__(self, col: Collection, did: DeckId | int, field: Optional[str] = None):
        self.col = col
        self.did = did
        self.field = field

    def file_lists(self) -> Generator[List[str], None, None]:
        "Return a generator that yields a list of media files for each note in the deck with the ID `self.did`"
        search_params = [SearchNode(deck=self.col.decks.name(self.did))]
        if self.field:
            search_params.append(SearchNode(field_name=self.field))
        search = self.col.build_search_string(*search_params)
        for nid in self.col.find_notes(search):
            note = self.col.get_note(nid)
            if self.field:
                flds = note[self.field]
            else:
                flds = "".join(note.fields)
            yield self.col.media.filesInStr(note.mid, flds)

    def export(
        self, folder: Path | str, exts: Optional[Set] = None
    ) -> Generator[Tuple[int, str], None, None]:
        """
        Export media files in `self.did` to `folder`,
        including only files that has extensions in `exts` if `exts` is not None.
        Returns a generator that yields the total media files exported so far and filenames as they are exported.
        """

        media_dir = self.col.media.dir()
        seen = set()
        exported = set()
        for filenames in self.file_lists():
            for filename in filenames:
                if filename in seen:
                    continue
                seen.add(filename)
                if exts is not None and os.path.splitext(filename)[1][1:] not in exts:
                    continue
                src_path = os.path.join(media_dir, filename)
                if not os.path.exists(src_path):
                    continue
                dest_path = os.path.join(folder, filename)
                shutil.copyfile(src_path, dest_path)
                exported.add(filename)
            yield len(exported), filenames
