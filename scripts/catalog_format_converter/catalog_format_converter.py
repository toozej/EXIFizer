#!/usr/bin/env python3
"""
Film Photo Catalog Format Converter (Take 2)

Converts a variety of legacy and current markdown list formats that describe film rolls
into a standardized "new - all fields" markdown format while preserving original order
and avoiding data loss.

Key requirements implemented:
- Support 4 known input styles (and similar variants):
  1) old - unstructured
  2) old - structured
  3) new - missing fields
  4) new - all fields
- Always output the standardized "new - all fields" format (all fields present).
  Use "None" for undetermined/empty fields EXCEPT:
    - "Developed Location" defaults to "Citizens PDX" when undetermined/empty.
- Preserve order of entries as in input.
- Avoid data loss: any information that cannot be confidently mapped is appended to Notes.
- Async file conversion; regex-based parsing; defensive and well logged.
- Complete type annotations, docstrings, and self-tests.

Run conversion example:
python3 scripts/catalog_format_converter/catalog_format_converter_take2.py --input in/in.md --output out/out_take2.md

Run internal tests:
python3 scripts/catalog_format_converter/catalog_format_converter_take2.py --self-test
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import logging
import re
import sys
from pathlib import Path

# Known cameras (canonical list). Any non-matching camera becomes "Unknown".
KNOWN_CAMERAS: tuple[str, ...] = (
    "Nikon N80",
    "Minolta SR-T101 silver",
    "Minolta SR-T101 black",
    "Minolta X-700",
    "Halina 35X",
)


def setup_logging(verbose: bool = False) -> None:
    """
    Configure logging based on verbosity.

    Args:
        verbose: If True, set level to DEBUG; else INFO.
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )


@dataclasses.dataclass(slots=True)
class FilmEntry:
    """
    A structured representation of a single film catalog entry.

    Notes on fields:
    - quantity: Optional count prefix like "1x", "2x" extracted from legacy top-line.
      If present, it will be prefixed to filmstock in output to prevent information loss.
    - Any unknown/undetermined values remain as empty strings in the model and are
      rendered as "None" in output (except Developed Location which defaults to Citizens PDX).
    """

    filmstock: str = ""
    iso: str = ""
    exposures: str = ""
    expiration: str = ""
    loaded_date: str = ""
    camera: str = ""
    lens: str = ""
    filter: str = ""
    notes: str = ""
    subject: str = ""
    shot_location: str = ""
    ready_date: str = ""
    developed_date: str = ""
    developed_location: str = ""
    roll_num: str = ""
    quantity: str = ""  # e.g., "1x"

    def to_markdown(self) -> str:
        """
        Convert the entry to the standardized new format markdown.

        Returns:
            The markdown block string representing this entry.

        Output schema:
        - Filmstock: VALUE
            - ISO: VALUE
            - Exposures: VALUE
            - Expiration: VALUE
            - Loaded Date: VALUE
            - Camera: VALUE
            - Lens: VALUE
            - Filter: VALUE
            - Notes: VALUE
            - Subject: VALUE
            - Shot Location: VALUE
            - Ready for Development Date: VALUE
            - Developed Date: VALUE
            - Developed Location: VALUE (defaults to "Citizens PDX" when empty)
            - RollNum: VALUE
        """

        def or_default(value: str, default: str = "None") -> str:
            return value if value.strip() else default

        # Developed Location default override
        developed_location_val = (
            self.developed_location.strip() if self.developed_location.strip() else "Citizens PDX"
        )

        # Preserve quantity in the Filmstock line to avoid data loss
        filmstock_display = " ".join(
            s for s in [self.quantity.strip(), self.filmstock.strip()] if s
        ).strip()
        if not filmstock_display:
            filmstock_display = "None"

        lines = [
            f"- Filmstock: {filmstock_display}",
            f"    - ISO: {or_default(self.iso)}",
            f"    - Exposures: {or_default(self.exposures)}",
            f"    - Expiration: {or_default(self.expiration)}",
            f"    - Loaded Date: {or_default(self.loaded_date)}",
            f"    - Camera: {or_default(self.camera)}",
            f"    - Lens: {or_default(self.lens)}",
            f"    - Filter: {or_default(self.filter)}",
            f"    - Notes: {or_default(self.notes)}",
            f"    - Subject: {or_default(self.subject)}",
            f"    - Shot Location: {or_default(self.shot_location)}",
            f"    - Ready for Development Date: {or_default(self.ready_date)}",
            f"    - Developed Date: {or_default(self.developed_date)}",
            f"    - Developed Location: {developed_location_val}",
            f"    - RollNum: {or_default(self.roll_num)}",
        ]
        return "\n".join(lines)


