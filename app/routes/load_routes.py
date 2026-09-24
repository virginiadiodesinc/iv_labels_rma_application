from flask import Blueprint, request, render_template
from app.services.date_converter import string_to_python_date
from app.services import db_service
from app.services import postprocess as pp
from app.services import field_registry as fr
from app.db import JB2_queries as jb2

load_bp = Blueprint("load", __name__)

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