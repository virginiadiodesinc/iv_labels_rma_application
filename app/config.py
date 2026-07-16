import os

iv_file_directory = os.path.abspath('I:/')
block_file_directory = os.path.abspath('K:/block')
build_file_directory = os.path.abspath('K:/build')
heat_data_directory = os.path.abspath('I:/Alpha IV program testing/Heat Data')

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