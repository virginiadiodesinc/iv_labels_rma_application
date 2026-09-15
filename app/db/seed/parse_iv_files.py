"""
Stage 1 of 2: PARSE

Walks I:/, runs every .iv file through iv_file_converter, and writes
one JSON object per line (JSONL) to raw_iv_records.jsonl.

Design goals, given ~25,000 files:
  - RESUMABLE: a checkpoint file tracks which (path, mtime) pairs have already
    been processed, so re-running after a crash or a bug fix doesn't reparse
    everything. Delete the checkpoint file to force a full re-parse.
  - INCREMENTAL WRITES: each record is written and flushed immediately, not
    accumulated in memory and dumped at the end. A crash on file #24,999
    doesn't lose the other 24,998.
  - RAW, UNTRANSFORMED OUTPUT: this stage does NOT rename keys or reshape
    data. It stores exactly what iv_converter.convert_iv_file()
    returned, plus source metadata. Key-mapping/cleanup happens in stage 2
    (transform_iv_records.py), so template-name changes never require
    re-parsing.
  - Every file is logged to a persistent log file, not just stdout.

Run:
    python parse_iv_files.py
    python parse_iv_files.py --force        # ignore checkpoint, reparse all
    python parse_iv_files.py --limit 500     # smoke-test on first N files
"""

from app.services import iv_file_converter as iv_converter
from pathlib import Path
import argparse
import datetime
import json
import logging
import os
import time

from app.db.seed import iv_folder_classification as folder_config

IV_FILE_DIRECTORY = Path("I:/")
OUTPUT_DIR = Path("W:/Python3/IV and Labels/database/seed")
RAW_RECORDS_PATH = OUTPUT_DIR / "raw_iv_records.jsonl"
ERROR_RECORDS_PATH = OUTPUT_DIR / "raw_iv_errors.jsonl"
CHECKPOINT_PATH = OUTPUT_DIR / "iv_parse_checkpoint.jsonl"
LOG_PATH = OUTPUT_DIR / "parse_iv_files.log"
FOLDER_REPORT_PATH = OUTPUT_DIR / "iv_folder_discovery_report.json"

# >>> CONFIRM: docstring above says ".txt" but this filters ".iv" -- if
# >>> that's a copy-paste leftover from the block/build scripts and these
# >>> are actually .txt files, fix this constant (and the docstring).
# Matched case-insensitively, since a mismatched case silently dropped
# files in the block-file pipeline before.
FILE_SUFFIX = ".iv"

# Only files modified after this date are considered "post template change".
# Kept as a constant here (rather than buried in a loop) so it's easy to spot
# and change later.
NEWEST_TEMPLATE_DATE = datetime.date(2000, 1, 1)


def discover_iv_files():
    """Recursively walks IV_FILE_DIRECTORY, pruning branches BEFORE
    descending into them (os.walk's topdown mutation of dirnames) so
    excluded/suspicious folders are never even listed, not just filtered
    after the fact -- matters on a network share where listing a huge
    irrelevant folder is itself expensive.

    DEFAULT POSTURE: every folder is walked unless it matches
    EXCLUDED_FOLDER_NAMES or SUSPICIOUS_NAME_PATTERNS (with
    ALLOWLIST_OVERRIDES winning over the latter). There's no
    "unclassified, blocked" bucket -- see iv_folder_classification.py for
    why, given ~700 top-level folders.

    Yields matching file Paths. Populates the module-level
    discovery_report dict as a side effect, for the end-of-run report.
    """
    excluded_lower = {name.lower() for name in folder_config.EXCLUDED_FOLDER_NAMES}
    allowlist_lower = {name.lower() for name in folder_config.ALLOWLIST_OVERRIDES}
    suspicious_patterns = [p.lower() for p in folder_config.SUSPICIOUS_NAME_PATTERNS]

    discovery_report["included"] = []
    discovery_report["excluded"] = []
    discovery_report["suspicious"] = []

    for root, dirs, files in os.walk(str(IV_FILE_DIRECTORY), topdown=True):
        root_path = Path(root)
        rel_root = "" if root_path == IV_FILE_DIRECTORY else str(
            root_path.relative_to(IV_FILE_DIRECTORY)
        ).replace("\\", "/")
        is_top_level = rel_root == ""

        kept_dirs = []
        for d in dirs:
            rel_child = d if is_top_level else f"{rel_root}/{d}"
            lower_name = d.lower()

            if lower_name in excluded_lower:
                discovery_report["excluded"].append(rel_child)
                continue

            if lower_name not in allowlist_lower and any(
                pattern in lower_name for pattern in suspicious_patterns
            ):
                discovery_report["suspicious"].append(rel_child)
                continue

            discovery_report["included"].append(rel_child)
            kept_dirs.append(d)

        dirs[:] = kept_dirs  # prune in place -- os.walk will not descend into removed dirs

        if is_top_level:
            continue  # no IV files expected directly at I:/ root

        for filename in files:
            file_path = root_path / filename
            if file_path.suffix.lower() == FILE_SUFFIX.lower():
                yield file_path


