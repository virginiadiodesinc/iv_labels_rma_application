import date_converter

def eliminate_whitespace_in_field_list(field_list):
	new_field_list = []
	
	for field in field_list:
		if not field:
			field = "X"
		new_field_list.append(field)

	return new_field_list

def sanitize_block_build_revision(revision):
	if not revision:
		return "A"
	else:
		return revision


