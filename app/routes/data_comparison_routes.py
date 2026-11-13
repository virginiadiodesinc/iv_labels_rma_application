import uuid
from flask import Blueprint, request, render_template
from app.services import db_service
from app.services import save_orchestrator
from app.services import parts_service
from app.db import JB2_queries as jb2
from functools import wraps 
from flask import abort
from markupsafe import escape


data_bp = Blueprint("data", __name__)

PAGE_SIZE = 25


# ---------- helpers ----------

def input_kind(key, op):
    """Decides the SHAPE of the input area from (filter key, operation).
    Used by both the template-swapping route and the form parser so they
    can never disagree."""
    if op == "in":
        return "list"      # any number of strings
    if key == "has_part_and_lot":
        return "pair"      # exactly two strings: part, lot
    if key == "yellow_flag_status" or key == "from_file":
        return "bool"
    if key == "last_save_datetime":
        return "datetime"
    if key == "full_build_date":
        return "date"
    return "single"        # exactly one string


def _parse_one_filter(form, uid):
    """One filter row -> (key, op, value), or None if it's empty.
    Same logic as the old parse_filters loop body."""
    key = form.get(f"filter-key-{uid}")
    op = form.get(f"filter-op-{uid}")
    values = [v.strip() for v in form.getlist(f"filter-value-{uid}")]

    kind = input_kind(key, op)
    if kind == "list":
        values = [v for v in values if v]
        return (key, op, values) if values else None
    if kind == "pair":
        return (key, op, tuple(values)) if values and all(values) else None
    return (key, op, values[0]) if values and values[0] else None


def parse_filters(form):
    """[[(key, op, value), ...], ...]: one inner list per OR group, groups in
    DOM order. Each group has a hidden 'filter_group' uid; each filter row
    carries its group's uid in 'filter-group-<filter_uid>'. Empty filters and
    groups that end up empty are dropped."""
    groups = {g: [] for g in form.getlist("filter_group")}     # dict keeps DOM order
    for uid in form.getlist("filter_uid"):
        parsed = _parse_one_filter(form, uid)
        if parsed is not None:
            groups.setdefault(form.get(f"filter-group-{uid}", ""), []).append(parsed)
    return [g for g in groups.values() if g]


def parse_sorts(form):
    """Each sort row contributes exactly one key and one direction (selects
    always submit), so a plain zip keeps them paired. DOM order = priority."""
    return list(zip(form.getlist("sort-key"), form.getlist("sort-dir")))


# ---------- pages / fragments ----------

@data_bp.get("/add_new_filter/")
def add_new_filter():
    return render_template(
        "partials/data-comparison/filter.html",
        filters=db_service.get_filter_menu(),
        group_uid=request.args["group_uid"],
    )


@data_bp.get("/add_filter_group/")
def add_filter_group():
    return render_template(
        "partials/data-comparison/filter-group.html",
        filters=db_service.get_filter_menu(),
    )


@data_bp.get("/add_new_sort/")
def add_new_sort():
    return render_template(
        "partials/data-comparison/sort.html",
        sorts=db_service.get_sort_menu(),
    )


@data_bp.get("/update_filter_inputs/")
def update_filter_inputs():
    uid = request.args["filter_uid"]
    key = request.args.get(f"filter-key-{uid}")
    op = request.args.get(f"filter-op-{uid}")
    return render_template(
        "partials/data-comparison/filter-input-container.html",
        filter_uid=uid,
        input_kind=input_kind(key, op),
    )


@data_bp.get("/add_filter_string_to_list/")
def add_filter_string_to_list():
    return render_template(
        "partials/data-comparison/string-input-for-list.html",
        filter_uid=request.args["filter_uid"],
    )


# ---------- search ----------

@data_bp.get("/data_comparison/search/")
def search_builds_route():
    try:
        filters = parse_filters(request.args)
        sorts = parse_sorts(request.args)
        page = max(request.args.get("page", 1, type=int), 1)
        total, builds = db_service.search_builds(filters, sorts, page=page, page_size=PAGE_SIZE)
        # print(total)
        # for build in builds:
        #     build_dict = db_service.build_to_dict(build)
        #     print(build_dict)
    except ValueError as e:
        # 200 on purpose: htmx does not swap 4xx responses by default
        return f'<p class="error">{e}</p>'
    return render_template(
        "partials/data-comparison/builds-table.html",
        total=total, builds=builds, page=page, page_size=PAGE_SIZE,
    )


# ---------- hard-coded example (kept for reference) ----------

@data_bp.get("/builds/test")
def test_builds():
    filters = [[
        ("engraving", "contains", "WR"),
        ("serial", "eq", "1-001"),
        ("has_part_and_lot", "eq", ("A", "100")),
    ]]
    sorts = [
        ("full_build_date", "ascending"),
        ("serial", "ascending"),
    ]
    total, builds = db_service.search_builds(filters, sorts, page=1, page_size=PAGE_SIZE)
    return render_template("partials/data-comparison/builds-table.html", total=total, builds=builds)


