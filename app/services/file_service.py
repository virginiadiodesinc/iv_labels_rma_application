"""
file_service.py

Owns all actual disk I/O for the block/build/IV/heat files. Nothing else --
not routes, not write_MicroA_files.py's line-building -- should call open()
on these files directly.
"""

import os
import statistics
from app.services import field_registry as fr
from app.services import string_utilities
from app import config
import webview
from pathlib import Path

current_iv_file_directory = config.iv_file_directory

def get_block_file_path(canonical: dict, block_file_directory: str) -> str:
    return os.path.join(block_file_directory, fr.block_file_name(canonical))


def get_build_file_path(canonical: dict, build_file_directory: str) -> str:
    return os.path.join(build_file_directory, fr.build_file_name(canonical))


def save_block_file_section(canonical: dict, section: fr.Section, block_file_directory: str) -> str:
    """Writes (new file) or updates (existing file, piecemeal) the block file
    for just the given section's fields. Returns the path written.

    Every line still gets rendered even for a brand-new file created by an
    inspection-only save -- rows this save doesn't own (PB1, PB2) just come
    out as placeholders, which is correct: the file has to be a complete,
    fixed-length file the moment it exists, even if most of it is still
    unfilled.
    """
    path = get_block_file_path(canonical, block_file_directory)
    print(canonical)

    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            existing_lines = f.read().splitlines()
        new_lines = []
        for template in fr.BLOCK_FILE_TEMPLATE:
            existing_line = (
                existing_lines[template.line_index]
                if template.line_index < len(existing_lines)
                else ""
            )
            new_lines.append(fr.update_existing_line(template, existing_line, canonical, section))
    else:
        new_lines = [fr.render_new_line(template, canonical) for template in fr.BLOCK_FILE_TEMPLATE]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines))

    print(path)
    return path


def save_block_file(canonical: dict, block_file_directory: str) -> str:
    path = get_block_file_path(canonical, block_file_directory)

    new_lines = [fr.render_new_line(template, canonical) for template in fr.BLOCK_FILE_TEMPLATE]

    with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(new_lines))
    
    return path



def save_build_file(canonical: dict, build_file_directory: str) -> str:
    canonical = fr.enrich_with_build_suffix(canonical, string_utilities.get_build_name_with_suffix)
    path = get_build_file_path(canonical, build_file_directory)

    new_lines = [fr.render_new_line(template, canonical) for template in fr.BUILD_FILE_TEMPLATE]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines))
        
    return path


def get_iv_file_path(canonical: dict, iv_file_directory: str) -> str:
    """Split out of save_iv_file so path can be computed BEFORE the DB
    decides insert vs. update (stage_upsert_iv_info needs the path first).
    NOTE: expects canonical to already be enriched
    (fr.enrich_with_build_suffix) -- caller's job now, not this function's."""
    file_name = fr.render_new_line(fr.IV_FILE_TEMPLATE[0], canonical).lower() + ".iv"
    return os.path.join(iv_file_directory, file_name)