class CatalogConverter:
    """
    Converter that parses legacy and current markdown list formats into structured entries
    and renders them into the standardized "new - all fields" format.
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        # Flexible date pattern that captures a wide variety of formats.
        self.date_pattern = re.compile(
            r"("
            r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"  # 01/23/23 or 1-2-2023
            r"|"
            r"\d{4}-\d{1,2}-\d{1,2}"  # 2023-01-23
            r"|"
            r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{2,4}"  # Apr 1, 2023
            r"|"
            r"\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4}"  # 1 Apr 2023
            r")",
            re.IGNORECASE,
        )

    # -------- Helper utilities for canonical camera parsing and finalization --------
    def _canonical_camera(self, raw: str) -> str | None:
        """
        Try to map a raw camera string to one of the KNOWN_CAMERAS.
        Returns the canonical name when confident, else None.
        """
        if not raw:
            return None
        text = raw.strip()
        low = text.lower()

        # 1) Exact (case-insensitive) match
        for cam in KNOWN_CAMERAS:
            if low == cam.lower():
                return cam

        # 2) Substring match of canonical names
        for cam in KNOWN_CAMERAS:
            if cam.lower() in low:
                return cam

        # 3) Heuristics
        # Nikon N80 (accept short/nickname forms like "N80")
        if re.search(r"\bn80\b", low):
            return "Nikon N80"

        # Minolta X-700 (accept "X-700"/"X700" even without brand prefix)
        if ("x-700" in low) or ("x700" in low):
            return "Minolta X-700"

        # Minolta SR-T101 variants:
        # If color isn't provided (or if only brand mentioned), assume "Minolta SR-T101 silver"
        srt101_hint = (
            ("sr" in low and "t101" in low)
            or "srt-101" in low
            or "srt101" in low
            or "sr-t101" in low
        )
        if "minolta" in low and srt101_hint:
            if "black" in low:
                return "Minolta SR-T101 black"
            # Default to silver when no explicit color is specified
            return "Minolta SR-T101 silver"

        # If it's just "Minolta" (no specific model we recognize), default to SR-T101 silver
        if "minolta" in low:
            return "Minolta SR-T101 silver"

        # Halina 35X (accept generic "Halina" as alias)
        if "halina" in low:
            return "Halina 35X"

        return None

    def _find_known_camera_in_text(self, text: str) -> str | None:
        """
        Search for any known camera within arbitrary text.
        Returns canonical camera name if found, else None.
        """
        if not text:
            return None
        low = text.lower()
        # Direct containment of canonical names
        for cam in KNOWN_CAMERAS:
            if cam.lower() in low:
                return cam
        # Heuristic detection
        return self._canonical_camera(text)

    def _looks_like_lens(self, text: str) -> bool:
        """
        Heuristic check whether a text fragment looks like a lens description.
        """
        if not text:
            return False
        low = text.lower()
        if "lens" in low:
            return True
        if "fisheye" in low or "teleconverter" in low or "pancake" in low:
            return True
        if re.search(r"\b\d{2,3}\s*mm\b", low):
            return True
        if re.search(r"\bf\s*/?\s*\d+(\.\d+)?", low):
            return True
        if re.search(r"\bf\d+(\.\d+)?", low):
            return True
        return False

    def _is_location_phrase(self, text: str) -> bool:
        """
        Determine if the text is likely a location phrase rather than a camera.
        Prioritize simple leading prepositions typical of location descriptions.
        """
        if not text:
            return False
        return bool(re.match(r"^\s*(?:around|at|in)\b", text.strip(), flags=re.IGNORECASE))

    def _finalize_entry(self, e: FilmEntry) -> None:
        """
        Normalize and correct fields to satisfy the constraints:
        - Camera must be a known camera or set to 'Unknown'
        - Location phrases mistakenly set as camera should be moved to Shot Location
        - If camera appears in the Lens value, correct it
        """
        # If camera contains a location phrase, move it
        if e.camera and self._is_location_phrase(e.camera):
            raw = e.camera
            e.camera = ""
            # Append to notes for traceability
            e.notes = (
                f"{e.notes}; Camera (raw -> location): {raw}".strip("; ").strip()
                if e.notes
                else f"Camera (raw -> location): {raw}"
            )
            # Do not drop the preposition (natural phrasing)
            e.shot_location = raw if not e.shot_location else e.shot_location

        # If lens accidentally contains a camera name, correct it
        if e.lens:
            cam_in_lens = self._find_known_camera_in_text(e.lens)
            if cam_in_lens:
                # Move detected camera
                e.camera = cam_in_lens
                # Preserve original lens text if it doesn't look like a lens
                if not self._looks_like_lens(e.lens):
                    e.notes = (
                        f"{e.notes}; Lens (raw contained camera): {e.lens}".strip("; ").strip()
                        if e.notes
                        else f"Lens (raw contained camera): {e.lens}"
                    )
                    e.lens = ""
            # else leave lens as-is

        # Canonicalize/validate camera
        if e.camera:
            canon = self._canonical_camera(e.camera)
            if canon is None:
                # Unknown camera; preserve raw to notes and set to Unknown
                e.notes = (
                    f"{e.notes}; Camera (raw): {e.camera}".strip("; ").strip()
                    if e.notes
                    else f"Camera (raw): {e.camera}"
                )
                e.camera = "Unknown"
            else:
                e.camera = canon
        else:
            # Try to infer camera from notes if present
            cam_from_notes = self._find_known_camera_in_text(e.notes) if e.notes else None
            if cam_from_notes:
                e.camera = cam_from_notes
            else:
                e.camera = "Unknown"

    def count_input_entries(self, content: str) -> int:
        """
        Count the number of intended entries in the raw input by looking for
        main-entry markers, even if accidentally indented inside a previous block.

        We consider a line an entry start if it matches one of:
        - ^\\s{0,3}-\\s+Filmstock(:|\\s+.+:\\s*$)
        - ^\\s{0,3}-\\s+\\d+x\\s+
        """
        count = 0
        for raw in content.splitlines():
            line = raw.rstrip("\n")
            if re.match(r"^\s{0,3}-\s+Filmstock(?::|\s+.+:\s*$)", line):
                count += 1
            elif re.match(r"^\s{0,3}-\s+\d+x\s+", line, flags=re.IGNORECASE):
                count += 1
        return count

    def normalize_date(self, date_str: str) -> str:
        """
        Normalize a date string into a consistent format if possible.

        If the date is ambiguous but contains meaningful text (e.g. "Unknown, likely 2026"),
        return a cleaned, human-readable normalization while preserving semantics.

        Args:
            date_str: Raw date string.

        Returns:
            A normalized date string (e.g., YYYY-MM-DD), "Unknown", "Unknown, likely YYYY",
            or the original text if no recognized format is found.

        Examples:
            >>> CatalogConverter().normalize_date("04/05/24")
            '2024-04-05'
            >>> CatalogConverter().normalize_date("4/5/2024")
            '2024-04-05'
            >>> CatalogConverter().normalize_date("2024-09-07")
            '2024-09-07'
            >>> CatalogConverter().normalize_date("May 1, 2023")
            '2023-05-01'
            >>> CatalogConverter().normalize_date("Unknown")
            'Unknown'
            >>> CatalogConverter().normalize_date("expiration unknown, likely expired")
            'Unknown'
            >>> CatalogConverter().normalize_date("Expires 09/2025")
            '2025-09-01'
        """
        if not date_str:
            return ""

        ds = date_str.strip()
        dslow = ds.lower()

        # Unknown cases
        if "unknown" in dslow:
            # Preserve "Unknown, likely YYYY" when present
            likely = re.search(r"likely\s+(\d{4})", ds, flags=re.IGNORECASE)
            if likely:
                return f"Unknown, likely {likely.group(1)}"
            return "Unknown"

        # Remove leading "expiration" or "expires" prefixes for normalization
        ds_clean = re.sub(r"^(?:expiration|expires):?\s*", "", ds, flags=re.IGNORECASE).strip()

        # YYYY-MM-DD
        m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})$", ds_clean)
        if m:
            y, mo, d = m.groups()
            return f"{y}-{int(mo):02d}-{int(d):02d}"

        # MM/DD/YYYY or M/D/YY
        m = re.match(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})$", ds_clean)
        if m:
            mo, d, y = m.groups()
            if len(y) == 2:
                y = f"20{y}" if int(y) <= 30 else f"19{y}"
            return f"{y}-{int(mo):02d}-{int(d):02d}"

        # MM/YYYY (normalize to first of month)
        m = re.match(r"^(\d{1,2})[/-](\d{2,4})$", ds_clean)
        if m:
            mo, y = m.groups()
            if len(y) == 2:
                y = f"20{y}" if int(y) <= 30 else f"19{y}"
            return f"{y}-{int(mo):02d}-01"

        # Month name maps
        month_map = {
            "jan": "01",
            "january": "01",
            "feb": "02",
            "february": "02",
            "mar": "03",
            "march": "03",
            "apr": "04",
            "april": "04",
            "may": "05",
            "jun": "06",
            "june": "06",
            "jul": "07",
            "july": "07",
            "aug": "08",
            "august": "08",
            "sep": "09",
            "sept": "09",
            "september": "09",
            "oct": "10",
            "october": "10",
            "nov": "11",
            "november": "11",
            "dec": "12",
            "december": "12",
        }

        # Month DD, YYYY or Month DD YYYY
        m = re.match(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{2,4})$", ds_clean)
        if m:
            mon, d, y = m.groups()
            mon_num = month_map.get(mon.lower())
            if mon_num:
                if len(y) == 2:
                    y = f"20{y}" if int(y) <= 30 else f"19{y}"
                return f"{y}-{mon_num}-{int(d):02d}"

        # DD Month YYYY
        m = re.match(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{2,4})$", ds_clean)
        if m:
            d, mon, y = m.groups()
            mon_num = month_map.get(mon.lower())
            if mon_num:
                if len(y) == 2:
                    y = f"20{y}" if int(y) <= 30 else f"19{y}"
                return f"{y}-{mon_num}-{int(d):02d}"

        # Unrecognized: return the original
        self.logger.debug("Could not normalize date format: %s", ds)
        return ds

    def parse_entries(self, content: str) -> list[FilmEntry]:
        """
        Parse mixed-format markdown content into a sequence of FilmEntry objects.

        Supports:
        - Legacy "old - unstructured/structured" blocks:
          - Top line like: "- 1x Kodak Color Plus"
          - Indented sub-lines prefixed by "    - ..."
        - New format variants:
          - "- Filmstock: 1x Kodak ..."
          - "- Filmstock 1x Kodak ...:"
          - Indented sub-lines as "    - Key: Value"

        Args:
            content: The markdown content to parse.

        Returns:
            A list of FilmEntry objects in the original order encountered.

        Data preservation:
        Any line that cannot be mapped to a known field is appended to `notes` to avoid data loss.
        """
        entries: list[FilmEntry] = []
        lines = content.splitlines()
        current: FilmEntry | None = None
        in_subentries = False
        current_is_new_format = False

        def flush_current() -> None:
            nonlocal current
            if current and (current.filmstock or current.quantity or current.notes):
                entries.append(current)
            current = None

        for ln, raw in enumerate(lines, start=1):
            line = raw.rstrip("\n")

            # Skip blank lines
            if not line.strip():
                continue

            try:
                # Detect "new format" main entry lines (allow small leading indentation)
                if re.match(r"^\s{0,3}-\s+Filmstock:\s*", line) or re.match(
                    r"^\s{0,3}-\s+Filmstock\s+.+:\s*$", line
                ):
                    flush_current()
                    current = FilmEntry()
                    in_subentries = True
                    current_is_new_format = True

                    # "- Filmstock: VALUE"
                    m = re.match(r"^\s{0,3}-\s+Filmstock:\s*(.+?)\s*$", line)
                    if m:
                        val = m.group(1).strip().rstrip(":")
                    else:
                        # "- Filmstock VALUE:"
                        m2 = re.match(r"^\s{0,3}-\s+Filmstock\s+(.+?):\s*$", line)
                        val = m2.group(1).strip() if m2 else ""

                    # Extract optional quantity like "1x Something"
                    qm = re.match(r"^(?P<qty>\d+x)\s+(?P<name>.+)$", val, flags=re.IGNORECASE)
                    if qm:
                        current.quantity = qm.group("qty").strip()
                        current.filmstock = qm.group("name").strip()
                    else:
                        current.filmstock = val

                    self.logger.debug(
                        "New-format entry started: %s %s", current.quantity, current.filmstock
                    )
                    continue

                # Detect old-format main entry "- 1x Film..." (allow small leading indentation)
                if re.match(r"^\s{0,3}-\s+\d+x\s+", line, flags=re.IGNORECASE):
                    flush_current()
                    current = FilmEntry()
                    in_subentries = True
                    current_is_new_format = False

                    m = re.match(
                        r"^\s{0,3}-\s+(?P<qty>\d+x)\s+(?P<name>.+)$", line, flags=re.IGNORECASE
                    )
                    if m:
                        current.quantity = m.group("qty").strip()
                        current.filmstock = m.group("name").strip()
                    self.logger.debug(
                        "Old-format entry started: %s %s", current.quantity, current.filmstock
                    )
                    continue

                # Sub-entry lines "    - ..." (also guard against mistakenly nested new main entries)
                if line.startswith("    - ") and current and in_subentries:
                    trimmed = line.strip()
                    # If a new main entry was mistakenly indented, start a new entry
                    if re.match(r"^-\s+Filmstock\b", trimmed, flags=re.IGNORECASE) or re.match(
                        r"^-\s+\d+x\b", trimmed, flags=re.IGNORECASE
                    ):
                        flush_current()
                        current = FilmEntry()
                        in_subentries = True
                        current_is_new_format = bool(
                            re.match(r"^-\s+Filmstock\b", trimmed, flags=re.IGNORECASE)
                        )
                        if current_is_new_format:
                            # Parse filmstock value from trimmed
                            m = re.match(r"^-\s+Filmstock:\s*(.+?)\s*$", trimmed)
                            if m:
                                val = m.group(1).strip().rstrip(":")
                            else:
                                m2 = re.match(r"^-\s+Filmstock\s+(.+?):\s*$", trimmed)
                                val = m2.group(1).strip() if m2 else ""
                            qm = re.match(
                                r"^(?P<qty>\d+x)\s+(?P<name>.+)$", val, flags=re.IGNORECASE
                            )
                            if qm:
                                current.quantity = qm.group("qty").strip()
                                current.filmstock = qm.group("name").strip()
                            else:
                                current.filmstock = val
                        else:
                            m = re.match(
                                r"^-\s+(?P<qty>\d+x)\s+(?P<name>.+)$", trimmed, flags=re.IGNORECASE
                            )
                            if m:
                                current.quantity = m.group("qty").strip()
                                current.filmstock = m.group("name").strip()
                        continue

                    if current_is_new_format:
                        self._parse_new_sub_entry(line, current, ln)
                    else:
                        self._parse_old_sub_entry(line, current, ln)
                    continue

                # Any other content within a block becomes part of notes to avoid loss
                if current and in_subentries:
                    extra = line.strip()
                    if extra:
                        if current.notes:
                            current.notes += f"; {extra}"
                        else:
                            current.notes = extra
                    continue

                # If we reach here, the line format is not recognized and not part of a current block.
                self.logger.warning("Line %d: Unrecognized top-level line: %s", ln, line[:80])

            except Exception as exc:
                self.logger.error("Line %d: Error parsing line: %s", ln, exc)

        # Flush the last open entry
        flush_current()
        self.logger.info("Parsed %d film entries", len(entries))
        return entries

    def _parse_old_sub_entry(self, line: str, entry: FilmEntry, line_num: int) -> None:
        """
        Parse an "old format" sub-entry line (prefix: '    - ').

        Known patterns extracted:
        - "ISO 200"
        - "24 exposure" / "36 exposures"
        - "expiration unknown, likely expired" or "expires 09/2025"
        - "loaded 01/23/23" / "loaded on 4/4/24" / "loaded in CAMERA with LENS around PLACE"
        - "shot on CAMERA" / "shot in CAMERA with LENS around/at/in LOCATION ..."
        - "ready ... as of DATE" or similar
        - "developed 4/17/24 at Citizens PDX"
        - "roll 4726"
        - Free-form description lines become notes
        """
        content = line[6:].strip()  # remove "    - "
        lcl = content.lower()

        try:
            # ISO
            if lcl.startswith("iso "):
                entry.iso = content[4:].strip()
                return

            # Exposures "NN exposure(s)"
            m = re.search(r"\b(\d+)\s+exposure(s)?\b", content, flags=re.IGNORECASE)
            if m:
                entry.exposures = m.group(1)
                return

            # Expiration/Expires
            if "expiration" in lcl or lcl.startswith("expires"):
                raw_val = content
                if lcl.startswith("expires"):
                    raw_val = content.split(" ", 1)[1].strip() if " " in content else ""
                else:
                    raw_val = re.sub(r"^expiration:?\s*", "", content, flags=re.IGNORECASE).strip()

                if not raw_val or "unknown" in raw_val.lower():
                    # Cannot determine; put details in notes but leave field empty to become "None"
                    note = f"Expiration info: {raw_val or 'Unknown'}"
                    entry.notes = (
                        f"{entry.notes}; {note}".strip("; ").strip() if entry.notes else note
                    )
                else:
                    entry.expiration = self.normalize_date(raw_val)
                return

            # Loaded
            if lcl.startswith("loaded "):
                loaded_text = content[7:].strip()

                # Extract date if present
                dm = self.date_pattern.search(loaded_text)
                if dm:
                    entry.loaded_date = self.normalize_date(dm.group(1))

                # Try camera/lens extraction: "in CAMERA with LENS ..." or "on DATE"
                if " in " in loaded_text:
                    segment = loaded_text.split(" in ", 1)[1]
                    if " with " in segment:
                        cam, ln = segment.split(" with ", 1)
                        entry.camera = cam.strip()
                        entry.lens = ln.strip()
                    else:
                        entry.camera = segment.strip()
                elif "on " in loaded_text:
                    after = loaded_text.split("on ", 1)[1]
                    dm2 = self.date_pattern.search(after)
                    if dm2:
                        entry.loaded_date = self.normalize_date(dm2.group(1))
                return

            # Shot on CAMERA
            if lcl.startswith("shot on "):
                entry.camera = content[8:].strip()
                return

            # Shot ... location/camera cues
            if lcl.startswith("shot "):
                shot_text = content[5:].strip()

                # Prefer explicit location phrases first
                loc_match = re.search(
                    r"\b(?:around|at|in)\s+(?P<loc>.+)$", shot_text, flags=re.IGNORECASE
                )
                if loc_match:
                    entry.shot_location = loc_match.group("loc").strip()

                # If there is a "with ..." segment, inspect it
                with_match = re.search(r"\bwith\s+(?P<with>.+)$", shot_text, flags=re.IGNORECASE)
                if with_match:
                    with_val = with_match.group("with").strip()
                    # If "with" contains a known camera, prefer to set camera from it
                    cam_found = self._find_known_camera_in_text(with_val)
                    if cam_found:
                        entry.camera = cam_found
                    else:
                        # Likely a lens description, keep if it looks like a lens
                        if self._looks_like_lens(with_val):
                            entry.lens = with_val
                        else:
                            entry.notes = (
                                f"{entry.notes}; {content}".strip("; ").strip()
                                if entry.notes
                                else content
                            )
                else:
                    # No "with": try to find a known camera anywhere in the text
                    cam_found = self._find_known_camera_in_text(shot_text)
                    if cam_found:
                        entry.camera = cam_found

                # If neither location nor camera were confidently extracted, preserve to notes
                if not entry.shot_location and not entry.camera and not entry.lens:
                    entry.notes = (
                        f"{entry.notes}; {content}".strip("; ").strip() if entry.notes else content
                    )
                return

            # Ready for development (various phrasings)
            if "ready" in lcl:
                dm = self.date_pattern.search(content)
                if dm:
                    entry.ready_date = self.normalize_date(dm.group(1))
                else:
                    entry.notes = (
                        f"{entry.notes}; {content}".strip("; ").strip() if entry.notes else content
                    )
                return

            # Developed DATE at LOCATION
            if lcl.startswith("developed "):
                dev_text = content[10:].strip()
                dm = self.date_pattern.search(dev_text)
                if dm:
                    entry.developed_date = self.normalize_date(dm.group(1))
                if " at " in dev_text:
                    entry.developed_location = dev_text.split(" at ", 1)[1].strip()
                return

            # Roll number
            if lcl.startswith("roll "):
                entry.roll_num = content[5:].strip()
                return

            # Quick location-only lines like "at X" / "around X" / "in X"
            if lcl.startswith("at ") or lcl.startswith("around ") or lcl.startswith("in "):
                # Keep the preposition for natural phrasing
                entry.shot_location = content.strip()
                return

            # Subject (explicit)
            if lcl.startswith("subject"):
                entry.subject = (
                    content.split(":", 1)[1].strip() if ":" in content else content[7:].strip()
                )
                return

            # Filter (explicit)
            if lcl.startswith("filter"):
                entry.filter = (
                    content.split(":", 1)[1].strip() if ":" in content else content[6:].strip()
                )
                return

            # Notes (explicit)
            if lcl.startswith("notes"):
                val = content.split(":", 1)[1].strip() if ":" in content else content[5:].strip()
                entry.notes = f"{entry.notes}; {val}".strip("; ").strip() if entry.notes else val
                return

            # Fallback into notes to avoid data loss
            entry.notes = (
                f"{entry.notes}; {content}".strip("; ").strip() if entry.notes else content
            )

        except Exception as exc:
            logging.getLogger(__name__).error(
                "Line %d: Error parsing old sub-entry '%s': %s", line_num, content, exc
            )

    def _parse_new_sub_entry(self, line: str, entry: FilmEntry, line_num: int) -> None:
        """
        Parse a "new format" sub-entry line: "    - Key: Value". Unknown keys are appended to notes.

        Special handling:
        - Expiration with 'Unknown' or empty goes to notes (field remains empty to become 'None' at render).
        - Dates are normalized when parseable; otherwise, text is appended to notes.
        """
        content = line[6:].strip()  # remove "    - "
        if not content:
            return

        try:
            if ":" not in content:
                lcl = content.lower().strip()
                # Treat free-form location cues as Shot Location
                if lcl.startswith("at ") or lcl.startswith("around ") or lcl.startswith("in "):
                    entry.shot_location = content.strip()
                else:
                    entry.notes = (
                        f"{entry.notes}; {content}".strip("; ").strip() if entry.notes else content
                    )
                return

            raw_key, raw_val = content.split(":", 1)
            key = raw_key.strip().lower()
            val = raw_val.strip()

            def note_append(prefix: str, v: str) -> None:
                if not v:
                    return
                frag = f"{prefix}: {v}"
                entry.notes = f"{entry.notes}; {frag}".strip("; ").strip() if entry.notes else frag

            if key == "iso":
                entry.iso = val
            elif key == "exposures":
                m = re.search(r"\d+", val)
                entry.exposures = m.group(0) if m else val
            elif key == "expiration":
                if not val or "unknown" in val.lower():
                    note_append("Expiration", val or "Unknown")
                else:
                    entry.expiration = self.normalize_date(val)
            elif key == "loaded date":
                if val:
                    m = self.date_pattern.search(val)
                    if m:
                        entry.loaded_date = self.normalize_date(m.group(1))
                    else:
                        note_append("Loaded Date", val)
            elif key == "camera":
                # If camera value looks like a location phrase, move it to Shot Location
                if re.match(r"^(?:around|at|in)\b", val, flags=re.IGNORECASE):
                    # Preserve original camera text to notes for traceability
                    entry.notes = (
                        f"{entry.notes}; Camera (raw -> location): {val}".strip("; ").strip()
                        if entry.notes
                        else f"Camera (raw -> location): {val}"
                    )
                    entry.shot_location = val
                    entry.camera = ""
                else:
                    # Normalize to known cameras or "Unknown"
                    cam_canon = self._canonical_camera(val)
                    if cam_canon is None:
                        # Unknown camera; preserve raw
                        entry.notes = (
                            f"{entry.notes}; Camera (raw): {val}".strip("; ").strip()
                            if entry.notes
                            else f"Camera (raw): {val}"
                        )
                        entry.camera = "Unknown"
                    else:
                        entry.camera = cam_canon
            elif key == "lens":
                cam_found = self._find_known_camera_in_text(val)
                if cam_found:
                    # Mis-filed camera into lens; correct it
                    entry.camera = cam_found
                    # If the provided "lens" text doesn't resemble a lens, clear it and preserve to notes
                    if not self._looks_like_lens(val):
                        entry.notes = (
                            f"{entry.notes}; Lens (raw contained camera): {val}".strip("; ").strip()
                            if entry.notes
                            else f"Lens (raw contained camera): {val}"
                        )
                    entry.lens = ""
                else:
                    entry.lens = val
            elif key == "filter":
                entry.filter = val
            elif key == "notes":
                entry.notes = f"{entry.notes}; {val}".strip("; ").strip() if entry.notes else val
            elif key == "subject":
                entry.subject = val
            elif key == "shot location":
                entry.shot_location = val
            elif key == "ready for development date":
                if val:
                    m = self.date_pattern.search(val)
                    if m:
                        entry.ready_date = self.normalize_date(m.group(1))
                    else:
                        note_append("Ready for Development Date", val)
            elif key == "developed date":
                if val:
                    m = self.date_pattern.search(val)
                    if m:
                        entry.developed_date = self.normalize_date(m.group(1))
                    else:
                        note_append("Developed Date", val)
            elif key == "developed location":
                entry.developed_location = val
            elif key in ("rollnum", "roll num", "roll number"):
                entry.roll_num = val
            else:
                # Preserve unknown key/value
                note_append(raw_key.strip(), val)

        except Exception as exc:
            logging.getLogger(__name__).error(
                "Line %d: Error parsing new sub-entry '%s': %s", line_num, content, exc
            )

    async def convert_file(self, input_path: Path, output_path: Path) -> bool:
        """
        Convert a single markdown file to the standardized format.

        Steps:
        - Read the file
        - Parse entries (off-main-thread, CPU-bound regex)
        - Render in order
        - Write output file

        Args:
            input_path: Path to input markdown file.
            output_path: Path where the converted markdown will be written.

        Returns:
            True on success; False otherwise.
        """
        try:
            self.logger.info("Reading input file: %s", input_path)
            content = await asyncio.to_thread(input_path.read_text, encoding="utf-8")

            # Count expected top-level entries in the raw input
            expected_count = await asyncio.to_thread(self.count_input_entries, content)

            # Parse CPU-ish work off the event loop
            entries = await asyncio.to_thread(self.parse_entries, content)

            # Post-process entries (camera normalization, lens/camera swaps, location fixes)
            for e in entries:
                self._finalize_entry(e)

            self.logger.info(
                "Detected input entries: %d; Parsed entries: %d", expected_count, len(entries)
            )
            if expected_count != len(entries):
                self.logger.error(
                    "Fatal: input entries (%d) != output entries (%d)", expected_count, len(entries)
                )
                return False

            # Render output in order
            blocks: list[str] = []
            for i, e in enumerate(entries):
                if i > 0:
                    blocks.append("")
                blocks.append(e.to_markdown())

            render = "\n".join(blocks) + ("\n" if blocks else "")
            self.logger.info("Writing output file: %s", output_path)
            # Ensure parent directory exists without raising if it already does
            await asyncio.to_thread(output_path.parent.mkdir, parents=True, exist_ok=True)
            await asyncio.to_thread(output_path.write_text, render, "utf-8")

            self.logger.info("Successfully converted %d entries", len(entries))
            return True
        except Exception as exc:
            self.logger.error("Error converting file: %s", exc)
            return False


async def _run_self_tests() -> int:
    """
    Execute internal unit tests for parsing and rendering behavior.

    Returns:
        0 if tests pass; non-zero otherwise.
    """
    import unittest

    class ConverterTests(unittest.TestCase):
        def setUp(self) -> None:
            setup_logging(False)
            self.converter = CatalogConverter()

        def test_old_unstructured(self) -> None:
            src = """- 1x Fujifilm Fujicolor
    - ISO 200
    - 24 exposure
    - loaded 01/23/23
    - expiration unknown, likely expired
    - ready to get developed as of 2/12/23
