from flask import Blueprint, request, render_template
from app.services.keithley_236_functions import SMU_K236, Fake_SMU, get_SMU
import pandas as pd
import plotly.express as px
from app.services import postprocess_static as pps
import traceback

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

		static_reverse_source = None
		static_reverse_measure = None
		if SMU_controls.get('reverse-breakdown-test') == 'on':
			static_reverse_source, static_reverse_measure = SMU.takeReverseBreakdown()
			static_reverse_source = pps.clean_string_or_list_values(static_reverse_source, conversion_factor=6)
			static_reverse_measure = pps.clean_string_or_list_values(static_reverse_measure)

		##############################
		static_source_values = pps.clean_string_or_list_values(source_values)
		static_voltage_up_values = pps.clean_string_or_list_values(voltage_up_values)
		static_voltage_down_values = pps.clean_string_or_list_values(voltage_down_values, reverse_list=True)

		process_static_dict = pps.calculate_iv_parameters(static_source_values, static_voltage_up_values, static_voltage_down_values)

		max_reverse_current = 0
		max_reverse_voltage = 0
		if static_reverse_source and static_reverse_measure:
			max_reverse_current, max_reverse_voltage = pps.get_reverse_breakdown_values(static_reverse_source, static_reverse_measure)

		if heat_test:
			heat_current_string, heat_voltage_string = SMU.takeHeatTest()
			heat_current_list = pps.clean_string_or_list_values(heat_current_string)
			heat_voltage_list = pps.clean_string_or_list_values(heat_voltage_string)

			temperature_list = pps.calculate_heat_parameters(heat_current_list, heat_voltage_list, float(process_static_dict["n (ideality)"]))
			process_static_dict["temperature"] = temperature_list[0]

		static_max_current = process_static_dict["Imax"]

		static_iv_dict ={
			"rs": process_static_dict["Rs"],
			"ideality": process_static_dict["n (ideality)"],
			"is": process_static_dict["Is"],
			"r_squared_error": process_static_dict["R^2 Error"],
			"mean_squared_error": process_static_dict["Mean Square Error"],
			"hysteresis_mean": process_static_dict["Hysteresis Mean (mV)"],
			"hysteresis_std": process_static_dict["Hysteresis SD (mV)"],
			"hysteresis_max": process_static_dict["Hysteresis Max (mV)"],
			"hysteresis_min": process_static_dict["Hysteresis Min (mV)"],
			"reverse_current": max_reverse_current,
			"reverse_voltage": max_reverse_voltage,
			"rs_1" : process_static_dict["Rs_1"],
			"rs_4pt": process_static_dict["Rs_4pt"],
			"rs_3pt": process_static_dict["Rs 3pt"],
			"pass_heat": process_static_dict.get("pass_heat", ""),
			"temperature": process_static_dict.get("temperature", ""),
			"i_max": process_static_dict['mV @ Imax'],
			"i_max_10": process_static_dict['mV @ Imax/10'],
			"i_max_100": process_static_dict['mV @ Imax/100'],
			f"{static_max_current}mA": process_static_dict[f'mV @ {static_max_current}mA'],
			f"{static_max_current}00uA": process_static_dict[f'mV @ {static_max_current}00uA'],
			f"{static_max_current}0uA": process_static_dict[f'mV @ {static_max_current}0uA'],
			f"{static_max_current}uA": process_static_dict[f'mV @ {static_max_current}uA'],
			f"{static_max_current}00nA": process_static_dict[f'mV @ {static_max_current}00nA'],
			"dv1": process_static_dict["dV1"],
			"dv2": process_static_dict["dV2"],
			"dv3": process_static_dict["dV3"],
			"dv4": process_static_dict["dV4"],
			"dv5": process_static_dict["dV5"],
			"max_current": static_max_current,
			"polarity": translated_settings["polarity"],
			"points_per_decade": translated_settings["points_per_decade"]
		}

		static_source_values = process_static_dict['I (uA)']
		static_source_values = [str(abs(float(value))) for value in static_source_values]

		static_voltage_up_values = process_static_dict['Vup (mV)']
		static_voltage_down_values = process_static_dict['Vdown (mV)']
		static_voltage_avg_values = [str(abs(((float(up) + float(down)) / 2) / 1000.0)) for up, down in zip(static_voltage_up_values, static_voltage_down_values)]

		static_truncated_source_values = ["{:.2f}".format(float(value)) for value in static_source_values]
		static_truncated_voltage_values = ["{:.2f}".format(float(value)) for value in static_voltage_avg_values]

		static_df = pd.DataFrame({
			"Current (uA)": static_truncated_source_values,
			"Voltage (V)": static_truncated_voltage_values
		})

		static_fig = px.scatter(static_df, x="Voltage (V)", y="Current (uA)", labels={"x": "Voltage (V)", "y": "Current (uA)"}, title=None, log_x=False, log_y=True)
		static_fig.update_traces(mode='lines+markers')

		static_iv_curve = {} 
		static_iv_curve["figure"] = static_fig.to_html(full_html=False)
		static_iv_curve["iv_source_values"] = ",".join(static_source_values)
		static_iv_curve["iv_measurement_values"] = ",".join(static_voltage_avg_values)
		static_iv_curve["iv_voltage_up"] = ",".join(static_voltage_up_values)
		static_iv_curve["iv_voltage_down"] = ",".join(static_voltage_down_values)
		static_iv_curve["polarity"] = SMU_controls.get("polarity", "")
		static_iv_curve["points_per_decade"] = SMU_controls.get("points-per-decade", "")

		if heat_test:
			static_iv_curve["heat_current_list"] = ",".join(str(item) for item in heat_current_list)
			static_iv_curve["heat_voltage_list"] = ",".join(str(item) for item in heat_voltage_list)
			static_iv_curve["temperature_list"] = ",".join(str(item) for item in temperature_list)

		##################################################################

		return render_template("partials/iv-page/run-iv-response.html", iv_curve=static_iv_curve, iv_data=static_iv_dict)

	except Exception as e:
		traceback.print_exc()
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

		polarity_measure_current = pps.clean_string_or_list_values(polarity_measure_current)
		polarity = pps.get_polarity(polarity_measure_current)

		return (f"Polarity: {polarity}")

	except Exception as e:
		traceback.print_exc()
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