def save_iv_file(canonical: dict, vup_list: list, vdown_list: list, isource_list: list, iv_file_directory: str) -> str:
    """canonical must already be enriched -- no longer calls
    fr.enrich_with_build_suffix itself, to avoid doing the CSV lookup twice
    per save now that get_iv_file_path also needs it."""
    lines = [fr.render_new_line(template, canonical) for template in fr.IV_FILE_TEMPLATE]

    for vup, vdown, isource in zip(vup_list, vdown_list, isource_list):
        lines.append(f"{float(vup):.6f}\t{float(vdown):.6f}\t{float(isource):.6f}")

    lines.append("")  # required trailing blank line -- do not remove

    path = get_iv_file_path(canonical, iv_file_directory)  # same-file call, unqualified
    stem = Path(path).stem

    selected_path = webview.windows[0].create_file_dialog(
            webview.FileDialog.SAVE,
            save_filename=stem,
            directory=iv_file_directory
            )
    selected_path = Path(selected_path[0])

    with selected_path.open(mode="w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return selected_path


def calculate_heat_deltas(temperature_list: list) -> tuple:
    """10-point delta: cold-start temp minus temp at point 10 (still
    warming up). 100-point delta: temp at point 10 minus temp at point 100
    (end of the heating ramp). End delta: final cooling temp minus a fixed
    25C baseline. Matches the old write_heat_test_file's math exactly."""
    ten_pt_delta = float(temperature_list[0]) - float(temperature_list[9])
    hundred_pt_delta = float(temperature_list[9]) - float(temperature_list[99])
    end_delta = float(temperature_list[-1]) - 25
    return ten_pt_delta, hundred_pt_delta, end_delta


def _render_heat_first_line(canonical: dict, iv_file_name: str, ten_pt_delta: float, hundred_pt_delta: float, end_delta: float) -> str:
    date_str = fr.stringify(canonical.get("iv_date"))
    time_str = canonical.get("iv_time_of_day") or ""
    boilerplate = "Heat(mA)=5.000E+1;Meas(mA)=1.000E-1;Htime(mS)=300;Mtime(mS)=100;PreTime(mS)=10"
    ideality = canonical.get("ideality")
    saturation_current = canonical.get("saturation_current")

    return (
        f"{date_str} {time_str}\t{iv_file_name};{boilerplate};"
        f"n={ideality:.3f};Is={fr.format_labview_scientific(saturation_current, 3)};"
        f"10ptdeltaT={ten_pt_delta:.3f};100ptdeltaT={hundred_pt_delta:.3f};EnddeltaT={end_delta:.3f}"
    )


def save_heat_test_file(canonical: dict, iv_file_name: str, temperature_list: list, heat_voltage_list: list, heat_file_directory: str) -> str:
    """Only called when a heat test was actually taken -- the orchestrator
    decides that by checking whether the relevant lists have real values.

    temperature_list must be pre-calculated (postprocess.calculate_heat_parameters)
    -- this function only renders and writes, it doesn't do the physics.

    heat_voltage_list is the FULL list (not pre-sliced) -- this slices it
    into the last-100 'hot' voltages (paired with temperature_list) and the
    first-10 'cold' voltages (averaged into the settled row), same as the
    old write_heat_test_file. Verified byte-for-byte against a real sample
    file, including the settled row's index being +2 (not the old code's
    +1 -- a confirmed bug fix) and the required trailing blank line."""
    ten_pt_delta, hundred_pt_delta, end_delta = calculate_heat_deltas(temperature_list)

    hot_voltage_list = heat_voltage_list[-100:]
    cold_voltage_list = heat_voltage_list[0:10]
    cold_mean_voltage = statistics.mean(float(v) for v in cold_voltage_list)

    lines = [_render_heat_first_line(canonical, iv_file_name, ten_pt_delta, hundred_pt_delta, end_delta)]
    lines.append("\t".join(["Time(mS)", "Temp(C)", "(V)", ""]))  # trailing tab -- matches sample exactly

    for i in range(len(hot_voltage_list)):
        index = fr.format_labview_scientific(1 + i)
        temp = fr.format_labview_scientific(float(temperature_list[i]))
        voltage = fr.format_labview_scientific(float(hot_voltage_list[i]))
        constant = fr.format_labview_scientific(1)
        lines.append(f"{index}\t{temp}\t{voltage}\t{constant}")

    settled_index = fr.format_labview_scientific(len(hot_voltage_list) + 2)
    settled_temp = fr.format_labview_scientific(25)
    settled_voltage = fr.format_labview_scientific(cold_mean_voltage)
    constant = fr.format_labview_scientific(1)
    lines.append(f"{settled_index}\t{settled_temp}\t{settled_voltage}\t{constant}")
    lines.append("")  # required trailing blank line -- same as the .iv file

    file_name = iv_file_name.replace(".iv", ".txt")
    path = os.path.join(heat_file_directory, file_name)

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return path


def delete_file(path: str) -> None:
    """You likely already have this from block/build delete work -- only
    including it in case IV is first."""
    if path and os.path.isfile(path):
        os.remove(path)
