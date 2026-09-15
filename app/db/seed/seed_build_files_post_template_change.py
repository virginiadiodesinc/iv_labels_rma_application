from app.db.models import *
from app.services import build_file_converter as build_converter
from app.services import string_utilities as su
from pathlib import Path
import datetime
import re
import time

def populate_info_from_build_file(build_file_path):
    """Populates the various input fields with information from a (likely LabView) build file

    This function uses a LabView build file to populate all the block (inspection, PB1, PB2) as well as build (part/note list) fields

    @return build-file-population-response Return value of type (template partial)
    """

    if build_file_path and build_file_path.endswith(".txt"):
        with open(build_file_path, "r") as build_file:
            build_dict = build_converter.convert_build_file(build_file)

        part_rows = []

        diode_1_full_text = build_dict.get("diode_1", "")
        diode_1_name, diode_1_lot, diode_1_extra = su.separate_part_and_lot(diode_1_full_text)
        diode_1_quantity = build_dict.get("diode_1_chip_count")

        circuit_1_full_text = build_dict.get("circuit_1", "")
        circuit_1_name, circuit_1_lot, circuit_1_extra = su.separate_part_and_lot(circuit_1_full_text)

        filter_1_full_text = build_dict.get("filter_1", "")
        filter_1_name, filter_1_lot, filter_1_extra = su.separate_part_and_lot(filter_1_full_text)

        diode_2_full_text = build_dict.get("diode_2", "")
        diode_2_name, diode_2_lot, diode_2_extra = su.separate_part_and_lot(diode_2_full_text)
        diode_2_quantity = build_dict.get("diode_2_chip_count")

        circuit_2_full_text = build_dict.get("circuit_2", "")
        circuit_2_name, circuit_2_lot, circuit_2_extra = su.separate_part_and_lot(circuit_2_full_text)

        filter_2_full_text = build_dict.get("filter_2", "")
        filter_2_name, filter_2_lot, filter_2_extra = su.separate_part_and_lot(filter_2_full_text)

        pcb_full_text = build_dict.get("pcb_info", "")
        pcb_name, pcb_lot, pcb_extra = su.separate_part_and_lot(pcb_full_text)

        mmic_name = build_dict.get("mmic_name", "")
        mmic_lot = build_dict.get("mmic_lot", "")


        part_rows = [
            {"part_name": diode_1_name, "quantity": diode_1_quantity, "part_type": "DIODE", "part_lot": diode_1_lot},
            {"part_name": circuit_1_name, "quantity": 1, "part_type": "CIRCUIT", "part_lot": circuit_1_lot},
            {"part_name": diode_2_name, "quantity": diode_2_quantity, "part_type": "DIODE", "part_lot": diode_2_lot},
            {"part_name": circuit_2_name, "quantity": 1, "part_type": "CIRCUIT", "part_lot": circuit_2_lot},
            {"part_name": pcb_name, "quantity": 1, "part_type": "PCB", "part_lot": pcb_lot},
            {"part_name": filter_1_name, "quantity": 1, "part_type": "FILTER", "part_lot": filter_1_lot},
            {"part_name": filter_2_name, "quantity": 1, "part_type": "FILTER", "part_lot": filter_2_lot},
            {"part_name": mmic_name, "quantity": 1, "part_type": "MMIC", "part_lot": mmic_lot}
        ]

        for part in part_rows[:]:
            part_name_without_whitespace = re.sub(r"\s+", "", part["part_name"]).lower()
            if (part_name_without_whitespace == "" or part_name_without_whitespace == "na" or part_name_without_whitespace == "n/a"):
                part_rows.remove(part)

        note_rows = []
        for note in build_dict.get("notes", []):
            note_rows.append({"note": note, "type": Note_Type.GENERIC})
        note_rows.append({"note": build_dict.get("vbr", ""), "type": Note_Type.GENERIC})
        note_rows.append({"note": build_dict.get("indium_info", ""), "type": Note_Type.GENERIC})

        for note in note_rows[:]:
            if not note:
                note_rows.remove(note)
                continue

            note_without_whitespace = re.sub(r"\s+", "", note["note"]).lower()
            if (note_without_whitespace == "" or note_without_whitespace == "na" or note_without_whitespace == "n/a"):
                note_rows.remove(note)

        return build_dict, part_rows, note_rows

def seed_build_files():
    build_file_directory = Path("K:/build")
    error_file = Path(__file__).resolve().parent.joinpath('New Build File Template Errors.txt')
    newest_template_date = datetime.date(2024, 5, 9)
    file_success_count = 0
    file_error_count = 0
    file_count = 0
    start_time = time.time()
    file_errors = []

    for file_path in build_file_directory.iterdir():
        if file_path.is_file() and file_path.suffix == ".txt":
            file_date = datetime.datetime.fromtimestamp(file_path.stat().st_mtime).date()
            if file_date > newest_template_date:
                print()
                print("FILE PATH: ", file_path)
                try:
                    build_dict, part_rows, note_rows = populate_info_from_build_file(str(file_path))
                    file_success_count = file_success_count + 1
                    print("SUCCESS")
                    print("PARTS: ", part_rows)
                    print("NOTES: ", note_rows)
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