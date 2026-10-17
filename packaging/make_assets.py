"""Uygulama simgesini üretir: packaging/build/optimuslock.ico ve .png (yazı tipi gerekmez)."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
S = 512
im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
d.rounded_rectangle((16, 16, S - 16, S - 16), radius=110, fill=(30, 102, 245, 255))
d.ellipse((120, 120, S - 120, S - 120), outline=(255, 255, 255, 255), width=64)
im.save(out / "optimuslock.png")
im.save(out / "optimuslock.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("simgeler hazır")
