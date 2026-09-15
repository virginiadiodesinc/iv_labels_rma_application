"""
Stage 1 of 2: PARSE

Walks K:/block, runs every .txt file through block_file_converter, and writes
one JSON object per line (JSONL) to raw_block_records.jsonl.

Design goals, given ~25,000 files:
  - RESUMABLE: a checkpoint file tracks which (path, mtime) pairs have already
    been processed, so re-running after a crash or a bug fix doesn't reparse
    everything. Delete the checkpoint file to force a full re-parse.
  - INCREMENTAL WRITES: each record is written and flushed immediately, not
    accumulated in memory and dumped at the end. A crash on file #24,999
    doesn't lose the other 24,998.
  - RAW, UNTRANSFORMED OUTPUT: this stage does NOT rename keys or reshape
    data. It stores exactly what block_converter.convert_block_file()
    returned, plus source metadata. Key-mapping/cleanup happens in stage 2
    (transform_block_records.py), so template-name changes never require
    re-parsing.
  - Every file is logged to a persistent log file, not just stdout.

Run:
    python parse_block_files.py
    python parse_block_files.py --force        # ignore checkpoint, reparse all
    python parse_block_files.py --limit 500     # smoke-test on first N files
"""

from app.services import block_file_converter as block_converter
from pathlib import Path
import argparse
import datetime
import json
import logging
import time

BLOCK_FILE_DIRECTORY = Path("K:/block")
OUTPUT_DIR = Path(__file__).resolve().parent
RAW_RECORDS_PATH = OUTPUT_DIR / "raw_block_records.jsonl"
ERROR_RECORDS_PATH = OUTPUT_DIR / "raw_block_errors.jsonl"
CHECKPOINT_PATH = OUTPUT_DIR / "block_parse_checkpoint.jsonl"
LOG_PATH = OUTPUT_DIR / "parse_block_files.log"

# Only files modified after this date are considered "post template change".
# Kept as a constant here (rather than buried in a loop) so it's easy to spot
# and change later.
NEWEST_TEMPLATE_DATE = datetime.date(2000, 1, 1)


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
    with open(file_path, "r") as block_file:
        block_dict = block_converter.convert_block_file(block_file)
    return block_dict


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Ignore checkpoint, reparse everything")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N matching files (for smoke testing)")
    args = parser.parse_args()

    setup_logging()
    logging.info("Starting block file parse run.")

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

        for file_path in sorted(BLOCK_FILE_DIRECTORY.iterdir()):
            if not (file_path.is_file() and file_path.suffix == ".txt"):
                continue

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
                block_dict = parse_one_file(file_path)
                record = {
                    "source_path": str(file_path),
                    "source_mtime": mtime,
                    "source_mtime_iso": datetime.datetime.fromtimestamp(mtime).isoformat(),
                    "parsed_at": datetime.datetime.now().isoformat(),
                    "raw_fields": block_dict,
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


if __name__ == "__main__":
    main()