"""
            entries = self.converter.parse_entries(src)
            self.assertEqual(len(entries), 1)
            e = entries[0]
            # Quantity and filmstock preserved
            self.assertEqual(e.quantity, "1x")
            self.assertIn("Fujifilm Fujicolor", e.filmstock)

            # Known fields
            self.assertEqual(e.iso, "200")
            self.assertEqual(e.exposures, "24")
            self.assertEqual(e.loaded_date, "2023-01-23")
            self.assertEqual(e.ready_date, "2023-02-12")

            # Expiration undetermined => empty field, note added, then rendered as "None"
            self.assertEqual(e.expiration, "")
            md = e.to_markdown()
            self.assertIn("- Expiration: None", md)
            self.assertIn("Expiration info:", md)

            # Developed Location defaults to Citizens PDX on render
            self.assertIn("- Developed Location: Citizens PDX", md)

        def test_old_structured(self) -> None:
            src = """- 1x Kodak Color Plus
    - ISO 200
    - 36 exposures
    - expires 09/2025
    - loaded on 4/4/24
    - shot in black Minolta SR-T101 with 28mm f2.5 around SE Portland flowers
    - ready for development as of 4/11/24
    - developed 4/17/24 at Citizens PDX
    - roll 4726
"""
            entries = self.converter.parse_entries(src)
            self.assertEqual(len(entries), 1)
            e = entries[0]
            self.assertEqual(e.iso, "200")
            self.assertEqual(e.exposures, "36")
            self.assertEqual(e.expiration, "2025-09-01")
            self.assertEqual(e.loaded_date, "2024-04-04")
            self.assertEqual(e.ready_date, "2024-04-11")
            self.assertEqual(e.developed_date, "2024-04-17")
            self.assertEqual(e.developed_location, "Citizens PDX")
            self.assertEqual(e.roll_num, "4726")
            md = e.to_markdown()
            self.assertIn("- Developed Location: Citizens PDX", md)

        def test_new_missing_fields(self) -> None:
            src = """- Filmstock: 1x Kodak Professional ProImage
    - ISO: 100
    - Exposures: 36
    - Expiration: expiration unknown, likely 2026
    - Loaded Date: 07/31/25
    - Camera: Nikon N80
    - Lens: 50mm f1.8
    - Shot Location: Inner SE Portland
    - Ready for Development Date: 08/02/25
    - Developed Date:
    - Developed Location: Citizens PDX
    - RollNum:
