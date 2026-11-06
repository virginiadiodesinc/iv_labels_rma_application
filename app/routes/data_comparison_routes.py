import uuid
from flask import Blueprint, request, render_template
from app.services import db_service
from functools import wraps 
from flask import abort

data_bp = Blueprint("data", __name__)

PAGE_SIZE = 25


# ---------- helpers ----------

@data_bp.app_template_global()
def new_uid():
    """Available in every template as new_uid()."""
    return uuid.uuid4().hex[:8]


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


def parse_filters(form):
    """Turns the submitted form into [(key, op, value), ...] for search_builds.
    Every filter row has a hidden 'filter_uid'; its key, op, and value inputs
    carry that uid in their names, so strings can't be paired with the wrong
    filter no matter how many strings each filter has."""
    filters = []
    for uid in form.getlist("filter_uid"):              # one per filter, DOM order
        key = form.get(f"filter-key-{uid}")
        op = form.get(f"filter-op-{uid}")
        values = [v.strip() for v in form.getlist(f"filter-value-{uid}")]

        kind = input_kind(key, op)
        if kind == "list":
            values = [v for v in values if v]
            if not values:
                continue                                # empty filter: ignore it
            value = values
        elif kind == "pair":
            if not all(values):
                continue
            value = tuple(values)                       # (part, lot)
        else:
            if not values or not values[0]:
                continue
            value = values[0]
        filters.append((key, op, value))
    return filters


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
    filters = [
        ("engraving", "contains", "WR"),
        ("serial", "eq", "1-001"),
        ("has_part_and_lot", "eq", ("A", "100")),
    ]
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


@data_bp.app_template_global()
def edit_sections():
    """Available in templates as edit_sections() -- the single source for
    which fields each section has."""
    return db_service.EDIT_SECTIONS


def _render_section(block_id, section_name, edit_section):
    build = db_service.get_build(block_id)
    if build is None or section_name not in db_service.EDIT_SECTIONS:
        abort(404)
    return render_template(
        "partials/data-comparison/section.html",
        build=build, section_name=section_name, edit_section=edit_section,
    )


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
    try:
        changes = db_service.stage_edit_section(block_id, section_name, request.form)
        if changes:
            # TODO: rewrite the block/build file from the updated row HERE,
            # before the commit, so a failed file write rolls the DB back.
            pass
        db_service.commit_db_changes()
    except ValueError as e:
        db_service.roll_back_db_changes()
        # re-show the form with the message and what the user typed
        return _render_row(db_service.get_build(block_id),
                           edit_section=section_name, edit_error=str(e), form=request.form)
    except Exception:
        db_service.roll_back_db_changes()
        raise

    return _render_row(db_service.get_build(block_id), open_section=section_name)

