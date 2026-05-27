from datetime import datetime


def labview_date_to_iso(labview_date):
	"""Converts a date from LabView format to ISO format
	
	This function converts a date of the style found in the LabView files (month/day/year with no leading zeros) 
	to the traditional ISO format.

	@param labview_date LabView-Style Date (string)
	@return iso_date Return value of type (datetime)
	"""
	if len(labview_date) < 6:
		return ""
	return (datetime.strptime(labview_date, "%m/%d/%Y").strftime("%Y-%m-%d"))


def iso_date_to_labview(iso_date):
	"""Converts a date from ISO format to LabView format
	
	This function converts a date of the traditional ISO format 
	to the style found in the LabView files (month/day/year with no leading zeros).

	@param iso_date LabView-Style Date (datetime)
	@return labview_date Return value of type (string)
	"""
	if len(iso_date) < 6:
		return ""
	return (datetime.strptime(iso_date, "%Y-%m-%d").strftime("%#m/%#d/%Y"))


def string_to_python_date(html_form_date):
	if len(html_form_date) < 6:
		return ""
	return(datetime.strptime(html_form_date, "%Y-%m-%d").date())