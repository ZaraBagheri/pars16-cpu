#!/usr/bin/env python3
"""Export the actual CPU schematic using Digital's SVG renderer."""

import argparse
import re
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--digital-jar", required=True, type=Path)
    parser.add_argument("--java", default="java", help="Java executable (default: java)")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = root / "docs/images/pars16-schematic.svg"
    subprocess.run(
        [args.java, "-Djava.awt.headless=true", "-cp", str(args.digital_jar.resolve()),
         "CLI", "svg", str(root / "circuits/Pars16.dig"), "-svg", str(output)],
        check=True,
    )
    svg = output.read_text(encoding="utf-8")
    svg = re.sub(r"<!-- created: .*? -->\n", "", svg)
    match = re.search(r'viewBox="([\d. -]+)"', svg)
    if not match:
        raise ValueError("Digital's SVG export did not contain a viewBox")
    x, y, width, height = match.group(1).split()
    # Pixel dimensions render consistently in repository viewers and thumbnails.
    svg = re.sub(r'width="[\d.]+mm"', f'width="{width}"', svg, count=1)
    svg = re.sub(r'height="[\d.]+mm"', f'height="{height}"', svg, count=1)
    background = f'<rect x="{x}" y="{y}" width="{width}" height="{height}" fill="white"/>\n'
    svg = svg.replace('<g stroke-linecap="square">', background + '<g stroke-linecap="square">', 1)
    output.write_text(svg, encoding="utf-8")
    print(f"Exported {output.relative_to(root)}")


if __name__ == "__main__":
    main()
