from flask import Blueprint, request, render_template
from app.services.keithley_236_functions import SMU_K236, Fake_SMU, get_SMU
from app.services import postprocess as pp
import pandas as pd
import plotly.express as px

iv_bp = Blueprint("iv", __name__)

@iv_bp.post("/take_iv/")
def take_iv():
	SMU_controls = request.form
	heat_test = request.form.get("heat_test") == "true"

	SMU = get_SMU()

	translated_settings = {
		# BASIC SETTINGS
		"compliance_voltage": float(SMU_controls.get("compliance-voltage")),
		"polarity": SMU_controls.get("polarity"),
		"maximum_current": SMU_controls.get("maximum-current") + "mA",
		"reverse_polarity_start_current": SMU_controls.get("reverse-current"),
		"reverse_compliance_voltage": SMU_controls.get("reverse-compliance"),
		# ADVANCED SETTINGS
		"default_delay": 'on' if SMU_controls.get("default-delay") == "on" else "off",
		"integration_time": SMU_controls.get("integration-time"),
		"filter_readings": SMU_controls.get("filter-readings"),
		"points_per_decade": SMU_controls.get("points-per-decade"),
		"sweep_delay": float(SMU_controls.get("sweep-delay")) if SMU_controls.get("sweep-delay") else 0,
		"gpib_address": SMU_controls.get("gpib-address")
	}

	SMU.update_settings(**translated_settings)

	try:
		source_values, voltage_up_values, voltage_down_values = SMU.takeIV()

		reverse_source = ''
		reverse_measure = ''
		if SMU_controls.get('reverse-breakdown-test') == 'on':
			reverse_source, reverse_measure = SMU.takeReverseBreakdown()

		process = pp.IV_curve(source_values, voltage_up_values, voltage_down_values, reverse_source, reverse_measure)
		process_dict = process.calc_IV_parameters()

		max_current = process_dict["Imax"]

		iv_dict ={
			"rs": process_dict["Rs"],
			"ideality": process_dict["n (ideality)"],
			"is": process_dict["Is"],
			"r_squared_error": process_dict["R^2 Error"],
			"mean_squared_error": process_dict["Mean Square Error"],
			"hysteresis_mean": process_dict["Hysteresis Mean (mV)"],
			"hysteresis_std": process_dict["Hysteresis SD (mV)"],
			"hysteresis_max": process_dict["Hysteresis Max (mV)"],
			"hysteresis_min": process_dict["Hysteresis Min (mV)"],
			"reverse_current": process_dict["Reverse Current (uA)"],
			"reverse_voltage": process_dict["Reverse Voltage (V)"],
			"rs_1" : process_dict["Rs_1"],
			"rs_4pt": process_dict["Rs_4pt"],
			"rs_3pt": process_dict["Rs 3pt"],
			"pass_heat": process_dict.get("pass_heat", ""),
			"temperature": process_dict.get("temperature", ""),
			"i_max": process_dict['mV @ Imax'],
			"i_max_10": process_dict['mV @ Imax/10'],
			"i_max_100": process_dict['mV @ Imax/100'],
			f"{max_current}mA": process_dict[f'mV @ {max_current}mA'],
			f"{max_current}00uA": process_dict[f'mV @ {max_current}00uA'],
			f"{max_current}0uA": process_dict[f'mV @ {max_current}0uA'],
			f"{max_current}uA": process_dict[f'mV @ {max_current}uA'],
			f"{max_current}00nA": process_dict[f'mV @ {max_current}00nA'],
			"dv1": process_dict["dV1"],
			"dv2": process_dict["dV2"],
			"dv3": process_dict["dV3"],
			"dv4": process_dict["dV4"],
			"dv5": process_dict["dV5"],
			"max_current": max_current,
			"polarity": translated_settings["polarity"],
			"points_per_decade": translated_settings["points_per_decade"]
		}

		temperature_list = []
		heat_current_list = []
		heat_voltage_list = []
		if heat_test:
			heat_current_string, heat_voltage_string = SMU.takeHeatTest()
			heat_current_list = heat_current_string.split(',')
			heat_voltage_list = heat_voltage_string.split(',')

			temperature_list = process.calc_heat_parameters(heat_current_list, heat_voltage_list, float(iv_dict["ideality"]))
			iv_dict["temperature"] = temperature_list[0]

		source_values = process_dict['I (uA)']
		source_values = [str(abs(float(value))) for value in source_values]

		voltage_up_values = process_dict['Vup (mV)']
		voltage_down_values = process_dict['Vdown (mV)']
		voltage_avg_values = [str(abs(((float(up) + float(down)) / 2) / 1000.0)) for up, down in zip(voltage_up_values, voltage_down_values)]

		truncated_source_values = ["{:.2f}".format(float(value)) for value in source_values]
		truncated_voltage_values = ["{:.2f}".format(float(value)) for value in voltage_avg_values]

		df = pd.DataFrame({
			"Current (uA)": truncated_source_values,
			"Voltage (V)": truncated_voltage_values
		})

		fig = px.scatter(df, x="Voltage (V)", y="Current (uA)", labels={"x": "Voltage (V)", "y": "Current (uA)"}, title=None, log_x=False, log_y=True)
		fig.update_traces(mode='lines+markers')

		iv_curve = {} 
		iv_curve["figure"] = fig.to_html(full_html=False)
		iv_curve["iv_source_values"] = ",".join(source_values)
		iv_curve["iv_measurement_values"] = ",".join(voltage_avg_values)
		iv_curve["iv_voltage_up"] = ",".join(voltage_up_values)
		iv_curve["iv_voltage_down"] = ",".join(voltage_down_values)
		iv_curve["polarity"] = SMU_controls.get("polarity", "")
		iv_curve["points_per_decade"] = SMU_controls.get("points-per-decade", "")

		if heat_test:
			iv_curve["heat_current_list"] = ",".join(str(item) for item in heat_current_list)
			iv_curve["heat_voltage_list"] = ",".join(str(item) for item in heat_voltage_list)
			iv_curve["temperature_list"] = ",".join(str(item) for item in temperature_list)

		return render_template("partials/iv-page/run-iv-response.html", iv_curve=iv_curve, iv_data=iv_dict)

	except RuntimeError:
		return render_template("partials/iv-page/no-keithley-connected-error.html")

