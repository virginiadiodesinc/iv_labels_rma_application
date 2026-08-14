from flask import Blueprint, request, render_template
from app.services import field_registry as fr
from app.services import save_orchestrator
from app.services import validate_red_flags as vrf
from app.services import validate_yellow_flags as vyf

save_bp = Blueprint("save", __name__)


def _handle_block_save(route_name, red_flag_checks, yellow_flag_checks, orchestrator_fn):
    canonical = fr.canonical_from_form(request.form)
    confirmed = request.form.get("confirmed") == "true"

    errors = vrf.validate_info(canonical, red_flag_checks)
    if errors:
        return render_template("partials/generic/red-flag-error-message.html", errors=errors), 200

    yellow_flags = vyf.check_yellow_flags(canonical, yellow_flag_checks)
    yellow_flags_found = vyf.any_flag_raised(yellow_flags)
    if not confirmed:
        return render_template(
            "partials/generic/save-confirmation-dialog.html",
            route=route_name,
            yellow_flag_dict=yellow_flags,
            yellow_flags_found=yellow_flags_found
        ), 200

    canonical = fr.merge_yellow_flags(canonical, yellow_flags)
    result = orchestrator_fn(canonical)

    if not result.success:
        print(result)
        return render_template(
            "partials/generic/save-error.html",
            failure_cause=result.failure_cause,
        ), 200

    return render_template("partials/generic/save-success.html"), 200


@save_bp.post("/save_inspection_info/")
def save_inspection_info():
    return _handle_block_save(
        "save_inspection_info",
        [vrf.validate_block_identification, vrf.validate_inspection_info],
        vyf.UNIVERSAL_BLOCK_YELLOW_FLAG_CHECKS,
        save_orchestrator.save_inspection_info,
    )


@save_bp.post("/save_pb1_info/")
def save_pb1_info():
    return _handle_block_save(
        "save_pb1_info",
        [vrf.validate_block_identification],
        vyf.UNIVERSAL_BLOCK_YELLOW_FLAG_CHECKS,
        save_orchestrator.save_pb1_info,
    )


@save_bp.post("/save_pb2_info/")
def save_pb2_info():
    return _handle_block_save(
        "save_pb2_info",
        [vrf.validate_block_identification],
        vyf.UNIVERSAL_BLOCK_YELLOW_FLAG_CHECKS,
        save_orchestrator.save_pb2_info,
    )


@save_bp.post("/save_all_block_info/")
def save_all_block_info():
    return _handle_block_save(
        "save_block_file",
        [
            vrf.validate_block_identification,
            vrf.validate_inspection_info
        ],
        vyf.UNIVERSAL_BLOCK_YELLOW_FLAG_CHECKS,
        save_orchestrator.save_all_block_info,
    )
