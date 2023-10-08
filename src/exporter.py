from __future__ import annotations

import os
import re
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Generator

from anki.collection import Collection, SearchNode
from anki.decks import DeckId
from anki.models import NotetypeDict, TemplateDict
from anki.notes import Note
from anki.utils import ids2str


def gather_media_from_css(css: str) -> list[str]:
    # Regular expression taken from the anki repo https://github.com/ankitects/anki/blob/c2b1ab5eb06935e93aea6af09a224a99f4b971f0/rslib/src/text.rs#L151
    underscored_css_imports_pattern = re.compile(
        r"""(?xi)
        (?:@import\s+           # import statement with a bare
            "(_[^"]*.css)"      # double quoted
            |                   # or
            '(_[^']*.css)'      # single quoted css filename
        )
        |
        (?:url\(\s*             # a url function with a
            "(_[^"]+)"          # double quoted
            |                   # or
            '(_[^']+)'          # single quoted
            |                   # or
            (_.+)               # unquoted filename
        \s*\))
    """
    )

    media_files = []

    matches = underscored_css_imports_pattern.findall(css)
    for match in matches:
        for group in match:
            if group and group.startswith("_"):
                media_files.append(group)

    return media_files


def gather_media_from_template_side(template_side: str) -> list[str]:
    # Regular expression taken from the anki repo https://github.com/ankitects/anki/blob/c2b1ab5eb06935e93aea6af09a224a99f4b971f0/rslib/src/text.rs#L169
    underscored_references_pattern = re.compile(
        r"""(?x)
        \[sound:(_[^]]+)\]  # a filename in an Anki sound tag
        |
        "(_[^"]+)"          # a double quoted
        |
        '(_[^']+)'          # single quoted string
        |
        \b(?:src|data)      # a 'src' or 'data' attribute
        =
        (_[^ >]+)           # an unquoted value
    """
    )

    media_files = []

    matches = underscored_references_pattern.findall(template_side)
    for match in matches:
        for group in match:
            if group and group.startswith("_"):
                media_files.append(group)

    return media_files


def gather_media_from_template(template: TemplateDict) -> list[str]:
    question_template = str(template["qfmt"])
    answer_template = str(template["afmt"])

    media_files = gather_media_from_template_side(question_template)
    media_files.extend(gather_media_from_template_side(answer_template))

    return media_files


def get_note_media(col: Collection, note: Note, fields: list[str] | None) -> list[str]:
    if fields is not None:
        matched_fields = [note[field] for field in fields if field in note]
    else:
        matched_fields = note.fields
    flds = "".join(matched_fields)
    files_in_str = getattr(col.media, "files_in_str", None)
    if not files_in_str:
        files_in_str = col.media.filesInStr  # type: ignore
    return files_in_str(note.mid, flds)


def get_notetype_media(notetype: NotetypeDict) -> list[str]:
    css_media = gather_media_from_css(notetype["css"])

    template_media = []
    for template in notetype["tmpls"]:
        template_media.extend(gather_media_from_template(template))

    return css_media + template_media


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
            notetypes_in_selection = set()
            for note in self.notes:
                # Gather notetypes in selected notes without duplicates
                notetypes_in_selection.add(note.note_type()["name"])

                media = get_note_media(self.col, note, self.fields)
                self._media_lists.append(media)
                yield media

            get_notetype_by_name = getattr(self.col.models, "by_name", None)
            if not get_notetype_by_name:
                get_notetype_by_name = self.col.models.byName  # type: ignore[attr-defined]
            for notetype_name in notetypes_in_selection:
                notetype = get_notetype_by_name(notetype_name)
                media = get_notetype_media(notetype)
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
        Export media files in `self.notes` to `folder`,
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
