import json, pathlib
from collections import defaultdict

INPUT  = pathlib.Path(__file__).parents[3] / "data/bibles/1-enoch.json"
OUTPUT = pathlib.Path(__file__).parents[3] / "data/bibles/ENO.usfm"

def convert():
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    book = data["books"][0]

    # Group all verses by chapter number (merges split ch91)
    chapters = defaultdict(list)
    for ch in book["chapters"]:
        for v in ch["verses"]:
            chapters[ch["chapter"]].append(v)

    lines = [
        r"\id ENO",
        r"\usfm 3.0",
        r"\ide UTF-8",
        r"\h 1 Enoch",
        r"\toc1 The Book of Enoch",
        r"\toc2 1 Enoch",
        r"\toc3 Eno",
        r"\mt1 The Book of Enoch",
    ]

    total_dupes = 0
    for chapter_num in sorted(chapters.keys()):
        lines.append(f"\\c {chapter_num}")
        lines.append(r"\p")
        seen = set()
        for v in sorted(chapters[chapter_num], key=lambda v: v["verse"]):
            if v["verse"] in seen:
                total_dupes += 1
                continue  # Keep first occurrence, skip variants
            seen.add(v["verse"])
            # Collapse embedded newlines and normalize whitespace
            text = " ".join(v["text"].split())
            lines.append(f"\\v {v['verse']} {text}")

    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Written: {OUTPUT}  ({len(lines)} lines)")
    if total_dupes:
        print(f"Deduplicated: {total_dupes} manuscript variant verses skipped (kept first occurrence)")

if __name__ == "__main__":
    convert()