def edit_gate(view):
    """Lets everyone through today. When the admin login exists, the check
    goes here and every edit/save route is protected by this one decorator."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        # TODO: if not current_user_is_admin(): abort(403)
        return view(*args, **kwargs)
    return wrapper


SECTION_TEMPLATES = {
    "yellow_flags": "partials/data-comparison/yellow-flags-section.html",
    "parts": "partials/data-comparison/parts-section.html",
    "notes": "partials/data-comparison/notes-section.html",
}


def _render_section(block_id, section_name, edit_section):
    build = db_service.get_build(block_id)
    if build is None:
        abort(404)
    if section_name in SECTION_TEMPLATES:
        template = SECTION_TEMPLATES[section_name]
    elif section_name in db_service.EDIT_SECTIONS:
        template = "partials/data-comparison/section.html"
    else:
        abort(404)
    return render_template(template, build=build, section_name=section_name, edit_section=edit_section)


def _render_row(build, **context):
    return render_template(
        "partials/data-comparison/build-data.html",
        build=build, build_open=True, **context,
    )


@data_bp.get("/data_comparison/edit_section/")
@edit_gate
def edit_section():
    name = request.args["section"]
    return _render_section(request.args["block_id"], name, edit_section=name)


@data_bp.get("/data_comparison/view_section/")        # the Cancel button
def view_section():
    return _render_section(request.args["block_id"], request.args["section"], edit_section=None)


@data_bp.post("/data_comparison/save_section/")
@edit_gate
def save_section():
    block_id = request.form["block_id"]
    section_name = request.form["section"]

    def show_error(message):
        # re-show the form with the message and what the user typed
        return _render_row(db_service.get_build(block_id),
                           edit_section=section_name, edit_error=message, form=request.form)

    # Four kinds of section, same skeleton: validate (pure) -> one orchestrator call.
    if section_name == "yellow_flags":
        try:
            flags_to_clear, changes, initials, reason = db_service.validate_yellow_flags_edit(
                block_id, request.form)
        except ValueError as e:
            return show_error(str(e))
        save = lambda: save_orchestrator.save_edited_yellow_flags(
            block_id, flags_to_clear, audit=(changes, initials, reason))
    elif section_name in db_service.LIST_SECTIONS:      # parts / notes
        try:
            new_rows, changes, initials, reason = db_service.validate_parts_or_notes_edit(
                block_id, section_name, request.form)
        except ValueError as e:
            return show_error(str(e))
        save = lambda: save_orchestrator.save_edited_parts_or_notes(
            block_id, section_name, new_rows, audit=(changes, initials, reason))
    else:
        try:
            new_values, changes, initials, reason = db_service.validate_section_edit(
                block_id, section_name, request.form)
        except ValueError as e:
            return show_error(str(e))
        audit = (changes, initials, reason)
        if section_name in db_service.FILE_SECTIONS:
            save = lambda: save_orchestrator.save_edited_section(
                block_id, section_name, new_values, audit=audit)
        else:   # "meta": DB only
            save = lambda: save_orchestrator.save_edited_meta(
                block_id, section_name, new_values, audit=audit)

    if changes:
        result = save()
        if not result.success:
            if isinstance(result.error, ValueError):
                return show_error(str(result.error))
            return show_error(f"Save failed ({result.failure_cause}). The database was not changed.")
        if result.warning:
            print(result.warning)

    return _render_row(db_service.get_build(block_id), open_section=section_name)



# ---------- template globals ----------

@data_bp.app_template_global()
def part_types():
    return parts_service.PART_TYPES


@data_bp.app_template_global()
def subassembly_tags():
    return parts_service.SUBASSEMBLY_TAGS


@data_bp.app_template_global()
def note_types():
    return parts_service.NOTE_TYPES


@data_bp.app_template_global()
def edit_part_rows(build, form=None):
    """Rows for the parts edit table: what the user submitted when re-showing
    after an error, otherwise the DB rows in saved order."""
    if form:
        return parts_service.raw_part_rows(form)
    parts, _ = db_service.get_parts_and_notes_as_dicts(build.block_id)
    return [parts_service.part_row_for_display(p) for p in parts]


@data_bp.app_template_global()
def edit_note_rows(build, form=None):
    if form:
        return parts_service.raw_note_rows(form)
    _, notes = db_service.get_parts_and_notes_as_dicts(build.block_id)
    return [parts_service.note_row_for_display(n) for n in notes]


@data_bp.app_template_global()
def new_uid():
    """Available in every template as new_uid()."""
    return uuid.uuid4().hex[:8]


@data_bp.app_template_global()
def edit_sections():
    """Available in templates as edit_sections() -- the single source for
    which fields each section has."""
    return db_service.EDIT_SECTIONS


@data_bp.app_template_global()
def yellow_flag_columns():
    return db_service.YELLOW_FLAG_COLUMNS


# ---------- row fragments ----------

@data_bp.get("/data_comparison/new_part_row/")
@edit_gate
def new_part_row():
    return render_template("partials/data-comparison/edit-part-row.html",
                           row=parts_service.blank_part_row())


@data_bp.get("/data_comparison/new_note_row/")
@edit_gate
def new_note_row():
    return render_template("partials/data-comparison/edit-note-row.html",
                           row={"type": parts_service.NOTE_TYPES[0], "note": ""})


# ---------- lot suggestions ----------

def _jb2_lots_for(part_name: str) -> list:
    """Same lookup /search_part_lots/ uses for lot-input.html's lot_list."""
    return list(jb2.get_Lots(part_name) or [])


@data_bp.get("/data_comparison/lot_options/")
@edit_gate
def lot_options():
    """<option>s for a lot <datalist>. A datalist suggests values but accepts
    anything typed, which replaces the main page's 'Other' + custom-lot input."""
    part_name = request.args.get("part_name", "").strip()
    lots = ["NA", "Unknown"] + (list(reversed(_jb2_lots_for(part_name))) if part_name else [])
    return "".join(f'<option value="{escape(lot)}"></option>' for lot in lots)
