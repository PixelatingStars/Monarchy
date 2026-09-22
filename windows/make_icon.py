"""Build the Windows icon from the supplied Monarchy crown artwork."""

from pathlib import Path

from PIL import Image


root = Path(__file__).resolve().parent
crown = Image.open(root / "assets" / "crown-icon.png").convert("RGBA")
crown = crown.crop(crown.getbbox())
crown.thumbnail((256, 256), Image.Resampling.LANCZOS)
icon = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
icon.alpha_composite(crown, ((256 - crown.width) // 2, (256 - crown.height) // 2))
icon.save(root / "assets" / "monarchy.ico", sizes=[(16, 16), (24, 24), (32, 32),
                                                     (48, 48), (64, 64), (128, 128),
                                                     (256, 256)])
