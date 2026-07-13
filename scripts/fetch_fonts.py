"""
One-time setup: download the UI's fonts from Google Fonts into
interface\\ui\\fonts\\ and generate fonts.css with @font-face rules.

Run once with internet:  python scripts/fetch_fonts.py
After that the app never touches the network for fonts (offline invariant).
"""

import re
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "interface" / "ui" / "fonts"

# The exact families/weights the approved UI design uses.
FAMILIES = [
    ("Space Grotesk", [400, 500, 600, 700]),
    ("Inter", [400, 450, 500, 600]),
    ("JetBrains Mono", [400, 500, 600]),
]

# A browser User-Agent makes Google serve modern woff2.
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}


def main():
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    css_out = []

    for family, weights in FAMILIES:
        wght = ";".join(str(w) for w in weights)
        url = (f"https://fonts.googleapis.com/css2?"
               f"family={family.replace(' ', '+')}:wght@{wght}&display=swap")
        css = requests.get(url, headers=UA, timeout=30).text

        # Keep only the latin blocks; each has a woff2 URL and a weight.
        for block in re.findall(r"/\* latin \*/\s*@font-face\s*{[^}]+}", css):
            weight = re.search(r"font-weight:\s*(\d+)", block).group(1)
            src = re.search(r"url\((https://[^)]+\.woff2)\)", block).group(1)
            fname = f"{family.replace(' ', '')}-{weight}.woff2"
            (FONT_DIR / fname).write_bytes(
                requests.get(src, headers=UA, timeout=30).content)
            css_out.append(
                f"@font-face{{font-family:'{family}';font-style:normal;"
                f"font-weight:{weight};font-display:swap;"
                f"src:url('fonts/{fname}') format('woff2');}}"
            )
            print(f"  {fname}")

    (ROOT / "interface" / "ui" / "fonts.css").write_text(
        "\n".join(css_out) + "\n", encoding="utf-8")
    print(f"Done: {len(css_out)} font files + fonts.css")


if __name__ == "__main__":
    main()
