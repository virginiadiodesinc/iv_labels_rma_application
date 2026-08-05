from flask import Blueprint, request
from app.services import build_file_converter as build_converter, block_file_converter as block_converter, dymo_printer as printer, iv_file_converter as iv_converter


print_bp = Blueprint("print", __name__)

@print_bp.post("/print/full_build/")
def print_full_build():
	"""Prints a full build label
	
	This function prints from the relevant fields a dynamic label including all parts and notes

	@return print_engine Return value of type (callable)
	"""
	full_build_info = request.form
	printer.print_engine("full_build_270.label", printer.populate_full_build_label_fields, full_build_info, printer.prepare_full_build_label)
	return "", 204

@print_bp.post("/print/inspection_label/")
def print_block_inspection():
	"""Prints an inspection label
	
	This function prints from the relevant fields an inspection label identical to the LabView version

	@return print_engine Return value of type (callable)
	"""
	inspection_info = request.form
	printer.print_engine("inspection.label", printer.populate_inspection_label_fields, inspection_info)
	return "", 204

@print_bp.post("/print/pb1_label/")
def print_pb1_label():
	"""Prints a PB1 label
	
	This function prints from the relevant fields an PB1 label identical to the LabView version

	@return print_engine Return value of type (callable)
	"""
	pb1_info = request.form
	printer.print_engine("pb1.label", printer.populate_pb1_label_fields, pb1_info)
	return "", 204

@print_bp.post("/print/pb2_label/")
def print_pb2_label():
	"""Prints a PB2 label
	
	This function prints from the relevant fields an PB2 label identical to the LabView version
	(minus some now unnecessary fields)

	@return print_engine Return value of type (callable)
	"""
	pb2_info = request.form
	printer.print_engine("pb2.label", printer.populate_pb2_label_fields, pb2_info)