@iv_bp.post("/take_polarity_sweep/")
def take_polarity_sweep():
	SMU_controls = request.form

	SMU = get_SMU()

	translated_settings = {
		# BASIC SETTINGS
		"compliance_voltage": float(SMU_controls.get("compliance-voltage")),
		"polarity": SMU_controls.get("polarity"),
		"maximum_current": SMU_controls.get("maximum-current") + "mA",
		"reverse_polarity_start_current": SMU_controls.get("reverse-current"),
		"reverse_compliance_voltage": SMU_controls.get("reverse-compliance"),
		# ADVANCED SETTINGS
		"default_delay": 'on' if SMU_controls.get("default-delay") == "on" else "off",
		"integration_time": SMU_controls.get("integration-time"),
		"filter_readings": SMU_controls.get("filter-readings"),
		"points_per_decade": SMU_controls.get("points-per-decade"),
		"sweep_delay": float(SMU_controls.get("sweep-delay")) if SMU_controls.get("sweep-delay") else 0,
		"gpib_address": SMU_controls.get("gpib-address")
	}

	SMU.update_settings(**translated_settings)

	try:

		polarity_source_voltage, polarity_measure_current = SMU.takePolaritySweep()

		process = pp.IV_curve([], [], [], Polarity_Sweep_source = polarity_source_voltage, Polarity_Sweep_measure = polarity_measure_current)
		polarity = process.find_polarity()

		return ("Polarity: ", polarity)

	except RuntimeError:
		return ("Polarity: No Keithley Connected")


@iv_bp.get("/get_empty_plot")
def get_empty_plot():
	df = pd.DataFrame({
		"Voltage (V)": [],
		"Current (uA)": []
	})

	fig = px.scatter(df, x="Voltage (V)", y="Current (uA)", labels={"x": "Voltage (V)", "y": "Current (uA)"}, title=None, log_y=True)
	fig.update_traces(mode='lines+markers')

	# if abs(df["Voltage (mV)"].astype(float).max() - df["Voltage (mV)"].astype(float).min()) < 100:
	# 	fig.update_xaxes(range=[df["Voltage (mV)"].astype(float).min() - 25, df["Voltage (mV)"].astype(float).min() + 75])

	iv_curve = {} 
	iv_curve["figure"] = fig.to_html(full_html=False)
	iv_curve["iv_source_values"] = ""
	iv_curve["iv_measurement_values"] = ""

	return render_template("partials/iv-page/iv-plot-figure.html", iv_curve=iv_curve)