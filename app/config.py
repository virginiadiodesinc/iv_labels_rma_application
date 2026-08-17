import os

app_root_directory = os.path.dirname(os.path.abspath(__file__))


iv_file_auto_directory = os.path.abspath('I:/Alpha IV program testing')
iv_file_directory = os.path.abspath('I:/')
block_file_directory = os.path.abspath('K:/block')
build_file_directory = os.path.abspath('K:/build')
heat_data_directory = os.path.abspath('I:/Alpha IV program testing/Heat Data')
iv_spec_directory = os.path.abspath('V:/Production/Inventory/General/SpecialDiodeMarks')

block_list_file = os.path.join(app_root_directory, 'services', 'block_engravings.csv')
build_list_file = os.path.join(app_root_directory, 'services', 'build_list.csv')

default_keithley_settings = {
	# BASIC SETTINGS
	"compliance_voltage": 4.0,
	"polarity": '+',
	"maximum_current": '1mA',
	"reverse_polarity_start_current": 10.0,
	"reverse_compliance_voltage": 100.0,
	# ADVANCED SETTINGS
	"default_delay": 'on',
	"integration_time": 'Medium',
	"sweep_delay": 0,
	"points_per_decade": '5',
	"filter_readings": '8',
	"gpib_address": 16
}
