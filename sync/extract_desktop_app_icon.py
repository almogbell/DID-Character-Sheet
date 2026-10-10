from __future__ import annotations

import io
import struct
import sys
from pathlib import Path

import pefile
from PIL import Image

RT_ICON = 3
RT_GROUP_ICON = 14


def resource_bytes(pe: pefile.PE, type_id: int, name_id: int | None = None) -> bytes:
    root = getattr(pe, "DIRECTORY_ENTRY_RESOURCE", None)
    if root is None:
        raise RuntimeError("Executable has no resource directory")
    for type_entry in root.entries:
        if type_entry.id != type_id:
            continue
        for name_entry in type_entry.directory.entries:
            if name_id is not None and name_entry.id != name_id:
                continue
            lang_entries = name_entry.directory.entries
            if not lang_entries:
                continue
            data = lang_entries[0].data.struct
            return pe.get_data(data.OffsetToData, data.Size)
    raise RuntimeError(f"Resource type {type_id}, id {name_id} not found")


def extract_group_icon(exe_path: Path) -> bytes:
    pe = pefile.PE(str(exe_path), fast_load=False)
    pe.parse_data_directories(
        directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_RESOURCE"]]
    )
    group = resource_bytes(pe, RT_GROUP_ICON)
    if len(group) < 6:
        raise RuntimeError("Invalid group icon resource")
    reserved, icon_type, count = struct.unpack_from("<HHH", group, 0)
    if reserved != 0 or icon_type != 1 or count < 1:
        raise RuntimeError("Invalid Windows group icon header")

    parsed = []
    pos = 6
    for _ in range(count):
        if pos + 14 > len(group):
            raise RuntimeError("Truncated group icon resource")
        width, height, colors, reserved_byte, planes, bpp, size, resource_id = struct.unpack_from(
            "<BBBBHHIH", group, pos
        )
        pos += 14
        image_data = resource_bytes(pe, RT_ICON, resource_id)
        parsed.append((width, height, colors, reserved_byte, planes, bpp, image_data))

    offset = 6 + 16 * len(parsed)
    out = bytearray(struct.pack("<HHH", 0, 1, len(parsed)))
    blobs = bytearray()
    for width, height, colors, reserved_byte, planes, bpp, image_data in parsed:
        out.extend(
            struct.pack(
                "<BBBBHHII",
                width,
                height,
                colors,
                reserved_byte,
                planes,
                bpp,
                len(image_data),
                offset,
            )
        )
        blobs.extend(image_data)
        offset += len(image_data)
    out.extend(blobs)
    return bytes(out)


def save_largest_png(ico_bytes: bytes, output_path: Path) -> None:
    icon = Image.open(io.BytesIO(ico_bytes))
    frames = []
    frame_count = getattr(icon, "n_frames", 1)
    for index in range(frame_count):
        icon.seek(index)
        frame = icon.convert("RGBA").copy()
        frames.append(frame)
    if not frames:
        raise RuntimeError("No icon frames decoded")
    best = max(frames, key=lambda image: image.width * image.height)
    if best.width < 256 or best.height < 256:
        best = best.resize((512, 512), Image.Resampling.LANCZOS)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    best.save(output_path, "PNG")
    print(f"Saved desktop DID icon {best.width}x{best.height} to {output_path}")


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: extract_desktop_app_icon.py SETUP_EXE OUTPUT_PNG")
    exe_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    save_largest_png(extract_group_icon(exe_path), output_path)


if __name__ == "__main__":
    main()
