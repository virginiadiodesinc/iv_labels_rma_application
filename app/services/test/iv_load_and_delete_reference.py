"""
REFERENCE ONLY -- not a real module, not meant to be imported.

Everything needed for IV load-by-id and delete, organized by which real
file each piece belongs in. Calls to functions in OTHER files are written
qualified (fr.something, db_service.something) so you can tell at a glance
what's local to the section vs. imported. Calls within the SAME section are
unqualified, since they're calling a sibling function in that same file.
"""


# =============================================================================
# db_service.py -- ADD these four functions
# =============================================================================
# (Needs: from app.db.models import Build_Info, Build_Parts, IV_Info,
#  IV_Points, Polarity -- add Polarity if it's not already imported)

def get_iv_info_by_id(iv_id):
    """Direct PK lookup -- IV_Info.iv_id IS the primary key, so this is the
    one thing that should ever be used to name a specific IV row. Replaces
    the old query-by-build_id-then-scan-for-matching-path-stem pattern."""
    return db_session.get(IV_Info, iv_id)


def stage_upsert_iv_info(canonical: dict, iv_file_path: str) -> object:
    """Keyed by the computed file path, not a business identity like
    Build_Info's upsert or a bare delete-and-reinsert like Build_Parts --
    "same path" IS the identity rule for an IV file in this app. If a row
    already exists at this path, its old IV_Points get cleared here (fresh
    ones get staged right after by the caller, using the returned entry's
    iv_id) rather than accumulating alongside stale ones from the previous
    save at this same path.

    NOTE: expects canonical to already be enriched
    (fr.enrich_with_build_suffix) -- the orchestrator does that once, up
    top, not this function."""
    existing = queries.get_table_entries(db_session, IV_Info, iv_file_path=iv_file_path)

    kwargs = fr.canonical_to_db_kwargs(canonical, "IV_Info")
    kwargs["build_id"] = fr.build_block_id_from_iv(canonical)
    kwargs["polarity"] = Polarity.POSITIVE if canonical.get("polarity") == "+" else Polarity.NEGATIVE
    kwargs["iv_file_path"] = iv_file_path

    if existing:
        entry = existing[0]
        stage_delete_iv_points(entry.iv_id)  # same-file call, unqualified
        entry = queries.update_table_entry(db_session, IV_Info, entry.iv_id, **kwargs)
    else:
        entry = queries.add_table_entry(db_session, IV_Info, **kwargs)
    return entry


def stage_delete_iv_points(iv_id) -> list:
    points = queries.get_table_entries(db_session, IV_Points, iv_id=iv_id)
    for point in points:
        queries.delete_table_entry(db_session, IV_Points, point.point_id)
    return points


def stage_delete_iv_info(iv_id):
    """Returns the entry that was deleted -- fetched and kept as a
    reference BEFORE the delete happens, since delete_table_entry itself
    only returns True/False, not the row. Reading entry.iv_file_path /
    entry.heat_file_path after this still works within the same
    transaction (the object isn't invalidated until commit)."""
    entry = db_session.get(IV_Info, iv_id)
    if entry:
        queries.delete_table_entry(db_session, IV_Info, iv_id)
    return entry


# =============================================================================
# file_service.py -- REPLACE get_iv_file_path (new) and save_iv_file,
# ADD delete_file
# =============================================================================

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
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return path


def delete_file(path: str) -> None:
    """You likely already have this from block/build delete work -- only
    including it in case IV is first."""
    if path and os.path.isfile(path):
        os.remove(path)


# =============================================================================
# save_orchestrator.py -- REPLACE save_iv_info, ADD delete_iv_info
# =============================================================================
# (Needs: import os, from app.services import postprocess, traceback if not
#  already imported)

def save_iv_info(canonical: dict, vup_list: list, vdown_list: list, isource_list: list,
                  heat_current_list: list = None, heat_voltage_list: list = None) -> SaveResult:
    canonical = fr.stamp_iv_datetime(canonical)
    # Enriched ONCE here -- get_iv_file_path, stage_upsert_iv_info, and
    # save_iv_file all assume this already happened, so they don't each
    # redo the CSV lookup.
    canonical = fr.enrich_with_build_suffix(
        canonical, string_utilities.get_build_name_with_suffix,
        build_name_key="iv_build_name", block_engraving_key="iv_block_engraving",
        output_key="iv_full_build_name_with_suffix",
    )

    block_identity = fr.iv_identity_as_block_identity(canonical)
    try:
        db_service.stage_upsert_build_info(block_identity)
    except Exception as e:
        db_service.roll_back_db_changes()
        return SaveResult(success=False, failure_cause="db", error=e)

    iv_file_path = file_service.get_iv_file_path(canonical, config.iv_file_directory)

    try:
        iv_entry = db_service.stage_upsert_iv_info(canonical, iv_file_path)
    except Exception as e:
        db_service.roll_back_db_changes()
        return SaveResult(success=False, failure_cause="db", error=e)

    canonical = dict(canonical)
    canonical["iv_id"] = iv_entry.iv_id

    try:
        db_service.stage_add_iv_points(canonical)
    except Exception as e:
        db_service.roll_back_db_changes()
        return SaveResult(success=False, failure_cause="db", error=e)

    try:
        file_service.save_iv_file(canonical, vup_list, vdown_list, isource_list, config.iv_file_directory)
    except Exception as e:
        db_service.roll_back_db_changes()
        return SaveResult(success=False, failure_cause="file", error=e)

    heat_test_taken = bool(heat_current_list) and bool(heat_voltage_list) and any(heat_current_list) and any(heat_voltage_list)
    if heat_test_taken:
        try:
            temperature_list = postprocess.calculate_heat_parameters(
                heat_current_list, heat_voltage_list, canonical.get("ideality")
            )
            heat_file_name = os.path.basename(iv_file_path)
            heat_path = file_service.save_heat_test_file(
                canonical, heat_file_name, temperature_list, heat_voltage_list, config.heat_data_directory
            )
            iv_entry.heat_file_path = heat_path
        except Exception as e:
            db_service.roll_back_db_changes()
            return SaveResult(success=False, failure_cause="file", error=e)

    db_service.commit_db_changes()
    return SaveResult(success=True)