discovery_report = {}


def write_discovery_report():
    with open(FOLDER_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(discovery_report, f, indent=2)

    excluded = discovery_report.get("excluded", [])
    suspicious = discovery_report.get("suspicious", [])
    included_count = len(discovery_report.get("included", []))
    print()
    print(f"Walked {included_count} folder(s).")
    if excluded:
        print(f"EXCLUDED ({len(excluded)}, per excluded_folders.txt):")
        for folder in sorted(set(excluded)):
            print(f"  {folder}")
    if suspicious:
        print(f"SUSPICIOUS-NAMED ({len(suspicious)}, pruned automatically -- review, add to ALLOWLIST_OVERRIDES if wrong):")
        for folder in sorted(set(suspicious)):
            print(f"  {folder}")
    print()
    print(f"Full discovery report (including the full 'included' list) written to: {FOLDER_REPORT_PATH}")


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def load_checkpoint():
    """Returns a dict of {file_path_str: mtime_float} already processed."""
    processed = {}
    if CHECKPOINT_PATH.exists():
        with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                processed[entry["path"]] = entry["mtime"]
    return processed


def append_checkpoint(checkpoint_file, file_path, mtime):
    checkpoint_file.write(json.dumps({"path": str(file_path), "mtime": mtime}) + "\n")
    checkpoint_file.flush()


def already_processed(checkpoint, file_path, mtime):
    prior_mtime = checkpoint.get(str(file_path))
    # Reprocess if we've never seen this path, or if the file has changed
    # since we last saw it (mtime differs).
    return prior_mtime is not None and prior_mtime == mtime


def parse_one_file(file_path):
    """Runs the converter and returns the raw dict. Raises on failure."""
    with open(file_path, "r") as iv_file:
        iv_dict = iv_converter.convert_iv_file(iv_file)
    return iv_dict


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Ignore checkpoint, reparse everything")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N matching files (for smoke testing)")
    args = parser.parse_args()

    setup_logging()
    logging.info("Starting iv file parse run.")

    checkpoint = {} if args.force else load_checkpoint()
    if args.force and CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()

    success_count = 0
    error_count = 0
    skipped_count = 0
    processed_count = 0
    start_time = time.time()

    with open(RAW_RECORDS_PATH, "a", encoding="utf-8") as raw_out, \
         open(ERROR_RECORDS_PATH, "a", encoding="utf-8") as err_out, \
         open(CHECKPOINT_PATH, "a", encoding="utf-8") as checkpoint_out:

        for file_path in sorted(discover_iv_files()):
            stat = file_path.stat()
            mtime = stat.st_mtime
            file_date = datetime.datetime.fromtimestamp(mtime).date()

            if file_date <= NEWEST_TEMPLATE_DATE:
                continue

            if already_processed(checkpoint, file_path, mtime):
                skipped_count += 1
                continue

            if args.limit is not None and processed_count >= args.limit:
                break

            processed_count += 1
            logging.info("Parsing: %s", file_path)

            try:
                iv_dict = parse_one_file(file_path)
                record = {
                    "source_path": str(file_path),
                    "source_mtime": mtime,
                    "source_mtime_iso": datetime.datetime.fromtimestamp(mtime).isoformat(),
                    "parsed_at": datetime.datetime.now().isoformat(),
                    "raw_fields": iv_dict,
                }
                raw_out.write(json.dumps(record, default=str) + "\n")
                raw_out.flush()
                success_count += 1
                logging.info("SUCCESS: %s", file_path)
            except Exception as e:
                error_record = {
                    "source_path": str(file_path),
                    "source_mtime": mtime,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "attempted_at": datetime.datetime.now().isoformat(),
                }
                err_out.write(json.dumps(error_record, default=str) + "\n")
                err_out.flush()
                error_count += 1
                logging.warning("ERROR parsing %s: %s", file_path, e)
            finally:
                append_checkpoint(checkpoint_out, file_path, mtime)

    total_time = time.time() - start_time
    logging.info(
        "Run complete. Success: %d, Errors: %d, Skipped (already done): %d, Total time: %.1fs",
        success_count, error_count, skipped_count, total_time,
    )
    print()
    print(f"TOTAL TIME TAKEN: {total_time:.1f}s")
    print(f"NEWLY PARSED SUCCESSFULLY: {success_count}")
    print(f"NEWLY FAILED: {error_count}")
    print(f"SKIPPED (already in checkpoint): {skipped_count}")
    print(f"Raw records written to: {RAW_RECORDS_PATH}")
    print(f"Errors written to: {ERROR_RECORDS_PATH}")
    write_discovery_report()


if __name__ == "__main__":
    main()