"""
file_service.py

Owns all actual disk I/O for the block/build file. Nothing else -- not
routes, not write_MicroA_files.py's line-building -- should call open() on
these files directly.
"""

import os
from app.services import field_registry as fr


def get_block_file_path(canonical: dict, block_file_directory: str) -> str:
    return os.path.join(block_file_directory, fr.block_file_name(canonical))


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

def save_full_block_file(canonical: dict, block_file_directory: str) -> str:
    path = get_block_file_path(canonical, block_file_directory)

    new_lines = [fr.render_new_line(template, canonical) for template in fr.BLOCK_FILE_TEMPLATE]

    with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(new_lines))
    
    return path


