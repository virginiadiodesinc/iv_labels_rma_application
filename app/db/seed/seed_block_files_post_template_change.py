from app.db.models import *
from app.services import block_file_converter as block_converter
from app.services import string_utilities as su
from pathlib import Path
import datetime
import re
import time

def populate_info_from_block_file(block_file_path):
    if block_file_path and block_file_path.endswith(".txt"):
        with open(block_file_path, "r") as block_file:
            block_dict = block_converter.convert_block_file(block_file)
        return block_dict

        
def seed_build_files():
    block_file_directory = Path("K:/block")
    error_file = Path(__file__).resolve().parent.joinpath('Block File Template Errors.txt')
    newest_template_date = datetime.date(2020, 5, 9)
    file_success_count = 0
    file_error_count = 0
    file_count = 0
    start_time = time.time()
    file_errors = []

    for file_path in block_file_directory.iterdir():
        if file_path.is_file() and file_path.suffix == ".txt":
            file_date = datetime.datetime.fromtimestamp(file_path.stat().st_mtime).date()
            if file_date > newest_template_date:
                print()
                print("FILE PATH: ", file_path)
                try:
                    block_dict = populate_info_from_block_file(str(file_path))
                    file_success_count = file_success_count + 1
                    print("SUCCESS")
                    print("BLOCK INFO: ", block_dict)
                except Exception as e:
                    print(e)
                    file_errors.append(str(file_path))
                    file_error_count = file_error_count + 1
                    continue

    with open(error_file, "w") as file:
        file.write("\n".join(file_errors)+ "\n")

    end_time = time.time()
    total_time = end_time - start_time

    print()
    print("TOTAL TIME TAKEN: ", total_time)
    print("TOTAL FILES SUCCESSSFUL: ", file_success_count)
    print("TOTAL FILES WITH ERRORS: ", file_error_count)

def main():
    seed_build_files()

if __name__ == "__main__":
    main()