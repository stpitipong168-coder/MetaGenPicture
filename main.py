"""
CLI entry point for MetaGenPicture.

Usage:
    python main.py --input photo.jpg
    python main.py --input photo.jpg --layout 1+4 --seed 99
    python main.py --input *.jpg --layout 2+3          # batch (glob)
"""

import argparse
import sys
from pathlib import Path
from PIL import Image

from splitter import split
from transformer import transform_all
from composer import compose

LAYOUTS = ("1+2", "1+3", "1+4", "2+3")


def process_one(input_path: Path, output_path: Path, layout: str, seed: int) -> None:
    print(f"[→] {input_path.name}")
    img = Image.open(input_path).convert("RGB")

    parts = split(img)
    print(f"    split: {len(parts)} sub-images")
    if len(parts) < 2:
        print("    SKIP: could not detect multiple photos.")
        return

    parts = transform_all(parts, base_seed=seed)
    result = compose(parts, layout=layout)
    result.save(output_path, quality=95)
    print(f"    saved: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="MetaGenPicture — collage re-composer")
    parser.add_argument("--input", "-i", required=True, nargs="+",
                        help="Input image(s) — supports multiple files")
    parser.add_argument("--output-dir", "-o", default=".",
                        help="Output directory (default: current dir)")
    parser.add_argument("--layout", "-l", default="1+3", choices=LAYOUTS,
                        help="Output layout: 1+2 / 1+3 / 1+4 / 2+3  (default: 1+3)")
    parser.add_argument("--seed", "-s", type=int, default=42,
                        help="Random seed for visual transforms (default: 42)")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    inputs = [Path(p) for p in args.input]
    missing = [p for p in inputs if not p.exists()]
    if missing:
        sys.exit(f"Error: file(s) not found — {missing}")

    for inp in inputs:
        out = out_dir / (inp.stem + "_out.jpg")
        process_one(inp, out, args.layout, args.seed)

    print(f"\nDone — {len(inputs)} file(s) processed → {out_dir}/")


if __name__ == "__main__":
    main()
