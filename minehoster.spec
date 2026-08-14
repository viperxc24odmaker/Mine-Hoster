# -*- mode: python ; coding: utf-8 -*-
import struct
import sys
import zlib
from pathlib import Path

block_cipher = None

# Generate a small dependency-free ICO at build time so the Windows executable,
# taskbar and window use a MineHoster-branded icon without requiring Pillow.
ICON_PATH = Path("minehoster_build_icon.ico")

def _png_rgba(width, height):
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            # Dark rounded-looking field with a bright M made from thick strokes.
            bg = (18, 22, 30, 255)
            accent = (92, 225, 166, 255)
            on_m = (
                34 <= x <= 66 and 42 <= y <= 176
            ) or (
                66 <= x <= 98 and 42 <= y <= 112 and abs((x - 82) - (y - 42) * 0.28) < 12
            ) or (
                98 <= x <= 130 and 42 <= y <= 112 and abs((x - 114) + (y - 42) * 0.28) < 12
            ) or (
                130 <= x <= 162 and 42 <= y <= 176
            )
            row.extend(accent if on_m else bg)
        rows.append(bytes(row))
    raw = b"".join(rows)
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def _write_ico(path):
    png = _png_rgba(192, 192)
    # ICO containing one 192x192 PNG image.
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png), 22)
    path.write_bytes(header + entry + png)


_write_ico(ICON_PATH)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[(str(ICON_PATH), 'assets')],
    hiddenimports=[
        'flet',
        'flet_core',
        'flet_runtime',
        'src.app',
        'src.theme',
        'src.server_manager',
        'src.version_fetcher',
        'src.playit',
        'toml',
        'src.views.dashboard',
        'src.views.create_server',
        'src.views.console',
        'src.views.files',
        'src.views.plugins',
        'src.views.players',
        'src.views.settings',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='MineHoster',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON_PATH),
)
