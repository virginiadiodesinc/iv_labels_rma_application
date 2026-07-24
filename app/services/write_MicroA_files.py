import statistics

def write_block_file(block_dict):
	"""
	Takes a dictionary with the following keys:

	block_engraving, PB1_name, block_sn, rows_build_label_1, rows_build_label_2, inspection_date, inspection_initials, PB1_date,
	PB1_initials, PB2_name, PB2_date, PB2_initials, PB2_passfail, PB2_bond_wire_pads, PB2_components, PB2_inspection

	and writes their values to a text file in the block file template adopted on 5/9/2024

	Names the file with block_engraving and block_sn values
	"""
	rows = []
	i = 0

	print(block_dict)

	rows.append(block_dict['block_engraving'] + ' ' + block_dict['PB1_name'])
	rows.append(block_dict['block_sn'] + ' ' + '12' + ' ' + '12')
	rows.append(block_dict['inspection_date'])
	rows.append(block_dict['inspection_initials'])
	rows.append(block_dict['PB1_date'])
	rows.append(block_dict['PB1_initials'] + ';' +
				block_dict['PB2_name'] + ';' +
				block_dict['PB2_date'] + ';' +
				block_dict['PB2_initials'] + ';' +
				" " + ';' +#block_dict['PB2_passfail'] + ';' + We're removing these so we'll need to come up with some way to read old files without breaking the code
				" " + ';' +#block_dict['PB2_bond_wire_pads'] + ';' +
				" " + ';' +#block_dict['PB2_components'] + ';' +
				block_dict['PB2_inspection'])
	
	file_name = f'{block_dict["block_engraving"]}' + ' ' + f'{block_dict["block_sn"]}' + '.txt'
	file_name = file_name.lower()
	
	return file_name, rows

	# with open(file_name, 'w', encoding='utf-8') as block_file:
	# 	for row in rows:
	# 		block_file.write(row)
	# 		if i != len(rows) - 1:
	# 			i += 1
	# 			block_file.write('\n')

def write_build_file(block_dict, build_dict, build_name):
	"""
	Takes two dictionaries, block_dict and build_dict, with the following sets of keys, respectively:

	block_engraving, PB1_name, block_sn, rows_build_label_1, rows_build_label_2, inspection_date, inspection_initials, PB1_date,
	PB1_initials, PB2_name, PB2_date, PB2_initials, PB2_passfail, PB2_bond_wire_pads, PB2_components, PB2_inspection

	diode1, qty_chips1, assembly_initials1, assembly_date1, circuit1, indium, Vbr, MMIC, MMIC_lot, notes, PCB, filter1, diode2, qty_chips2,
	assembly_initials2, assembly_date2, circuit2, notes1, notes2, notes3, notes4, notes5, notes6, filter2

	and writes their values to a text file in the build file template adopted on 5/9/2024

	Names the file with build_name and block_sn values
	"""
	rows = []
	i = 0

	print(block_dict)
	print(build_dict)

	rows.append(block_dict['block_engraving'] + ' ' + block_dict['PB1_name'])
	rows.append(block_dict['block_sn'] + ' ' + '12' + ' ' + '12')
	rows.append(block_dict['inspection_date'])
	rows.append(block_dict['inspection_initials'])
	rows.append(block_dict['PB1_date'])
	rows.append(block_dict['PB1_initials'] + ';' +
				block_dict['PB2_name'] + ';' +
				block_dict['PB2_date'] + ';' +
				block_dict['PB2_initials'] + ';' +
				block_dict['PB2_passfail'] + ';' +
				block_dict['PB2_bond_wire_pads'] + ';' +
				block_dict['PB2_components'] + ';' +
				block_dict['PB2_inspection'])
	
	rows.append(build_dict['diode1'])
	rows.append(build_dict['qty_chips1'])
	rows.append(build_dict['assembly_initials1'])
	rows.append(build_dict['assembly_date1'])
	rows.append(build_dict['circuit1'])
	rows.append(build_dict['indium'])
	rows.append(build_dict['Vbr'])
	rows.append(build_dict['MMIC'])
	rows.append(build_dict['MMIC_lot'])
	rows.append(build_dict['notes'])
	rows.append(build_dict['PCB'])
	rows.append(build_dict['filter1'])
	rows.append(build_dict['diode2'])
	rows.append(build_dict['qty_chips2'])
	rows.append(build_dict['assembly_initials2'])
	rows.append(build_dict['assembly_date2'])
	rows.append(build_dict['circuit2'])
	rows.append(build_dict['notes1'])
	rows.append(build_dict['notes2'])
	rows.append(build_dict['notes3'])
	rows.append(build_dict['notes4'])
	rows.append(build_dict['notes5'])
	rows.append(build_dict['notes6'])
	rows.append(build_dict['filter2'])

	file_name = f'{build_name.lower()}' + ' ' + f'{block_dict["block_sn"].lower()}' + '.txt'

	return file_name, rows

	# with open(file_name, 'w', encoding='utf-8') as build_file:
	# 	for row in rows:
	# 		build_file.write(row)
	# 		if i != len(rows) - 1:
	# 			i += 1
	# 			build_file.write('\n')

