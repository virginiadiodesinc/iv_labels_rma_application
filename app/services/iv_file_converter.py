# THIS RETURNS A DICTIONARY WITH ALL THE IV FILE DATA, INCLUDING THE BUILD INFO AND THE IV CURVE DATA POINTS
# The expected format of the returned dict is as follows:
# {
# 	"build_name": "BUILD_NAME",
# 	"build_sn": "BUILD_SN",
# 	"diode": "DIODE_NAME",
# 	"circuit": "CIRCUIT_NAME",
# 	"assembly_number": "ASSEMBLY_NUMBER",
# 	"polarity": "POLARITY",
# 	"block_name": "BLOCK_NAME",
# 	"block_sn": "BLOCK_SN",
# 	"additional_info": "ADDITIONAL_INFO",
# 	"date": "DATE",
# 	"time": "TIME",
# 	"points_per_decade": "POINTS_PER_DECADE",
# 	"ideality": "IDEALITY",
# 	"is": "IS",
# 	"rs": "RS",
# 	"mean_square_error": "MEAN_SQUARE_ERROR",
# 	"r_squared_error": "R_SQUARED_ERROR",
# 	"hysteresis_sd": "HYSTERESIS_SD",
# 	"hysteresis_max": "HYSTERESIS_MAX",
# 	"hysteresis_min": "HYSTERESIS_MIN",
# 	"reverse_current": "REVERSE_CURRENT",
# 	"reverse_voltage": "REVERSE_VOLTAGE",
# 	"voltage_up": ["VOLTAGE_UP_POINT_1", "VOLTAGE_UP_POINT_2", ...],
# 	"voltage_down": ["VOLTAGE_DOWN_POINT_1", "VOLTAGE_DOWN_POINT_2", ...],
# 	"current": ["CURRENT_POINT_1", "CURRENT_POINT_2", ...]
# }

def convert_iv_file(file):
	"""Converts an IV file to a pattern which can be used to populate the fields of the forms on the page
	
	This function converts a IV file to our input field format

	@param file IV File.
	@return iv_dict Return value of type(dict)
	
	"""
	file_content = file.read()
	lines = file_content.splitlines()
	iv_dict = {}

	for index, line in enumerate(lines):
		# FIRST LINE: Build Name, Build SN(and Rev Letter), Diode, Circuit, Assembly Number, 
		# Polarity?, Block Name, Block SN(and Rev Letter), Additional Info
		if index == 0:
			split_line = line.split()
			iv_dict["build_name"] = split_line[0].split('_')[0]
			iv_dict["full_build_sn"] = split_line[1][1:]
			iv_dict["build_sn"] = split_line[1][1:-1] if split_line[1][-1].isalpha() else split_line[1][1:]
			iv_dict["build_revision"] = split_line[1][-1] if split_line[1][-1].isalpha() else ''
			iv_dict["diode"] = split_line[2]
			iv_dict["circuit"] = split_line[3].replace("Cir", "")
			iv_dict["assembly_number"] = split_line[4].replace("A#", "")  # Remove "A#" if present

			polarity_offset = 5  # Default index for polarity
			if len(split_line) > 7:
				iv_dict["polarity"] = split_line[polarity_offset]
			else:
				polarity_offset = 4

			iv_dict["block_name"] = split_line[polarity_offset + 1]
			iv_dict["block_sn"] = split_line[polarity_offset + 2]
			iv_dict["additional_info"] = " ".join(split_line[polarity_offset + 3:]) if len(split_line) > (polarity_offset + 3) else ""

		# SECOND LINE: Date, Time
		if index == 1:
			split_line = line.split()
			iv_dict["date"] = split_line[0]
			iv_dict["time"] = split_line[1] + " " + split_line[2]

		#THIRD LINE: Points per Decade
		if index == 2:
			split_line = line.split()
			iv_dict["points_per_decade"] = split_line[1]

		# FOURTH LINE: Ideality
		if index == 3:
			split_line = line.split()
			iv_dict["ideality"] = split_line[2]

		# FIFTH LINE: Is
		if index == 4:
			split_line = line.split()
			iv_dict["is"] = split_line[1]

		# SIXTH LINE: Rs
		if index == 5:
			split_line = line.split()
			iv_dict["rs"] = split_line[1]

		# SEVENTH LINE: Mean Square Error
		if index == 6:
			split_line = line.split()
			iv_dict["mean_squared_error"] = split_line[3]

		# EIGHTH LINE: R^2 Error
		if index == 7:
			split_line = line.split()
			iv_dict["r_squared_error"] = split_line[2]

		# NINTH LINE: Polarity
		if index == 8:
			split_line = line.split()
			iv_dict["polarity"] = split_line[1] if len(split_line) > 1 else " "

		# TENTH LINE: Hysteresis SD (mV)
		if index == 9:
			split_line = line.split()
			iv_dict["hysteresis_std"] = split_line[4]

		# ELEVENTH LINE: Hysteresis Mean (mV)
		if index == 10:
			split_line = line.split()
			iv_dict["hysteresis_mean"] = split_line[4]

		# ELEVENTH LINE: Hysteresis Max (mV)
		if index == 11:
			split_line = line.split()
			iv_dict["hysteresis_max"] = split_line[4]

		# TWELFTH LINE: Hysteresis Min (mV)
		if index == 12:
			split_line = line.split()
			iv_dict["hysteresis_min"] = split_line[4]

		# THIRTEENTH LINE: Reverse Current (uA)
		if index == 13:
			split_line = line.split()
			iv_dict["reverse_current"] = split_line[3]

		# FOURTEENTH LINE: Reverse Voltage (V)
		if index == 14:
			split_line = line.split()
			iv_dict["reverse_voltage"] = split_line[3]

		# FIFTEENTH LINE: [HEADERS] Voltage Up (mV), Voltage Down (mV), Current (uA)
		if index == 15:
			iv_dict["voltage_up"] = []
			iv_dict["voltage_down"] = []
			iv_dict["current"] = []

		# SIXTEENTH LINE AND BEYOND: [DATA POINTS] Voltage Up (mV), Voltage Down (mV), Current (uA)
		if index >= 16:
			split_line = line.split()
			if len(split_line) >= 3:
				iv_dict["voltage_up"].append(split_line[0])
				iv_dict["voltage_down"].append(split_line[1])
				iv_dict["current"].append(split_line[2])

	return iv_dict