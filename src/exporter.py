from __future__ import annotations

import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Generator

from anki.collection import Collection, SearchNode
from anki.decks import DeckId
from anki.notes import Note
from anki.utils import ids2str


def get_note_media(col: Collection, note: Note, fields: list[str] | None) -> list[str]:
    if fields is not None:
        matched_fields = [note[field] for field in fields if field in note]
    else:
        matched_fields = note.fields
    flds = "".join(matched_fields)
    files_in_str = getattr(col.media, "files_in_str", None)
    if not files_in_str:
        files_in_str = col.media.filesInStr
    return files_in_str(note.mid, flds)


class MediaExporter(ABC):
    """Abstract media exporter."""

    def __init__(
        self, col: Collection, fields: list[str] | None = None, exts: set | None = None
    ) -> None:
        self.col = col
        self.fields = fields
        self.exts = exts
        self._notes: list[Note] = []
        self._media_lists: list[list[str]] = []

    @property
    @abstractmethod
    def notes(self) -> list[Note]:
        return self._notes

    @property
    def media_lists(self) -> Generator[list[str], None, None]:
        """Return a generator that yields a list of media files for each note."""
        if self._media_lists:
            yield from self._media_lists
        else:
            for note in self.notes:
                media = get_note_media(self.col, note, self.fields)
                self._media_lists.append(media)
                yield media

    def all_extensions(self) -> set[str]:
        exts = set()
        for media_list in self.media_lists:
            for filename in media_list:
                ext = os.path.splitext(filename)[1][1:]
                exts.add(ext)
        return exts

    def all_fields(self) -> list[str]:
        fields = self.col.db.list(
            "select distinct name from fields where ntid in (select mid from notes where id in %s)"
            % ids2str(note.id for note in self.notes)
        )
        return fields

    def export(
        self, folder: Path | str
    ) -> Generator[tuple[int, list[str]], None, None]:
        """
        Export media files in `self.did` to `folder`,
        including only files that has extensions in `self.exts` if it's not None.
        Returns a generator that yields the total media files exported so far and filenames as they are exported.
        """

        media_dir = self.col.media.dir()
        seen = set()
        exported = set()
        for filenames in self.media_lists:
            for filename in filenames:
                if filename in seen:
                    continue
                seen.add(filename)
                if (
                    self.exts is not None
                    and os.path.splitext(filename)[1][1:] not in self.exts
                ):
                    continue
                src_path = os.path.join(media_dir, filename)
                if not os.path.exists(src_path):
                    continue
                dest_path = os.path.join(folder, filename)
                shutil.copyfile(src_path, dest_path)
                exported.add(filename)
            yield len(exported), filenames


class NoteMediaExporter(MediaExporter):
    """Exporter for a list of notes."""

    def __init__(
        self,
        col: Collection,
        notes: list[Note],
        fields: list[str] | None = None,
        exts: set | None = None,
    ):
        super().__init__(col, fields, exts)
        self._notes = notes

    @property
    def notes(self) -> list[Note]:
        return self._notes


class DeckMediaExporter(MediaExporter):
    "Exporter for all media in a deck."

    def __init__(
        self,
        col: Collection,
        did: DeckId,
        fields: list[str] | None = None,
        exts: set | None = None,
    ):
        super().__init__(col, fields, exts)
        self.did = did

    @property
    def notes(self) -> list[Note]:
        if self._notes:
            return self._notes
        search_terms = [SearchNode(deck=self.col.decks.name(self.did))]
        if self.fields is not None:
            or_terms = []
            for field in self.fields:
                or_terms.append(SearchNode(field_name=field))
            search_terms.append(self.col.group_searches(*or_terms, joiner="OR"))
        search = self.col.build_search_string(*search_terms)
        for nid in self.col.find_notes(search):
            self._notes.append(self.col.get_note(nid))
        return self._notes