def delete_iv_info(iv_id) -> DeleteResult:
    try:
        entry = db_service.stage_delete_iv_info(iv_id)
        if entry is None:
            return DeleteResult(success=False, failure_cause="db iv info", error=ValueError(f"No IV_Info row for iv_id={iv_id}"))
    except Exception as e:
        traceback.print_exc()
        db_service.roll_back_db_changes()
        return DeleteResult(success=False, failure_cause="db iv info", error=e)

    try:
        db_service.stage_delete_iv_points(iv_id)
    except Exception as e:
        traceback.print_exc()
        db_service.roll_back_db_changes()
        return DeleteResult(success=False, failure_cause="db iv points", error=e)

    try:
        if entry.iv_file_path:
            file_service.delete_file(entry.iv_file_path)
    except Exception as e:
        traceback.print_exc()
        db_service.roll_back_db_changes()
        return DeleteResult(success=False, failure_cause="iv file", error=e)

    try:
        if entry.heat_file_path:
            file_service.delete_file(entry.heat_file_path)
    except Exception as e:
        traceback.print_exc()
        db_service.roll_back_db_changes()
        return DeleteResult(success=False, failure_cause="heat file", error=e)

    db_service.commit_db_changes()
    return DeleteResult(success=True)


# =============================================================================
# db_routes.py (load side -- becomes load_routes.py eventually) --
# REPLACE select_iv_from_db and populate_iv_from_db
# =============================================================================

@db_bp.post("/select_iv_from_db/")
def select_iv_from_db():
    build_info = request.form
    build_id_query = (
        build_info.get("iv-block-engraving") + " " +
        build_info.get("iv-block-sn") + " " +
        build_info.get("iv-block-revision", "A")
    )

    ivs = get_table_entries(db_session, IV_Info, build_id=build_id_query)

    # Passing the actual rows now, not just the path stems -- the template
    # needs both: iv.iv_id for the option's VALUE, the stem for what's
    # DISPLAYED. This is the one change that makes populate_iv_from_db (and
    # delete) simple.
    return render_template("partials/iv-page/select-iv-from-db.html", ivs=ivs)
    # In select-iv-from-db.html:
    #   {% for iv in ivs %}
    #     <option value="{{ iv.iv_id }}">{{ Path(iv.iv_file_path).stem }}</option>
    #   {% endfor %}
    # (or compute the stem in the route and pass it alongside, if the
    # template shouldn't import pathlib itself)


@db_bp.post("/populate_iv_from_db/")
def populate_iv_from_db():
    build_info = request.form
    selected_iv_id = build_info.get("selected-iv-id")  # was "selected-iv-path"

    iv = db_service.get_iv_info_by_id(selected_iv_id)
    if iv is None:
        return render_template("partials/generic/error-message.html", errors=["That IV no longer exists."]), 200

    # everything below this point is UNCHANGED from the original --
    # iv_info_dict, iv_curve_points, process_dict, etc. all still work the
    # same way, they just no longer depend on a fragile path-stem match to
    # get here. The build_id_query / for-loop-scanning-for-matching-stem
    # block that used to sit here is gone entirely.
    iv_info_dict = {
        column.name: getattr(iv, column.name)
        for column in iv.__table__.columns
    }
    iv_curve_points = get_table_entries(db_session, IV_Points, iv_id=iv_info_dict['iv_id'])
    # ... rest of the function is identical to what you already have.


# =============================================================================
# delete_routes.py -- illustrative shape for the IV delete route.
# You already have your own dialog/validation scaffolding for block/build
# delete -- this just shows how it plugs into save_orchestrator.delete_iv_info
# once you're past confirmation. No yellow flags needed, as you noted.
# =============================================================================

@delete_bp.post("/delete_iv_info/")
def delete_iv_info_route():
    iv_id = request.form.get("iv-id")  # or wherever your confirm dialog carries it
    result = save_orchestrator.delete_iv_info(iv_id)

    if not result.success:
        return render_template("partials/generic/save-error.html", failure_cause=result.failure_cause), 200

    return render_template("partials/generic/save-success.html"), 200
