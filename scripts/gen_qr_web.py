#!/usr/bin/env python3
"""Сгенерировать qr-web.png в стиле презентации (фиолетовые точки)."""
from __future__ import annotations

import os
import sys

import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.colormasks import SolidFillColorMask
from qrcode.image.styles.moduledrawers import CircleModuleDrawer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "static", "presentation", "qr-web.png")

PURPLE = (124, 58, 237)


def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else os.getenv("PUBLIC_DEMO_URL", "http://139.100.227.156:8026/")
    url = url.rstrip("/") + "/"

    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=14, border=1)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=CircleModuleDrawer(),
        color_mask=SolidFillColorMask(back_color=(255, 255, 255), front_color=PURPLE),
    )
    img.save(OUT)
    print(f"QR web → {url}\nSaved: {OUT}")


if __name__ == "__main__":
    main()
