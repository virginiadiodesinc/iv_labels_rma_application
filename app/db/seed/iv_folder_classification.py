"""
Config for which folders under I:/ get walked during IV parsing.

DEFAULT POSTURE FLIPPED from the first draft: with ~700 top-level folders,
requiring an explicit INCLUDED_FOLDERS list meant enumerating nearly all of
them by hand. Now every folder is walked BY DEFAULT, EXCEPT:

  1. SUSPICIOUS_NAME_PATTERNS -- checked at EVERY depth. A folder whose
     name contains one of these substrings (case-insensitive) is pruned
     and reported, even nested inside an otherwise-normal folder. This is
     automatic -- no per-folder decision needed.

  2. EXCLUDED_FOLDER_NAMES -- loaded from excluded_folders.txt (same
     directory as this file), one folder NAME per line, matched at any
     depth. Plain text, no quotes/commas -- paste directly from a
     directory listing or the discovery report and delete the ones you
     want walked.

  3. ALLOWLIST_OVERRIDES -- folder names that WOULD match a suspicious
     pattern but are legitimate (e.g. a real folder literally named
     "Backup Diodes" isn't junk just because "backup" is in it). Checked
     before rule 1, so these always win.

There's no more "unclassified, not walked" bucket -- every top-level
folder discovered gets walked and logged in the report's "included" list
for a one-time skim, but nothing is blocked pending approval. Given the
scale here, review-after-the-fact is more realistic than approve-in-
advance.
"""

from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent
EXCLUDED_FOLDERS_FILE = CONFIG_DIR / "excluded_folders.txt"

SUSPICIOUS_NAME_PATTERNS = [
    "old",
    "archive",
    "backup",
    "scratch",
    "temp",
    "duplicate",
    "do not use",
    "copy of",
    "amp",
    "new folder",
    "recycle"
]

# Folder names that would otherwise trip SUSPICIOUS_NAME_PATTERNS but are
# legitimate -- add exceptions here as you find them during review.
ALLOWLIST_OVERRIDES = {
    # "Backup Diodes",
}


def _load_plain_text_list(path):
    """One entry per line. Blank lines and lines starting with # are
    ignored, so you can paste a raw listing and comment out lines instead
    of deleting them if you're not sure yet."""
    names = set()
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    names.add(line)
    return names


EXCLUDED_FOLDER_NAMES = _load_plain_text_list(EXCLUDED_FOLDERS_FILE)