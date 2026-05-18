from datetime import datetime

def labview_date_to_iso(labview_date):
	if len(labview_date) < 6:
		return ""
	return (datetime.strptime(labview_date, "%m/%d/%Y").strftime("%Y-%m-%d"))


def iso_date_to_labview(iso_date):
	if len(iso_date) < 6:
		return ""
	return (datetime.strptime(iso_date, "%Y-%m-%d").strftime("%#m/%#d/%Y"))

def string_to_python_date(html_form_date):
	if len(html_form_date) < 6:
		return ""
	return(datetime.strptime(html_form_date, "%Y-%m-%d").date())