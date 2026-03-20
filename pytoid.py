#!/usr/bin/env python3
"""
Count PDF dictionary tags and structural tokens while skipping stream data.

Counts:
- Dictionary name tags inside dictionaries, e.g. /JavaScript, /Page, /AA, /JS
- Structural PDF tokens: obj, endobj, stream, endstream, xref, startxref, %%EOF

Important behavior:
- Stream contents are skipped to avoid false positives from binary data.
- Dictionary tags are counted only when inside << ... >> dictionaries.
- Works on raw bytes, not via a PDF library parser.

Usage:
    python pytoid.py sample.pdf
    python pytoid.py sample.pdf --json
    python pytoid.py sample.pdf --pdfid
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass
from typing import Optional
from xml.sax.saxutils import escape


WHITESPACE = b" \t\n\r\x0c\x00"
DELIMITERS = b"()<>[]{}/%"


@dataclass
class ScanResult:
    dictionary_tags: Counter
    dictionary_tag_hexcodes: Counter
    tokens: Counter
    dates: list[tuple[str, str]]


PDFID_VERSION = "0.0.4"
PDFID_KEYWORDS = [
    "obj",
    "endobj",
    "stream",
    "endstream",
    "xref",
    "trailer",
    "startxref",
    "/Page",
    "/Encrypt",
    "/ObjStm",
    "/JS",
    "/JavaScript",
    "/AA",
    "/OpenAction",
    "/AcroForm",
    "/JBIG2Decode",
    "/RichMedia",
    "/Launch",
    "/EmbeddedFile",
    "/XFA",
]
_hex_escape_re = re.compile(rb"#([0-9A-Fa-f]{2})")
_pdf_header_re = re.compile(rb"%PDF-\d\.\d")


def is_whitespace_byte(b: int) -> bool:
    return b in WHITESPACE


def is_delimiter_byte(b: int) -> bool:
    return b in DELIMITERS


def is_regular_token_char(b: int) -> bool:
    return not is_whitespace_byte(b) and not is_delimiter_byte(b)


def skip_whitespace(data: bytes, i: int) -> int:
    n = len(data)
    while i < n and is_whitespace_byte(data[i]):
        i += 1
    return i


def skip_comment(data: bytes, i: int) -> int:
    n = len(data)
    if i < n and data[i] == ord("%"):
        while i < n and data[i] not in (ord("\n"), ord("\r")):
            i += 1
    return i


def skip_ws_and_comments(data: bytes, i: int) -> int:
    n = len(data)
    while i < n:
        start = i
        i = skip_whitespace(data, i)
        if i < n and data[i] == ord("%"):
            i = skip_comment(data, i)
            continue
        if i == start:
            break
    return i


def read_regular_token(data: bytes, i: int) -> tuple[Optional[bytes], int]:
    n = len(data)
    if i >= n or not is_regular_token_char(data[i]):
        return None, i
    start = i
    while i < n and is_regular_token_char(data[i]):
        i += 1
    return data[start:i], i


def read_name(data: bytes, i: int) -> tuple[Optional[bytes], int]:
    """
    Read a PDF name object beginning with '/'.
    Keeps hex escapes literally, e.g. /A#42C remains /A#42C.
    """
    n = len(data)
    if i >= n or data[i] != ord("/"):
        return None, i

    start = i
    i += 1
    while i < n and not is_whitespace_byte(data[i]) and not is_delimiter_byte(data[i]):
        i += 1
    return data[start:i], i


def skip_literal_string(data: bytes, i: int) -> int:
    """
    Skip (...) string, handling nesting and escapes.
    """
    n = len(data)
    if i >= n or data[i] != ord("("):
        return i

    i += 1
    depth = 1
    while i < n and depth > 0:
        b = data[i]
        if b == ord("\\"):
            i += 2
            continue
        if b == ord("("):
            depth += 1
        elif b == ord(")"):
            depth -= 1
        i += 1
    return i


def read_literal_string_value(data: bytes, i: int) -> tuple[Optional[str], int]:
    """
    Read (...) string and return its raw (latin-1) value without delimiters.
    Keeps escapes as-is to preserve original representation.
    """
    n = len(data)
    if i >= n or data[i] != ord("("):
        return None, i

    i += 1
    depth = 1
    out = bytearray()
    while i < n and depth > 0:
        b = data[i]
        if b == ord("\\"):
            out.append(b)
            i += 1
            if i < n:
                out.append(data[i])
                i += 1
            continue
        if b == ord("("):
            depth += 1
            if depth > 1:
                out.append(b)
            i += 1
            continue
        if b == ord(")"):
            depth -= 1
            if depth == 0:
                i += 1
                break
            out.append(b)
            i += 1
            continue
        out.append(b)
        i += 1

    return out.decode("latin-1", errors="replace"), i


def skip_hex_string(data: bytes, i: int) -> int:
    """
    Skip <...> hex string, but not dictionary start <<.
    """
    n = len(data)
    if i >= n or data[i] != ord("<"):
        return i
    if i + 1 < n and data[i + 1] == ord("<"):
        return i
    i += 1
    while i < n and data[i] != ord(">"):
        i += 1
    if i < n:
        i += 1
    return i


def is_token_boundary(data: bytes, start: int, end: int) -> bool:
    """
    Check that token is bounded by whitespace/delimiter/start/end.
    """
    left_ok = start == 0 or is_whitespace_byte(data[start - 1]) or is_delimiter_byte(data[start - 1])
    right_ok = end >= len(data) or is_whitespace_byte(data[end]) or is_delimiter_byte(data[end])
    return left_ok and right_ok


def find_token(data: bytes, token: bytes, start: int) -> int:
    """
    Find a token with PDF-like boundaries.
    """
    pos = start
    while True:
        pos = data.find(token, pos)
        if pos == -1:
            return -1
        end = pos + len(token)
        if is_token_boundary(data, pos, end):
            return pos
        pos += 1


_length_direct_re = re.compile(rb"/Length\s+(\d+)\b")


def extract_direct_length(dict_bytes: bytes) -> Optional[int]:
    """
    Try to read direct numeric /Length from the dictionary bytes.
    Does not resolve indirect references like '/Length 12 0 R'.
    """
    m = _length_direct_re.search(dict_bytes)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def skip_eol_after_stream_keyword(data: bytes, i: int) -> int:
    """
    After 'stream' there should be EOL: CRLF or LF or CR.
    """
    n = len(data)
    if i < n and data[i] == ord("\r"):
        i += 1
        if i < n and data[i] == ord("\n"):
            i += 1
    elif i < n and data[i] == ord("\n"):
        i += 1
    return i


def skip_stream_data(data: bytes, stream_keyword_start: int, last_dict_bytes: Optional[bytes]) -> tuple[int, bool]:
    """
    Returns:
      (index_after_endstream_or_best_effort_position, found_endstream)

    Strategy:
    1. If direct /Length exists, skip exactly that many bytes, then look for endstream nearby.
    2. Otherwise fallback to searching next 'endstream' token.
    """
    after_stream = stream_keyword_start + len(b"stream")
    stream_data_start = skip_eol_after_stream_keyword(data, after_stream)

    if last_dict_bytes is not None:
        length = extract_direct_length(last_dict_bytes)
        if length is not None:
            candidate = stream_data_start + length
            search_from = max(stream_data_start, candidate - 16)
            search_to = min(len(data), candidate + 64)
            pos = find_token(data[search_from:search_to], b"endstream", 0)
            if pos != -1:
                absolute = search_from + pos
                return absolute + len(b"endstream"), True

    pos = find_token(data, b"endstream", stream_data_start)
    if pos != -1:
        return pos + len(b"endstream"), True

    return len(data), False


def scan_pdf(data: bytes) -> ScanResult:
    dictionary_tags: Counter[str] = Counter()
    dictionary_tag_hexcodes: Counter[str] = Counter()
    tokens: Counter[str] = Counter()
    dates: list[tuple[str, str]] = []

    i = 0
    n = len(data)
    dict_depth = 0
    current_dict_start_stack: list[int] = []
    last_completed_dict_bytes: Optional[bytes] = None

    while i < n:
        i = skip_ws_and_comments(data, i)
        if i >= n:
            break

        # Dictionary start <<
        if data.startswith(b"<<", i):
            current_dict_start_stack.append(i)
            dict_depth += 1
            i += 2
            continue

        # Dictionary end >>
        if data.startswith(b">>", i):
            if dict_depth > 0:
                dict_depth -= 1
                if current_dict_start_stack:
                    start = current_dict_start_stack.pop()
                    last_completed_dict_bytes = data[start:i + 2]
            i += 2
            continue

        # Literal string
        if data[i] == ord("("):
            i = skip_literal_string(data, i)
            continue

        # Hex string
        if data[i] == ord("<") and not data.startswith(b"<<", i):
            i = skip_hex_string(data, i)
            continue

        # Name object /Something
        if data[i] == ord("/"):
            name_token, new_i = read_name(data, i)
            if name_token is not None:
                if dict_depth > 0:
                    name = name_token.decode("latin-1", errors="replace")
                    dictionary_tags[name] += 1

                    hexcode_count = len(_hex_escape_re.findall(name_token))
                    if hexcode_count:
                        dictionary_tag_hexcodes[name] += hexcode_count

                    if name.endswith("Date"):
                        value_start = skip_ws_and_comments(data, new_i)
                        if value_start < n and data[value_start] == ord("("):
                            date_value, value_end = read_literal_string_value(data, value_start)
                            if date_value is not None:
                                dates.append((name, date_value))
                                i = value_end
                                continue
                i = new_i
                continue

        # %%EOF
        if data.startswith(b"%%EOF", i):
            tokens["%%EOF"] += 1
            i += len(b"%%EOF")
            continue

        # Regular token
        token, new_i = read_regular_token(data, i)
        if token is not None:
            if token == b"obj":
                tokens["obj"] += 1
            elif token == b"endobj":
                tokens["endobj"] += 1
            elif token == b"xref":
                tokens["xref"] += 1
            elif token == b"trailer":
                tokens["trailer"] += 1
            elif token == b"startxref":
                tokens["startxref"] += 1
            elif token == b"stream":
                tokens["stream"] += 1
                i, found_endstream = skip_stream_data(data, i, last_completed_dict_bytes)
                if found_endstream:
                    tokens["endstream"] += 1
                continue

            i = new_i
            continue

        # Single unknown delimiter or byte
        i += 1

    return ScanResult(
        dictionary_tags=dictionary_tags,
        dictionary_tag_hexcodes=dictionary_tag_hexcodes,
        tokens=tokens,
        dates=dates,
    )


def print_text_report(result: ScanResult) -> None:
    print("Structural tokens:")
    for token in ["obj", "endobj", "stream", "endstream", "xref", "trailer", "startxref", "%%EOF"]:
        print(f"  {token}: {result.tokens.get(token, 0)}")

    print()
    print("Dictionary tags:")
    if not result.dictionary_tags:
        print("  (none found)")
        return

    for name, count in sorted(result.dictionary_tags.items(), key=lambda item: (-item[1], item[0])):
        print(f"  {name}: {count}")


def detect_pdf_header(data: bytes) -> str:
    """
    Return the first %PDF-x.y header seen near the file start, or empty string.
    """
    m = _pdf_header_re.search(data[:1024])
    if not m:
        return ""
    return m.group(0).decode("latin-1")


def calculate_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    total = len(data)
    entropy = 0.0
    for count in counts.values():
        p = count / total
        entropy -= p * math.log2(p)
    return entropy


def build_pdfid_xml(pdf_file: str, data: bytes, result: ScanResult) -> str:
    header = detect_pdf_header(data)
    is_pdf = bool(header)
    filename = os.path.basename(pdf_file)
    entropy = f"{calculate_entropy(data):.2f}"

    lines = [
        (
            f'<PDFiD ErrorOccured="False" ErrorMessage="" Filename="{escape(filename)}" '
            f'Header="{escape(header)}" IsPDF="{"True" if is_pdf else "False"}" '
            f'Version="{PDFID_VERSION}" Entropy="{entropy}">'
        ),
        "  <Keywords>",
    ]

    for keyword in PDFID_KEYWORDS:
        if keyword.startswith("/"):
            count = result.dictionary_tags.get(keyword, 0)
            hexcode_count = result.dictionary_tag_hexcodes.get(keyword, 0)
        else:
            count = result.tokens.get(keyword, 0)
            hexcode_count = 0
        lines.append(
            f'    <Keyword Count="{count}" HexcodeCount="{hexcode_count}" Name="{escape(keyword)}"/>'
        )

    lines.append("  </Keywords>")
    lines.append("  <Dates>")
    for name, value in result.dates:
        lines.append(f'    <Date Value="{escape(value)}" Name="{escape(name)}"/>')
    lines.append("  </Dates>")
    lines.append("</PDFiD>")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Count PDF dictionary tags and structural tokens while skipping stream contents."
    )
    parser.add_argument("pdf_file", help="Path to the PDF file")
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("--json", action="store_true", help="Output JSON")
    output_group.add_argument("--pdfid", action="store_true", help="Output PDFiD-like XML")
    args = parser.parse_args()

    try:
        with open(args.pdf_file, "rb") as f:
            data = f.read()
    except OSError as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        return 1

    result = scan_pdf(data)

    if args.json:
        payload = {
            "tokens": dict(result.tokens),
            "dictionary_tags": dict(sorted(result.dictionary_tags.items())),
            "dictionary_tag_hexcodes": dict(sorted(result.dictionary_tag_hexcodes.items())),
            "dates": [{"name": name, "value": value} for name, value in result.dates],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif args.pdfid:
        print(build_pdfid_xml(args.pdf_file, data, result))
    else:
        print_text_report(result)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
