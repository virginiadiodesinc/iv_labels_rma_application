from flask import Blueprint, request
from app.services import build_file_converter as build_converter, block_file_converter as block_converter, dymo_printer as printer, iv_file_converter as iv_converter

print_bp = Blueprint("print", __name__)

@print_bp.post("/print/full_build/")
def print_full_build():
	full_build_info = request.form
	printer.print_engine("full_build.label", printer.populate_full_build_label_fields, full_build_info, printer.prepare_full_build_label)
	return "", 204

@print_bp.post("/print/inspection_label/")
def print_block_inspection():
	inspection_info = request.form
	printer.print_engine("inspection.label", printer.populate_inspection_label_fields, inspection_info)
	return "", 204

@print_bp.post("/print/pb1_label/")
def print_pb1_label():
	pb1_info = request.form
	printer.print_engine("pb1.label", printer.populate_pb1_label_fields, pb1_info)
	return "", 204

@print_bp.post("/print/pb2_label/")
def print_pb2_label():
	pb2_info = request.form
	printer.print_engine("pb2.label", printer.populate_pb2_label_fields, pb2_info)