def write_IV_file(info_dict, IV_dict, Vup_list, Vdown_list, I_source_list):
	"""
	Takes two dictionaries, info_dict and IV_dict, with the following sets of keys, respectively

	build_name, build_sn, diode, circuit, assembly_no, polarity, block_engraving, block_sn, medium, date, time

	Points\Decade, n (ideality), Is, Rs, Mean Square Error, R^2 Error, Polarity, Hysteresis SD (mV), Hysteresis Mean (mV), Hysteresis Max (mV), Hysteresis Min (mV),
	Reverse Current (uA), Reverse Voltage(V), ? ? ? pass_heat ? ? ?, ? ? ? temperature ? ? ?

	Also takes three lists Vup, Vdown, and Isource

	and writes their values to a text file per the IV file format.

	Names the file based on values in info_dict.

	? ? ? Appends heat test result to Dave Kurtz's spreadsheet ? ? ?
	"""
	rows = []
	i = 0

	print("INFO", info_dict)
	print("IV INFO", IV_dict)

	rows.append(info_dict['build_name'] + ' ' +
				'B' + info_dict['build_sn'] + ' ' +
				info_dict['diode'] + ' ' +
				'Cir' + info_dict['circuit'] + ' ' +
				'A#' + info_dict['assembly_no'] + ' ' +
				info_dict['polarity'] + ' ' +
				info_dict['block_engraving'] + ' ' +
				info_dict['block_sn'] + ' ' +
				info_dict['medium'])
	rows.append(info_dict['date'] + ' ' + info_dict['time'])
	rows.append('Points/Decade: ' + IV_dict['Points/Decade'])
	rows.append('n (ideality): ' + IV_dict['n (ideality)'])
	rows.append('Is: ' + IV_dict['Is'])
	rows.append('Rs: ' + IV_dict['Rs'])
	rows.append('Mean Square Error: ' + IV_dict['Mean Square Error'])
	rows.append('R^2 Error: ' + IV_dict['R^2 Error'])
	rows.append('Polarity: ' + IV_dict['Polarity'])
	rows.append('Hysteresis SD (mV) = ' + IV_dict['Hysteresis SD (mV)'])
	rows.append('Hysteresis Mean (mV) = ' + IV_dict['Hysteresis Mean (mV)'])
	rows.append('Hysteresis Max (mV) = ' + IV_dict['Hysteresis Max (mV)'])
	rows.append('Hysteresis Min (mV) = ' + IV_dict['Hysteresis Min (mV)'])
	rows.append('Reverse Current (uA): ' + IV_dict['Reverse Current (uA)'])
	rows.append('Reverse Voltage (V): ' + IV_dict['Reverse Voltage (V)'])
	rows.append('Voltage Up (mV)    Voltage Down (mV)    Current (uA)')

	for Vup, Vdown, I_source in zip(Vup_list, Vdown_list, I_source_list):
		rows.append(f"{float(Vup):6f}" + '\t' + f"{float(Vdown):6f}" + '\t' + f"{float(I_source):6f}")

	rows.append('')

	file_name = rows[0].lower() + '.iv'

	return file_name, rows

	# with open(file_name, 'w', encoding='utf-8') as IV_file:
	# 	for row in rows:
	# 		IV_file.write(row)
	# 		if i != len(rows) - 1:
	# 			i += 1
	# 			IV_file.write('\n')

def write_heat_test_file(iv_file_name, heat_current_list, heat_voltage_list, temperature_list, 
						 date, time,
						 ideality, saturation_current):
	cold_voltage_list = heat_voltage_list[0:10]
	cold_mean_voltage = statistics.mean(float(item) for item in cold_voltage_list)

	hot_current_list = heat_current_list[-100:]
	hot_voltage_list = heat_voltage_list[-100:]

	ten_pt_delta = float(temperature_list[0]) - float(temperature_list[9])
	hundred_pt_delta = float(temperature_list[9]) - float(temperature_list[99])
	end_delta = float(temperature_list[-1]) - 25

	file_rows = []

	first_row = (f"{date} {time}\t{iv_file_name}" 
			f";Heat(mA)=5.000E+1;Meas(mA)=1.000E-1;Htime(mS)=300;Mtime(mS)=100;PreTime(mS)=10;" 
				f"n={float(ideality):.3f};Is={float(saturation_current):.3e};10ptdeltaT={ten_pt_delta:.3f};100ptdeltaT={hundred_pt_delta:.3f};EnddeltaT={end_delta:.3f}")
	second_row = "Time(mS)\tTemp(C) (V)"

	data_rows = []
	for i in range(len(hot_voltage_list)):
		row = f"{(1 + i):5e}\t{float(temperature_list[i]):.5e}\t{float(hot_voltage_list[i]):.5e}\t{1:.5e}"
		data_rows.append(row)

	file_rows.append(first_row)
	file_rows.append(second_row)
	for row in data_rows:
		file_rows.append(row)

	settled_temperature_row = f"{(len(hot_voltage_list) + 1):.5e}\t{25:.5e}\t{cold_mean_voltage:.5e}\t{1:.5e}"
	file_rows.append(settled_temperature_row)

	heat_file_name = iv_file_name.replace(".iv", ".txt")

	return heat_file_name, file_rows