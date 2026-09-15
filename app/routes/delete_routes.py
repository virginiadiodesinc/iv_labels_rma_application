from flask import Blueprint, request, render_template
from app.services import field_registry as fr
from app.services import validate_red_flags as vrf
from app.services import delete_orchestrator

delete_bp = Blueprint("delete", __name__)


def _handle_build_block_delete(route_name, red_flag_checks, orchestrator_fn):
    canonical = fr.canonical_from_form(request.form)
    confirmed = request.form.get("confirmed") == "true"
    block_id = fr.build_block_id(canonical)

    errors = vrf.validate_info(canonical, red_flag_checks)
    if errors:
        return render_template("partials/generic/red-flag-error-message.html", errors=errors), 200

    if not confirmed:
        return render_template(
            "partials/generic/delete-confirmation-dialog.html",
            route=route_name,
        ), 200

    result = orchestrator_fn(block_id)

    if not result.success:
        print(result)
        return render_template(
            "partials/generic/delete-error.html",
            failure_cause=result.failure_cause,
        ), 200

    return render_template("partials/generic/delete-success.html"), 200


@delete_bp.delete("/delete_block_info")
def delete_block_info():
    return


@delete_bp.delete("/delete_build_info")
def delete_build_info():
    return


@delete_bp.post("/delete_iv_info/")
def delete_iv_info_route():
    route_name = "delete_iv_info"
    iv_id = request.form.get("selected-iv-id")
    confirmed = request.form.get("confirmed") == "true"

    if not confirmed:
            return render_template(
                "partials/generic/delete-iv-confirmation-dialog.html",
                route=route_name,
                iv_id=iv_id
            ), 200
    
    result = delete_orchestrator.delete_iv_info(iv_id)

    if not result.success:
        return render_template("partials/generic/delete-error.html", failure_cause=result.failure_cause), 200

    return render_template("partials/generic/delete-success.html"), 200