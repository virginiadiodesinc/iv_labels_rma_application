import uuid
from flask import Blueprint, request, render_template
from app.services import db_service

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
        "partials/data-comparison/filter-string-container.html",
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
        print(total)
        for build in builds:
            build_dict = db_service.build_to_dict(build)
            print(build_dict)
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
