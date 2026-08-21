from app.services import dymo_printer as printer

def print_full_build(full_build_info):
	"""Prints a full build label
	
	This function prints from the relevant fields a dynamic label including all parts and notes

	@return print_engine Return value of type (callable)
	"""

	printer.print_engine("full_build_270.label", printer.populate_full_build_label_fields, full_build_info, printer.prepare_full_build_label)
	return "", 204


def print_block_inspection(inspection_info):
	"""Prints an inspection label
	
	This function prints from the relevant fields an inspection label identical to the LabView version

	@return print_engine Return value of type (callable)
	"""
	
	printer.print_engine("inspection.label", printer.populate_inspection_label_fields, inspection_info)
	return "", 204


def print_pb1_label(pb1_info):
	"""Prints a PB1 label
	
	This function prints from the relevant fields an PB1 label identical to the LabView version

	@return print_engine Return value of type (callable)
	"""

	printer.print_engine("pb1.label", printer.populate_pb1_label_fields, pb1_info)
	return "", 204


def print_pb2_label(pb2_info):
	"""Prints a PB2 label
	
	This function prints from the relevant fields an PB2 label identical to the LabView version
	(minus some now unnecessary fields)

	@return print_engine Return value of type (callable)
	"""

	printer.print_engine("pb2.label", printer.populate_pb2_label_fields, pb2_info)