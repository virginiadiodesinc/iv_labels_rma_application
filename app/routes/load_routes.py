from flask import Blueprint, request, render_template
from app.services import db_service
from app.services import postprocess as pp
from app.services import field_registry as fr
from app.db import JB2_queries as jb2
from app.db import queries
from app.db.database import db_session
from pathlib import Path
from app.db.models import Build_Info, Build_Parts, Notes, IV_Info, Polarity, Note_Type, Yellow_Flags
from app.services import parts_service

load_bp = Blueprint("load", __name__)

@load_bp.post("/select_iv_from_db/")
def select_iv_from_db():
    build_info = request.form
    canonical = fr.canonical_from_form(request.form)
    search_by = request.form.get("iv-search-by")
    max_responses = request.form.get("iv-search-max-responses")


    build_id = fr.build_block_id_from_iv(canonical)
    iv_parts = parts_service.iv_parts_from_form(request.form)
    canonical.update(iv_parts)
    build_name = canonical.get("iv_build_name", "")
    diode_name = canonical.get("iv_diode_name", "")
    print(canonical)
    print(request.form)

    required_forms = {
        "Block ID": [build_info.get("iv-block-engraving", ""), build_info.get("iv-block-sn", "")],
        "Build Name": [build_name],
        "Diode": [diode_name]
    }

    # missing_forms = not (build_info.get("iv-block-engraving", "") and build_info.get("iv-block-sn", ""))
    missing_forms = any(not form.strip() for form in required_forms[search_by])
    iv_list = []
    if not missing_forms:
        if search_by == "Block ID":
            iv_list = queries.get_table_entries(db_session, IV_Info, build_id=build_id, limit=int(max_responses))
        elif search_by == "Build Name":
            iv_list = queries.get_table_entries(db_session, IV_Info, build_id=build_id, limit=int(max_responses))
        elif search_by == "Diode":
            iv_list = queries.get_table_entries(db_session, IV_Info, diode=diode_name, limit=int(max_responses))
        
    for iv in iv_list:
        iv.iv_path_stem = Path(iv.iv_file_path).stem

    return render_template("partials/iv-page/select-iv-from-db.html", iv_list=iv_list, missing_forms=missing_forms)

@load_bp.post("/populate_block_info_from_db")
def populate_block_info_from_db():
    canonical = fr.canonical_from_form(request.form)
    missing_forms = not (canonical.get("block_engraving", "") and canonical.get("block_serial_number", ""))
    block, parts, notes = db_service.get_block_and_build_info(canonical)
    block_found = bool(block)
    if block_found:
        return render_template("partials/block-forms/block-and-build-population.html", block=block, parts=parts, notes=notes)
    else:
        return render_template("partials/generic/no-block-found.html", missing_forms=missing_forms)

@load_bp.post("/search_block_revisions/")
def check_block_revisions():
    canonical = fr.canonical_from_form(request.form)
    missing_forms = not (canonical.get("block_engraving", "") and canonical.get("block_serial_number", ""))
    partial_block_id = fr.build_partial_block_id(canonical)

    revision_letter_list = db_service.get_all_block_revisions(canonical)

    return render_template("partials/generic/revision-list-dialog.html", revision_letter_list=revision_letter_list, missing_forms=missing_forms)