"""
            entries = self.converter.parse_entries(src)
            self.assertEqual(len(entries), 1)
            e = entries[0]
            # Expiration unknown should be appended to notes; field empty -> "None" in output
            self.assertEqual(e.expiration, "")
            md = e.to_markdown()
            self.assertIn("- Expiration: None", md)
            self.assertIn("Expiration:", md)  # preserved to notes
            self.assertIn("- Developed Location: Citizens PDX", md)  # provided explicitly

        def test_new_all_fields(self) -> None:
            src = """- Filmstock 1x Lomography Color '92 Sun-kissed:
    - ISO: 400
    - Exposures: 36
    - Expiration: 07/2027
    - Loaded Date: 09/18/21
    - Camera: Minolta SR-T101 silver
    - Lens: 58mm f1.4
    - Filter: None
    - Notes: formula 2023
    - Subject: Winston
    - Shot Location: Portland, OR
    - Ready for Development Date: 09/19/25
    - Developed Date:
    - Developed Location: Citizens PDX
    - RollNum:
"""
            entries = self.converter.parse_entries(src)
            self.assertEqual(len(entries), 1)
            e = entries[0]
            self.assertEqual(e.iso, "400")
            self.assertEqual(e.exposures, "36")
            # Month/Year for expiration => normalized to first of month
            self.assertEqual(e.expiration, "2027-07-01")
            self.assertEqual(e.loaded_date, "2021-09-18")
            self.assertEqual(e.camera, "Minolta SR-T101 silver")
            self.assertEqual(e.lens, "58mm f1.4")
            self.assertIn("formula 2023", e.notes)
            self.assertEqual(e.subject, "Winston")
            self.assertEqual(e.shot_location, "Portland, OR")
            self.assertEqual(e.ready_date, "2025-09-19")
            self.assertEqual(e.developed_date, "")
            self.assertEqual(e.developed_location, "Citizens PDX")
            md = e.to_markdown()
            # Empty developed date -> "None"
            self.assertIn("- Developed Date: None", md)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ConverterTests)
    res = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if res.wasSuccessful() else 1


async def main() -> None:
    """
    CLI entry point.

    Flags:
      -i/--input  : Input markdown file path.
      -o/--output : Output markdown file path.
      -v/--verbose: Enable verbose logging.
      --self-test : Run internal unit tests and exit.
    """
    parser = argparse.ArgumentParser(
        description="Convert mixed-format film catalog markdown into standardized entries."
    )
    parser.add_argument("-i", "--input", type=Path, help="Input markdown file path")
    parser.add_argument("-o", "--output", type=Path, help="Output markdown file path")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--self-test", action="store_true", help="Run internal tests and exit")

    args = parser.parse_args()
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    if args.self_test:
        code = await _run_self_tests()
        sys.exit(code)

    # Validate required args for normal conversion
    if not args.input or not args.output:
        parser.error("--input and --output are required unless --self-test is provided")

    if not args.input.exists():
        logger.error("Input file does not exist: %s", args.input)
        sys.exit(1)
    if not args.input.is_file():
        logger.error("Input path is not a file: %s", args.input)
        sys.exit(1)

    # Ensure output directory
    args.output.parent.mkdir(parents=True, exist_ok=True)

    converter = CatalogConverter()
    ok = await converter.convert_file(args.input, args.output)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
