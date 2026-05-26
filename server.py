#!/usr/bin/env python3
import json
import math
import os
import re
import struct
import time
import unicodedata
import zlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


UNITS_PER_EM = 1000
ASCENT = 850
DESCENT = -180

INITIALS = ["ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"]
MEDIALS = ["ㅏ", "ㅐ", "ㅑ", "ㅒ", "ㅓ", "ㅔ", "ㅕ", "ㅖ", "ㅗ", "ㅘ", "ㅙ", "ㅚ", "ㅛ", "ㅜ", "ㅝ", "ㅞ", "ㅟ", "ㅠ", "ㅡ", "ㅢ", "ㅣ"]
FINALS = ["", "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ", "ㄻ", "ㄼ", "ㄽ", "ㄾ", "ㄿ", "ㅀ", "ㅁ", "ㅂ", "ㅄ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"]

MEDIAL_PARTS = {
    "ㅒ": ["ㅑ", "ㅣ"],
    "ㅖ": ["ㅕ", "ㅣ"],
    "ㅘ": ["ㅗ", "ㅏ"],
    "ㅙ": ["ㅗ", "ㅐ"],
    "ㅚ": ["ㅗ", "ㅣ"],
    "ㅝ": ["ㅜ", "ㅓ"],
    "ㅞ": ["ㅜ", "ㅔ"],
    "ㅟ": ["ㅜ", "ㅣ"],
    "ㅢ": ["ㅡ", "ㅣ"],
}

FINAL_PARTS = {
    "ㄳ": ["ㄱ", "ㅅ"],
    "ㄵ": ["ㄴ", "ㅈ"],
    "ㄶ": ["ㄴ", "ㅎ"],
    "ㄺ": ["ㄹ", "ㄱ"],
    "ㄻ": ["ㄹ", "ㅁ"],
    "ㄼ": ["ㄹ", "ㅂ"],
    "ㄽ": ["ㄹ", "ㅅ"],
    "ㄾ": ["ㄹ", "ㅌ"],
    "ㄿ": ["ㄹ", "ㅍ"],
    "ㅀ": ["ㄹ", "ㅎ"],
    "ㅄ": ["ㅂ", "ㅅ"],
}

VERTICAL_MEDIALS = set(["ㅏ", "ㅐ", "ㅑ", "ㅒ", "ㅓ", "ㅔ", "ㅕ", "ㅖ", "ㅣ"])
HORIZONTAL_MEDIALS = set(["ㅗ", "ㅛ", "ㅜ", "ㅠ", "ㅡ"])


def u16(value):
    return struct.pack(">H", value & 0xFFFF)


def i16(value):
    return struct.pack(">h", max(-32768, min(32767, int(round(value)))))


def u32(value):
    return struct.pack(">I", value & 0xFFFFFFFF)


def i32(value):
    return struct.pack(">i", int(value))


def fixed(value):
    return i32(int(value * 65536))


def long_datetime():
    # TrueType dates are seconds since 1904-01-01.
    return int(time.time()) + 2082844800


def pad4(data):
    return data + b"\0" * ((4 - len(data) % 4) % 4)


def checksum(data):
    padded = pad4(data)
    total = 0
    for index in range(0, len(padded), 4):
        total = (total + struct.unpack(">I", padded[index:index + 4])[0]) & 0xFFFFFFFF
    return total


def make_name_table(family):
    records = []
    strings = b""
    names = {
        1: family,
        2: "Regular",
        3: f"{family} Regular",
        4: f"{family} Regular",
        5: "Version 1.0",
        6: "".join(ch for ch in family if ch.isalnum()) + "-Regular",
    }
    for name_id, value in names.items():
        encoded = value.encode("utf-16-be")
        records.append((3, 1, 0x0409, name_id, len(encoded), len(strings)))
        strings += encoded
    header = u16(0) + u16(len(records)) + u16(6 + len(records) * 12)
    body = b"".join(u16(platform) + u16(encoding) + u16(language) + u16(name_id) + u16(length) + u16(offset)
                    for platform, encoding, language, name_id, length, offset in records)
    return header + body + strings


