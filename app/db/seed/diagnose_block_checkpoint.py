"""
Diagnostic: why does parse_block_files.py seem to reprocess files that
should be skipped by the checkpoint? Checks whether the checkpoint file is
even found, and whether currently-discovered file paths actually match its
keys -- a path-string mismatch (e.g. a remapped network drive) would cause
every single lookup to miss, which looks exactly like "processes
everything" even though the checkpoint has real entries in it.

Run:
    python diagnose_block_checkpoint.py
"""
from pathlib import Path
import json

BLOCK_FILE_DIRECTORY = Path("K:/build")
CHECKPOINT_PATH = Path(__file__).resolve().parent / "block_parse_checkpoint.jsonl"


def main():
    print(f"Looking for checkpoint at: {CHECKPOINT_PATH}")
    if not CHECKPOINT_PATH.exists():
        print("NOT FOUND. This alone fully explains 'processes everything' -- there's")
        print("nothing to skip against. Likely cause: running from a different folder")
        print("than the one with your original checkpoint file from the first run.")
        return

    checkpoint_keys = set()
    with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                checkpoint_keys.add(json.loads(line)["path"])

    print(f"Checkpoint found with {len(checkpoint_keys)} entries.")
    print("Sample checkpoint keys:")
    for k in list(checkpoint_keys)[:3]:
        print(f"  {k!r}")

    print()
    print("Checking currently-discovered files against checkpoint keys...")
    checked = 0
    matched = 0
    for file_path in BLOCK_FILE_DIRECTORY.iterdir():
        if file_path.is_file() and file_path.suffix == ".txt":
            checked += 1
            key = str(file_path)
            is_match = key in checkpoint_keys
            if is_match:
                matched += 1
            if checked <= 5:
                print(f"  {key!r} -- {'MATCHED' if is_match else 'NOT in checkpoint'}")
        if checked >= 300:
            break

    print()
    print(f"Of the first {checked} files checked, {matched} matched a checkpoint entry.")
    if matched == 0:
        print("ZERO matches despite a non-empty checkpoint -- this is a path-format")
        print("mismatch (remapped drive, UNC vs letter, trailing slash, case, etc),")
        print("not a logic bug. Compare the checkpoint key samples above against the")
        print("currently-discovered path samples to see exactly how they differ.")
    elif matched < checked:
        print("PARTIAL match -- some files line up, some don't. Could be a mix of")
        print("genuinely-new files and a smaller formatting inconsistency. Worth a")
        print("closer look at which specific ones didn't match.")
    else:
        print("Full match on this sample -- checkpoint lookups appear to be working")
        print("correctly for these files. If you're still seeing everything")
        print("reprocessed, something else is going on (worth double-checking you're")
        print("not passing --force).")


if __name__ == "__main__":
    main()
