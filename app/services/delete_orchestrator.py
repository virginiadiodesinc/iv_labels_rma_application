from dataclasses import dataclass
from typing import Callable, Optional

from app.services import field_registry as fr
from app.services import file_service
from app.services import db_service
from app.services import postprocess
from app import config
import traceback
import os


@dataclass
class DeleteResult:
    success: bool
    failure_cause: Optional[str] = None   # "file" or "db"
    error: Optional[Exception] = None


def delete_build_info(canonical: dict) -> DeleteResult:
    block_id = fr.build_block_id(canonical)
    return


def delete_build_info(canonical: dict) -> DeleteResult:
    block_id = fr.build_block_id(canonical)
    return


def delete_block_and_build_info(canonical: dict) -> DeleteResult:
    block_id = fr.build_block_id(canonical)
    return


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