from datetime import datetime
from pathlib import Path
import re

def labview_date_to_iso_with_modified_date_fallback(labview_date, file_path):
	if labview_date_to_iso(labview_date) == False:
		fallback_date = datetime.fromtimestamp(Path(file_path).stat().st_mtime).strftime("%Y-%m-%d")
		return fallback_date
	else:
		return labview_date_to_iso(labview_date)

def labview_date_to_iso(labview_date):
	"""Converts a date from LabView format to ISO format
	
	This function converts a date of the style found in the LabView files (month/day/year with no leading zeros) 
	to the traditional ISO format.

	@param labview_date LabView-Style Date (string)
	@return iso_date Return value of type (datetime)
	"""
	if len(labview_date) < 6:
		return ""
	try:
		labview_date = re.sub(r"\s+", "", labview_date)
		return (datetime.strptime(labview_date, "%m/%d/%Y").strftime("%Y-%m-%d"))
	except Exception as e:
		return False

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