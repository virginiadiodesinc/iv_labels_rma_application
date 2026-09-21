from flask import Blueprint, request, render_template
from app.services import field_registry as fr
from app.services import save_orchestrator
from app.services import validate_red_flags as vrf
from app.services import validate_yellow_flags as vyf
from app.services import parts_service
from app.services import print_service

save_bp = Blueprint("save", __name__)


def _handle_save(route_name, red_flag_checks, yellow_flag_checks, orchestrator_fn, build_name_key='full_build_name',
                 print_fn=None, collects_parts=False):
    """One handler for every block/build save. The stages differ only in
    which validators run, which yellow-flag set applies, which orchestrator
    function is called, what gets printed, and whether parts/notes come
    along -- all parameters, so there's no reason for two near-identical
    handlers anymore.

    collects_parts=True is everything from PB1 onward: prebuilds now carry
    parts, so parts/notes gathering is no longer full-build-only. Only the
    inspection save leaves it False."""
    canonical = fr.canonical_from_form(request.form)
    confirmed = request.form.get("confirmed") == "true"
    print_label = request.form.get("print_label") == "true"

    parts_list = notes_list = None
    if collects_parts:
        parts_list = parts_service.parts_from_form(request.form)
        notes_list = parts_service.notes_from_form(request.form)
        # Slot names (diode1, MMIC, Vbr...) merged into canonical so
        # BUILD_FILE_TEMPLATE can render them as ordinary Field tokens.
        # canonical_to_db_kwargs filters by db_model, so these never leak
        # into the Build_Info upsert.
        canonical.update(parts_service.assign_parts_to_build_slots(parts_list))

    errors = vrf.validate_info(canonical, red_flag_checks)
    if collects_parts:
        errors.extend(vrf.validate_all_lots_chosen(parts_list))
    if errors:
        return render_template("partials/generic/red-flag-error-message.html", errors=errors), 200

    flag_ctx = vyf.FlagContext(
        canonical=fr.with_build_name_from(canonical, build_name_key),
        parts=parts_list or [],
        notes=notes_list or [],
    )
    yellow_flags = vyf.check_yellow_flags(flag_ctx, yellow_flag_checks)
    yellow_flags_found = vyf.any_flag_raised(yellow_flags)
    if not confirmed:
        return render_template(
            "partials/generic/save-confirmation-dialog.html",
            route=route_name,
            yellow_flag_dict=yellow_flags,
            yellow_flags_found=yellow_flags_found,
            print_label=print_label
        ), 200

    canonical = fr.merge_yellow_flags(canonical, yellow_flags)

    if collects_parts:
        result = orchestrator_fn(canonical, parts_list, notes_list)
    else:
        result = orchestrator_fn(canonical)

    if not result.success:
        print(result)
        return render_template(
            "partials/generic/save-error.html",
            failure_cause=result.failure_cause,
        ), 200

    if result.warning:
        # Saved fine; a superseded file just couldn't be cleaned up.
        print(result.warning)

    # Was `if print:` -- the builtin, always truthy, so the full-build route
    # printed on every save regardless of the checkbox, and ignored print_fn.
    if print_label and print_fn:
        print_fn(request.form)

    return render_template("partials/generic/save-success.html"), 200


@save_bp.post("/save_inspection_info/")
def save_inspection_info():
    return _handle_save(
        "save_inspection_info",
        [vrf.validate_block_identification, vrf.validate_inspection_info],
        vyf.UNIVERSAL_BLOCK_YELLOW_FLAG_CHECKS,
        save_orchestrator.save_inspection_info,
        print_fn=print_service.print_block_inspection,
        collects_parts=False,
    )


@save_bp.post("/save_pb1_info/")
def save_pb1_info():
    return _handle_save(
        "save_pb1_info",
        [vrf.validate_block_identification, vrf.validate_inspection_info, vrf.validate_pb1_info],
        vyf.FULL_BUILD_YELLOW_FLAG_CHECKS,
        save_orchestrator.save_pb1_info,
        print_fn=print_service.print_pb1_label,
        collects_parts=True,
        build_name_key="pb1_build_name"
    )


@save_bp.post("/save_pb2_info/")
def save_pb2_info():
    return _handle_save(
        "save_pb2_info",
        [vrf.validate_block_identification, vrf.validate_inspection_info, vrf.validate_pb2_info],
        vyf.FULL_BUILD_YELLOW_FLAG_CHECKS,
        save_orchestrator.save_pb2_info,
        print_fn=print_service.print_pb2_label,
        collects_parts=True,
        build_name_key="pb2_build_name"
    )


@save_bp.post("/save_block_info/")
def save_block_info():
    """Now identical to save_build_info -- see the note in save_orchestrator.
    Safe to delete along with its UI entry point."""
    return _handle_save(
        "save_block_info",
        [
            vrf.validate_block_identification,
            vrf.validate_inspection_info,
            vrf.validate_full_build_info,
        ],
        vyf.FULL_BUILD_YELLOW_FLAG_CHECKS,
        save_orchestrator.save_block_info,
        collects_parts=True,
    )


@save_bp.post("/save_build_info/")
def save_build_info():
    return _handle_save(
        "save_build_info",
        [
            vrf.validate_block_identification,
            vrf.validate_inspection_info,
            vrf.validate_full_build_info,
        ],
        vyf.FULL_BUILD_YELLOW_FLAG_CHECKS,
        save_orchestrator.save_build_info,
        print_fn=print_service.print_full_build,
        collects_parts=True,
    )


@save_bp.post("/save_iv_info/")
def save_iv_info():
    canonical = fr.canonical_from_form(request.form)
    print(canonical)
    confirmed = request.form.get("confirmed") == "true"

    iv_parts = parts_service.iv_parts_from_form(request.form)
    canonical.update(iv_parts)

    errors = vrf.validate_info(canonical, [vrf.validate_iv_identification])
    lot_chosen_errors = vrf.validate_iv_lots_chosen(iv_parts)
    errors.extend(lot_chosen_errors)
    if errors:
        return render_template("partials/generic/red-flag-error-message.html", errors=errors), 200

    yellow_flags = vyf.check_yellow_flags(vyf.FlagContext(canonical), vyf.IV_YELLOW_FLAG_CHECKS)
    yellow_flags_found = vyf.any_flag_raised(yellow_flags)
    if not confirmed:
        return render_template(
            "partials/generic/save-confirmation-dialog.html",
            route="save_iv_info",
            yellow_flag_dict=yellow_flags,
            yellow_flags_found=yellow_flags_found,
        ), 200

    canonical = fr.merge_yellow_flags(canonical, yellow_flags)

    vup_list = request.form.get("iv-voltage-up", "").split(",")
    vdown_list = request.form.get("iv-voltage-down", "").split(",")
    isource_list = request.form.get("iv-source-values", "").split(",")

    heat_current_raw = request.form.get("heat-current-list", "")
    heat_voltage_raw = request.form.get("heat-voltage-list", "")
    heat_current_list = heat_current_raw.split(",") if heat_current_raw else []
    heat_voltage_list = heat_voltage_raw.split(",") if heat_voltage_raw else []
 
    result = save_orchestrator.save_iv_info(
        canonical, vup_list, vdown_list, isource_list, heat_current_list, heat_voltage_list
    )

    if not result.success:
        print(result)
        return render_template("partials/generic/save-error.html", failure_cause=result.failure_cause), 200

    return render_template("partials/generic/save-success.html"), 200