def simplify_points(points):
    cleaned = []
    for point in points:
        x = float(point.get("x", 0))
        y = float(point.get("y", 0))
        pressure = float(point.get("pressure", 0.55) or 0.55)
        if not cleaned or abs(cleaned[-1][0] - x) + abs(cleaned[-1][1] - y) > 3:
            cleaned.append((x, y, pressure))
    if len(cleaned) > 42:
        step = max(1, len(cleaned) // 42)
        cleaned = cleaned[::step]
    return cleaned


def bounds_for_strokes(strokes):
    xs = []
    ys = []
    for stroke in strokes:
        for point in stroke:
            xs.append(float(point.get("x", 0)))
            ys.append(float(point.get("y", 0)))
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def decompose_hangul(char):
    code = ord(char)
    if code < 0xAC00 or code > 0xD7A3:
        return None
    offset = code - 0xAC00
    return INITIALS[offset // 588], MEDIALS[(offset % 588) // 28], FINALS[offset % 28]


def glyph_profile(char):
    if char in "abcdefghijklmnopqrstuvwxyz":
        if char in "bdfhklt":
            return {"top": 700, "bottom": 0, "max_width": 610, "left": 45, "right": 55, "min_advance": 480}
        if char in "gjpqy":
            return {"top": 505, "bottom": -185, "max_width": 610, "left": 45, "right": 55, "min_advance": 500}
        if char in "mw":
            return {"top": 505, "bottom": 0, "max_width": 760, "left": 45, "right": 55, "min_advance": 650}
        if char in "il":
            return {"top": 700 if char == "l" else 505, "bottom": 0, "max_width": 300, "left": 35, "right": 35, "min_advance": 260}
        return {"top": 505, "bottom": 0, "max_width": 560, "left": 45, "right": 55, "min_advance": 450}
    if char in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        if char in "MW":
            return {"top": 735, "bottom": 0, "max_width": 860, "left": 45, "right": 60, "min_advance": 760}
        if char in "IJ":
            return {"top": 735, "bottom": -40 if char == "J" else 0, "max_width": 380, "left": 40, "right": 45, "min_advance": 330}
        return {"top": 735, "bottom": 0, "max_width": 700, "left": 45, "right": 60, "min_advance": 590}
    if char in "0123456789":
        return {"top": 690, "bottom": 0, "max_width": 620, "left": 45, "right": 55, "min_advance": 540}
    if char in ".,:'\"":
        return {"top": 210, "bottom": -40 if char in ",;" else 0, "max_width": 210, "left": 35, "right": 35, "min_advance": 190}
    if char in "()[]{}":
        return {"top": 760, "bottom": -90, "max_width": 330, "left": 28, "right": 28, "min_advance": 290}
    if char in "+-=±≠<>≤≥×÷":
        return {"top": 505, "bottom": 55, "max_width": 520, "left": 35, "right": 35, "min_advance": 430}
    if char in "/\\√∫∑":
        return {"top": 760, "bottom": -120, "max_width": 560, "left": 35, "right": 45, "min_advance": 450}
    if char in "^_":
        return {"top": 710 if char == "^" else -55, "bottom": 500 if char == "^" else -160, "max_width": 330, "left": 35, "right": 35, "min_advance": 280}
    if char in "∞πθΔ":
        return {"top": 660, "bottom": 0, "max_width": 650, "left": 45, "right": 55, "min_advance": 530}
    return {"top": 650, "bottom": 0, "max_width": 650, "left": 45, "right": 55, "min_advance": 520}


def normalize_point(point, bounds, canvas, profile):
    min_x, min_y, max_x, max_y = bounds
    width = max(1, max_x - min_x)
    height = max(1, max_y - min_y)
    target_h = max(1, profile["top"] - profile["bottom"])
    scale = min(profile["max_width"] / width, target_h / height)
    used_w = width * scale
    x = (point[0] - min_x) * scale + profile["left"]
    y = profile["top"] - (point[1] - min_y) * scale
    return x, y, point[2], scale


def stroke_to_contour(stroke, bounds, canvas, profile):
    points = simplify_points(stroke)
    if len(points) == 1:
        x, y, pressure, scale = normalize_point(points[0], bounds, canvas, profile)
        radius = 18 + pressure * 18
        return [
            (x - radius, y - radius),
            (x + radius, y - radius),
            (x + radius, y + radius),
            (x - radius, y + radius),
        ]
    if len(points) < 2:
        return []

    left = []
    right = []
    normalized = [normalize_point(point, bounds, canvas, profile) for point in points]
    for index, (x, y, pressure, scale) in enumerate(normalized):
        prev_point = normalized[max(0, index - 1)]
        next_point = normalized[min(len(normalized) - 1, index + 1)]
        dx = next_point[0] - prev_point[0]
        dy = next_point[1] - prev_point[1]
        length = math.hypot(dx, dy) or 1
        nx = -dy / length
        ny = dx / length
        width = 13 + pressure * 26
        left.append((x + nx * width, y + ny * width))
        right.append((x - nx * width, y - ny * width))
    return left + list(reversed(right))


def make_glyph(strokes, canvas, char):
    bounds = bounds_for_strokes(strokes)
    if not bounds:
        return b"\0\0\0\0\0\0\0\0\0\0", 0, 0, 0, 0, 500

    profile = glyph_profile(char)
    contours = []
    for stroke in strokes:
        contour = stroke_to_contour(stroke, bounds, canvas, profile)
        if len(contour) >= 3:
            contours.append(contour)
    if not contours:
        return b"\0\0\0\0\0\0\0\0\0\0", 0, 0, 0, 0, profile["min_advance"]

    all_points = [point for contour in contours for point in contour]
    x_min = math.floor(min(x for x, _ in all_points))
    y_min = math.floor(min(y for _, y in all_points))
    x_max = math.ceil(max(x for x, _ in all_points))
    y_max = math.ceil(max(y for _, y in all_points))

    end_pts = []
    flags = []
    x_coords = []
    y_coords = []
    prev_x = 0
    prev_y = 0
    cursor = -1
    for contour in contours:
        for x, y in contour:
            cursor += 1
            xi = int(round(x))
            yi = int(round(y))
            flags.append(0x01)
            x_coords.append(i16(xi - prev_x))
            y_coords.append(i16(yi - prev_y))
            prev_x = xi
            prev_y = yi
        end_pts.append(cursor)

    data = (
        i16(len(contours)) + i16(x_min) + i16(y_min) + i16(x_max) + i16(y_max) +
        b"".join(u16(point) for point in end_pts) +
        u16(0) +
        bytes(flags) +
        b"".join(x_coords) +
        b"".join(y_coords)
    )
    advance = max(profile["min_advance"], min(1000, x_max + profile["right"]))
    return data, x_min, y_min, x_max, y_max, advance


def transform_strokes_to_box(strokes, box):
    bounds = bounds_for_strokes(strokes)
    if not bounds:
        return []
    min_x, min_y, max_x, max_y = bounds
    source_w = max(1, max_x - min_x)
    source_h = max(1, max_y - min_y)
    x, y, width, height = box
    scale = min(width / source_w, height / source_h)
    used_w = source_w * scale
    used_h = source_h * scale
    dx = x + (width - used_w) / 2
    dy = y + (height - used_h) / 2

    transformed = []
    for stroke in strokes:
        out = []
        for point in stroke:
            out.append({
                "x": dx + (float(point.get("x", 0)) - min_x) * scale,
                "y": dy + (float(point.get("y", 0)) - min_y) * scale,
                "pressure": float(point.get("pressure", 0.55) or 0.55),
            })
        transformed.append(out)
    return transformed


def layout_for_hangul(initial, medial, final):
    has_final = bool(final)
    if medial in VERTICAL_MEDIALS:
        return {
            "initial": (145, 48, 330, 285 if has_final else 360),
            "medial": (430, 36, 320, 305 if has_final else 385),
            "final": (245, 305, 430, 118),
        }
    if medial in HORIZONTAL_MEDIALS:
        return {
            "initial": (230, 42, 440, 210 if has_final else 255),
            "medial": (175, 235 if has_final else 265, 560, 105),
            "final": (250, 335, 420, 92),
        }
    return {
        "initial": (145, 48, 320, 245 if has_final else 320),
        "medial": (405, 56, 340, 285 if has_final else 350),
        "final": (250, 315, 420, 105),
    }


def add_jamo_strokes(result, by_char, jamo, box):
    if not jamo:
        return
    parts = FINAL_PARTS.get(jamo) or MEDIAL_PARTS.get(jamo) or [jamo]
    if len(parts) == 1:
        source = by_char.get(parts[0])
        if source:
            result.extend(transform_strokes_to_box(source, box))
        return

    x, y, width, height = box
    if jamo in FINAL_PARTS:
        each = width / len(parts)
        for index, part in enumerate(parts):
            add_jamo_strokes(result, by_char, part, (x + each * index, y, each * 0.92, height))
    elif jamo in ["ㅘ", "ㅙ", "ㅚ"]:
        add_jamo_strokes(result, by_char, parts[0], (x, y + height * 0.45, width * 0.95, height * 0.5))
        add_jamo_strokes(result, by_char, parts[1], (x + width * 0.5, y, width * 0.45, height))
    elif jamo in ["ㅝ", "ㅞ", "ㅟ", "ㅢ"]:
        add_jamo_strokes(result, by_char, parts[0], (x, y + height * 0.42, width * 0.95, height * 0.5))
        add_jamo_strokes(result, by_char, parts[1], (x + width * 0.5, y, width * 0.45, height))
    else:
        add_jamo_strokes(result, by_char, parts[0], box)


def synthesize_hangul_strokes(char, by_char):
    parts = decompose_hangul(char)
    if not parts:
        return None
    initial, medial, final = parts
    layout = layout_for_hangul(initial, medial, final)
    strokes = []
    add_jamo_strokes(strokes, by_char, initial, layout["initial"])
    add_jamo_strokes(strokes, by_char, medial, layout["medial"])
    if final:
        add_jamo_strokes(strokes, by_char, final, layout["final"])
    return strokes or None


def empty_glyph():
    return b"\0\0\0\0\0\0\0\0\0\0", 0, 0, 0, 0, 500


def make_cmap(codepoints):
    seg_count = len(codepoints) + 1
    seg_count_x2 = seg_count * 2
    search_range = 2 * (2 ** int(math.log2(seg_count)))
    entry_selector = int(math.log2(search_range / 2))
    range_shift = seg_count_x2 - search_range

    end_codes = codepoints + [0xFFFF]
    start_codes = codepoints + [0xFFFF]
    id_deltas = [((index + 1) - codepoint) & 0xFFFF for index, codepoint in enumerate(codepoints)] + [1]
    id_range_offsets = [0] * seg_count
    subtable_length = 16 + seg_count * 8

    subtable = (
        u16(4) + u16(subtable_length) + u16(0) +
        u16(seg_count_x2) + u16(search_range) + u16(entry_selector) + u16(range_shift) +
        b"".join(u16(code) for code in end_codes) +
        u16(0) +
        b"".join(u16(code) for code in start_codes) +
        b"".join(u16(delta) for delta in id_deltas) +
        b"".join(u16(offset) for offset in id_range_offsets)
    )
    return u16(0) + u16(1) + u16(3) + u16(1) + u32(12) + subtable


def make_ttf(payload):
    family = payload.get("familyName") or "PersonalHandwriting"
    canvas = payload.get("canvas") or {"width": 900, "height": 460}
    samples = payload.get("samples") or []
    by_char = {}
    for sample in samples:
        char = sample.get("char")
        strokes = sample.get("strokes") or []
        if char and len(char) == 1 and strokes:
            by_char[char] = strokes

    target_text = payload.get("targetText") or ""
    target_chars = set(ch for ch in target_text if not ch.isspace())
    target_chars.update(by_char.keys())
    for char in list(target_chars):
        if char not in by_char and decompose_hangul(char):
            synthesized = synthesize_hangul_strokes(char, by_char)
            if synthesized:
                by_char[char] = synthesized

    codepoints = sorted(ord(char) for char in by_char)
    glyph_records = [empty_glyph()]
    x_min = 0
    y_min = 0
    x_max = 0
    y_max = 0
    for codepoint in codepoints:
        char = chr(codepoint)
        glyph, gx_min, gy_min, gx_max, gy_max, advance = make_glyph(by_char[char], canvas, char)
        glyph_records.append((glyph, gx_min, gy_min, gx_max, gy_max, advance))
        x_min = min(x_min, gx_min)
        y_min = min(y_min, gy_min)
        x_max = max(x_max, gx_max)
        y_max = max(y_max, gy_max)

    glyf = b""
    offsets = []
    for record in glyph_records:
        offsets.append(len(glyf))
        glyf += pad4(record[0])
    offsets.append(len(glyf))
    loca = b"".join(u32(offset) for offset in offsets)
    hmtx = b"".join(u16(record[5]) + i16(0) for record in glyph_records)

    now = long_datetime()
    head = (
        fixed(1.0) + fixed(1.0) + u32(0) + u32(0x5F0F3CF5) +
        u16(0x000B) + u16(UNITS_PER_EM) +
        struct.pack(">q", now) + struct.pack(">q", now) +
        i16(x_min) + i16(y_min) + i16(x_max) + i16(y_max) +
        u16(0) + u16(0) + i16(2) + i16(1) + i16(0)
    )
    hhea = (
        fixed(1.0) + i16(ASCENT) + i16(DESCENT) + i16(0) + u16(1000) +
        i16(0) + i16(0) + i16(1000) + i16(1) + i16(0) + i16(0) +
        i16(0) + i16(0) + i16(0) + i16(0) + i16(0) +
        u16(len(glyph_records))
    )
    maxp = fixed(1.0) + u16(len(glyph_records)) + u16(256) + u16(64) + u16(16) + u16(2) + u16(0) + u16(0) + u16(0) + u16(0) + u16(0) + u16(0) + u16(0) + u16(0) + u16(0)
    os2 = (
        u16(3) + i16(500) + u16(400) + u16(5) + i16(0) +
        i16(0) + i16(0) + i16(0) + i16(0) + i16(0) + i16(0) + i16(0) + i16(0) + i16(0) + i16(0) +
        i16(0) + i16(0) + i16(0) + i16(0) + b"PYFT" +
        u32(0) + u32(0) + u32(0) + u32(0) +
        b"\0" * 10 +
        u32(0) + u32(0) + u32(0) + u32(0) +
        i16(ASCENT) + i16(abs(DESCENT)) + i16(0) +
        u16(ASCENT) + u16(abs(DESCENT)) + i16(0) +
        u32(0) + u32(0) + i16(0) + i16(0) + u16(0)
    )
    post = fixed(3.0) + fixed(0) + i16(0) + i16(0) + u32(0) + u32(0) + u32(0) + u32(0) + u32(0)
    cmap = make_cmap(codepoints)
    name = make_name_table(family)

    tables = {
        "OS/2": os2,
        "cmap": cmap,
        "glyf": glyf,
        "head": head,
        "hhea": hhea,
        "hmtx": hmtx,
        "loca": loca,
        "maxp": maxp,
        "name": name,
        "post": post,
    }

    tags = sorted(tables)
    num_tables = len(tags)
    search_range = 16 * (2 ** int(math.log2(num_tables)))
    entry_selector = int(math.log2(search_range / 16))
    range_shift = num_tables * 16 - search_range
    offset_table = u32(0x00010000) + u16(num_tables) + u16(search_range) + u16(entry_selector) + u16(range_shift)

    directory = b""
    body = b""
    offset = 12 + num_tables * 16
    for tag in tags:
        data = pad4(tables[tag])
        directory += tag.encode("ascii") + u32(checksum(tables[tag])) + u32(offset) + u32(len(tables[tag]))
        body += data
        offset += len(data)

    font = bytearray(offset_table + directory + body)
    adjustment = (0xB1B0AFBA - checksum(font)) & 0xFFFFFFFF
    head_offset = 12 + tags.index("head") * 16
    table_offset = struct.unpack(">I", font[head_offset + 8:head_offset + 12])[0]
    font[table_offset + 8:table_offset + 12] = u32(adjustment)
    return bytes(font)


def decode_pdf_literal(value):
    value = value.replace(rb"\(", b"(").replace(rb"\)", b")").replace(rb"\\", b"\\")
    value = value.replace(rb"\n", b"\n").replace(rb"\r", b"\r").replace(rb"\t", b"\t")
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError:
        return value.decode("latin-1", errors="ignore")


def decode_pdf_hex(value):
    raw = re.sub(rb"\s+", b"", value)
    if len(raw) % 2:
        raw += b"0"
    try:
        data = bytes.fromhex(raw.decode("ascii"))
    except ValueError:
        return ""
    for encoding in ("utf-16-be", "utf-8", "latin-1"):
        try:
            return data.decode(encoding).lstrip("\ufeff")
        except UnicodeDecodeError:
            continue
    return ""


def clean_pdf_text(value):
    cleaned = []
    printable = 0
    total = 0
    for char in value:
      total += 1
      category = unicodedata.category(char)
      if char in "\n\r\t":
          cleaned.append(" ")
          printable += 1
      elif category.startswith("C"):
          continue
      elif char.isprintable():
          cleaned.append(char)
          printable += 1
    text = "".join(cleaned)
    text = re.sub(r"\s+", " ", text).strip()
    if not text or total == 0:
        return ""
    if printable / total < 0.78:
        return ""
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 +-*/=()[]{}.,:;_^<>≤≥±≠×÷√∑∫∞πθΔ\n")
    readable = sum(1 for char in text if char in allowed)
    if readable / max(1, len(text)) < 0.72:
        return ""
    return text


def extract_strings_from_pdf_bytes(data):
    chunks = []
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.S):
        stream = match.group(1)
        try:
            chunks.append(zlib.decompress(stream))
        except zlib.error:
            chunks.append(stream)

    text_parts = []
    for chunk in chunks:
        for literal in re.findall(rb"\((?:\\.|[^\\)])*\)", chunk):
            inner = literal[1:-1]
            decoded = clean_pdf_text(decode_pdf_literal(inner))
            if decoded.strip():
                text_parts.append(decoded)
        for hex_string in re.findall(rb"<([0-9A-Fa-f\s]{4,})>", chunk):
            decoded = clean_pdf_text(decode_pdf_hex(hex_string))
            if decoded.strip():
                text_parts.append(decoded)

    text = " ".join(text_parts)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class Handler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/api/extract":
            self.handle_extract()
            return

        if self.path != "/api/font":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            font = make_ttf(payload)
        except Exception as exc:
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(str(exc).encode("utf-8"))
            return

        self.send_response(200)
        self.send_header("Content-Type", "font/ttf")
        self.send_header("Content-Disposition", 'attachment; filename="personal-handwriting.ttf"')
        self.send_header("Content-Length", str(len(font)))
        self.end_headers()
        self.wfile.write(font)

    def handle_extract(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = self.rfile.read(length)
            content_type = self.headers.get("Content-Type", "")
            if "pdf" in content_type.lower():
                text = extract_strings_from_pdf_bytes(data)
            else:
                text = data.decode("utf-8", errors="ignore")
        except Exception as exc:
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(str(exc).encode("utf-8"))
            return

        body = json.dumps({"text": text}, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    server = ThreadingHTTPServer(("0.0.0.0", 3000), Handler)
    print("Serving Handwriting Font Lab on http://0.0.0.0:3000")
    server.serve_forever()
