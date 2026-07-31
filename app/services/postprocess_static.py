import numpy as np
import pandas as pd
import statistics
from scipy.constants import e, k
from scipy.stats import linregress
import math

room_temp_kelvin = 293

def average_two_lists(list_1, list_2):
    if (len(list_1) != len(list_2)):
        return False

    average_list = []
    for item_1, item_2 in zip(list_1, list_2):
        average_item = (item_1 + item_2) / 2
        average_list.append(average_item)

    return average_list

def clean_string_or_list_values(string_or_list, conversion_factor = 0, reverse_list = False):
    is_list = isinstance(string_or_list, list)

    # IF THIS IS A LIST, IT IS EITHER FROM AN IV FILE OR THE DB
    # IN EITHER CASE, WE CAN OPTIONALLY CONVERT THE VALUES
    if is_list:
        valid_list = [float(item) * 10 ** (conversion_factor) for item in string_or_list]

    # IF IT'S A KEITHLEY STRING, CONVERT IT TO A LIST
    # THEN OPTIONALLY APPLY THE CONVERSION
    else:
        valid_list = convert_keithley_string_to_list(string_or_list)
        valid_list = [float(item) * 10 ** (conversion_factor) for item in valid_list]

    if reverse_list:
        valid_list.reverse()

    return valid_list

def convert_keithley_string_to_list(keithley_string):
    keithley_string = keithley_string.replace('/r', '').replace('/n', '')
    keithley_list = keithley_string.split(',')
    keithley_list = [float(item) for item in keithley_list]
    return keithley_list

def calculate_iv_parameters(current_list, voltage_up_list, voltage_down_list):
    # POINTS PER DECADE IS TOTAL NUMBER OF POINTS (- 1) / 4
    points_per_decade = int((len(current_list) - 1) / 4)

    # GET POLARITY JUST BY CHECKING FIRST POINT
    polarity_bool = (current_list[-1] >= 0)
    polarity_symbol = '+' if polarity_bool else '-'

    # NOW EVERYTHING IS POSITIVE
    current_list = np.array([abs(item) for item in current_list])
    voltage_up_list = np.array([abs(item) for item in voltage_up_list])
    voltage_down_list = np.array([abs(item) for item in voltage_down_list])

    # AVERAGE VOLTAGES AND MAKE POSITIVE
    average_voltage_list = average_two_lists(voltage_up_list, voltage_down_list)
    average_voltage_list = np.array(average_voltage_list)

    # GET THE LN OF ALL CURRENTS FOR LATER - ALSO GETTING VARIANCE FOR LATER
    natural_log_current_list = np.array([math.log(current) for current in current_list])
    natural_log_current_variance = statistics.pvariance(natural_log_current_list)

    # THIS IS ALL GUESSED RS VALUES - 0 TO 99.8 INCLUSIVE WITH .2 INCREMENTS
    potential_rs_list = np.linspace(0, 100, 500, endpoint=False)

    # SETTING UP THE LISTS OF ALL THE POSSIBLE LINE REGRESSION VALUES
    potential_regression_slope_list = np.array([])
    potential_regresson_intercept_list = np.array([])
    potential_regression_mse_list = np.array([])

    # LOOP THROUGH EACH GUESSED RS
    for potential_rs in potential_rs_list:
        # MAKE LIST OF VOLTAGES EXCLUDING THE RS
        voltage_without_rs_list = np.array([])

        # FOR EACH POINT: VOLTAGE - CURRENT * THAT GUESSED RS AND ADD IT TO THE LIST
        for current, voltage in np.column_stack((current_list, average_voltage_list)):
            voltage_without_rs = voltage - current * potential_rs
            voltage_without_rs_list = np.append(voltage_without_rs_list, voltage_without_rs)

        # GET YOUR SLOPE AND INTERCEPT USING THIS LINREGRESS
        if len(np.unique(voltage_without_rs_list)) <= 1:
            print("Warning: All x values are identical. Skipping regression.")
            slope, intercept = 0.0, np.mean(natural_log_current_list)
        slope, intercept, _, _, _ = linregress(voltage_without_rs_list, natural_log_current_list)

        # GET THE MSE FROM CHECKING THE SLOPE
        actual_y = natural_log_current_list
        predicted_y = slope * voltage_without_rs_list + intercept
        mse = np.mean((actual_y - predicted_y) ** 2)

        # ADD THE APPROPRIATE VALUES TO EACH LIST
        potential_regression_slope_list = np.append(potential_regression_slope_list, slope)
        potential_regresson_intercept_list = np.append(potential_regresson_intercept_list, intercept)
        potential_regression_mse_list = np.append(potential_regression_mse_list, mse)

    # SEARCH FOR THE BEST (LOWEST) MSE - THIS IS THE BEST GUESS RS - AND GET ITS VALUE AND INDEX
    best_mse = np.min(potential_regression_mse_list)
    best_mse_index = np.argmin(potential_regression_mse_list)

    # THE BEST SLOPE AND INTERCEPT (USED TO CALCULATE N AND IS) ARE AT THE SAME INDEX
    best_slope = potential_regression_slope_list[best_mse_index]
    best_intercept = potential_regresson_intercept_list[best_mse_index]

    # CALCULATE ALL THE APPROPRIATE VALUES - METHOD TAKEN FROM LABVIEW
    ideality = (39 / best_slope)
    saturation_current = np.exp(best_intercept)
    series_resistance = potential_rs_list[best_mse_index]
    mean_squared_error = best_mse
    r_squared_error = 1.0 - (mean_squared_error / natural_log_current_variance)

    # GET ALL HYSTERESIS VALUES AND CALCULATING THE BASIC STATISTICAL VALUES
    hysteresis_list_mv = []
    for voltage_up, voltage_down in zip(voltage_up_list, voltage_down_list):
        hysteresis_value = np.abs(voltage_up - voltage_down) * 1000
        hysteresis_list_mv.append(hysteresis_value)

    hysteresis_np_array_mv = np.array(hysteresis_list_mv)

    hysteresis_mean = np.mean(hysteresis_np_array_mv)
    hysteresis_minimum = np.min(hysteresis_np_array_mv)
    hysteresis_maximum = np.max(hysteresis_np_array_mv)
    hysteresis_standard_deviation = np.std(hysteresis_np_array_mv)

    # GET THE MAX CURRENT IN A FEW DIFFERENT WAYS
    max_current_string = f"{abs(current_list[-1]):e}"
    max_current_multiplier = int(max_current_string[0])
    max_current_value = float(current_list[-1])


    # THE "LANDMARK" CURRENT/VOLTAGE VALUES WHICH MICROA USES TO VALIDATE DIODES
    landmark_current_values = [max_current_multiplier * 1E-7, max_current_multiplier * 1E-6, max_current_multiplier * 1E-5, 
                                max_current_multiplier * 1E-4, max_current_multiplier * 1E-3, max_current_value, max_current_value / 10, max_current_value / 100]
    landmark_voltage_values = []

    # CHECKING FOR EACH VALUE
    for current in landmark_current_values:
        close_enough = np.isclose(current_list, current, rtol=1e-05, atol=1e-08)
        landmark_current_index = np.where(close_enough)[0]
        landmark_voltage_value = average_voltage_list[landmark_current_index]
        landmark_voltage_values = np.append(landmark_voltage_values, landmark_voltage_value)

    # FILLING IN THE LANDMARK VALUES
    # M is your max "multiplier" (as in 1, 2, 3, 4, or 5)
    delta_v1 = landmark_voltage_values[4] - landmark_voltage_values[3] # M00uA to MmA
    delta_v2 = landmark_voltage_values[3] - landmark_voltage_values[2] # M0uA to M00uA
    delta_v3 = landmark_voltage_values[2] - landmark_voltage_values[1] # MuA to M0uA
    delta_v4 = landmark_voltage_values[5] - landmark_voltage_values[6] # Max / 10 to Max
    delta_v5 = landmark_voltage_values[6] - landmark_voltage_values[7] # Max / 100 to Max / 10

    rs_4 = (delta_v1 - delta_v3) / (1E-3 - 1E-4)
    rs_1 = (delta_v1 - delta_v2) / (1E-3 - 1E-4)
    rs_3 = (delta_v4 - delta_v5) / (landmark_current_values[5] - landmark_current_values[6])

    # CONVERT THE SOURCE/MEASURE LISTS BACK TO THEIR UNITS AND CONVERTING TO STRINGS FOR USE LATER
    current_list_ma = [f"{current * 1E6:.6f}" for current in current_list]
    voltage_up_mv = [f"{voltage_up * 1E6:.6f}" for voltage_up in voltage_up_list]
    voltage_down_mv = [f"{voltage_down * 1E6:.6f}" for voltage_down in voltage_down_list]
    
    iv_parameter_dict = {
        'n (ideality)': ideality,
        'Is': f"{saturation_current:6e}",
        'Rs': series_resistance,
        'Rs_1': rs_1,
        'Rs 3pt': rs_3,
        'Rs_4pt': rs_4,
        'Mean Square Error': f"{mean_squared_error:6e}",
        'R^2 Error': r_squared_error,
        'Hysteresis SD (mV)': hysteresis_standard_deviation,
        'Hysteresis Mean (mV)': hysteresis_mean,
        'Hysteresis Max (mV)': hysteresis_maximum,
        'Hysteresis Min (mV)': hysteresis_minimum,
        'dV1': delta_v1,
        'dV2': delta_v2,
        'dV3': delta_v3,
        'dV4': delta_v4,
        'dV5': delta_v5,
        'mV @ Imax': landmark_voltage_values[5],
        'mV @ Imax/10': landmark_voltage_values[6],
        'mV @ Imax/100': landmark_voltage_values[7],
        f"mV @ {max_current_multiplier}mA": landmark_voltage_values[4],
        f"mV @ {max_current_multiplier}00uA": landmark_voltage_values[3],
        f"mV @ {max_current_multiplier}0uA": landmark_voltage_values[2],
        f"mV @ {max_current_multiplier}uA": landmark_voltage_values[1],
        f"mV @ {max_current_multiplier}00nA": landmark_voltage_values[0],
        'I (uA)': current_list_ma,
        'Vup (mV)': voltage_up_mv,
        'Vdown (mV)': voltage_down_mv,
        'Imax': max_current_multiplier,
        'Points/Decade': points_per_decade,
        'Polarity': polarity_symbol,
    }

    # CONVERT THESE ANNOYING/NASTY NP.FLOAT64 TO REGULAR FLOATS AND STRING FORMAT THEM
    for key, value in iv_parameter_dict.items():
        if isinstance(value, np.float64):
            converted_number = round(float(value), 6)
            formatted_number = f"{converted_number:.6f}"
            iv_parameter_dict[key] = formatted_number

    return(iv_parameter_dict)


def calculate_heat_parameters(heat_current_list, heat_voltage_list, ideality):
    temperature_list = []
    cold_voltages_strings = heat_voltage_list[0:10]
    cold_voltages = [float(voltage) for voltage in cold_voltages_strings]
    average_cold_voltage = statistics.mean(cold_voltages)

    for current, voltage in zip(heat_current_list[-100:], heat_voltage_list[-100:]):
        current = float(current)
        voltage = float(voltage)

        strange_temperature_value = abs(voltage - average_cold_voltage) * 849 / ideality + 25
        temperature_list.append(strange_temperature_value)

    return temperature_list

def get_reverse_breakdown_values(reverse_current_list, reverse_voltage_list):
    reverse_breakdown_max_current = abs(float(reverse_current_list[-1]))
    reverse_breakdown_max_voltage = abs(float(reverse_voltage_list[-1]))

    return reverse_breakdown_max_current, reverse_breakdown_max_voltage

def get_polarity(polarity_current_list):
    first_current_abs_value = abs(float(polarity_current_list[0]))
    last_current_abs_value = abs(float(polarity_current_list[-1]))

    if (first_current_abs_value > last_current_abs_value) and (first_current_abs_value / last_current_abs_value > 5):
        polarity = '-'
    elif (last_current_abs_value > first_current_abs_value) and (last_current_abs_value / first_current_abs_value > 5):
        polarity = '+'
    else:
        polarity = 'bidirectional'

    return polarity




# class IV_curve():
# 	def __init__(self, IV_source_up, IV_measure_up, IV_measure_down, Reverse_Breakdown_source='', Reverse_Breakdown_measure='', Polarity_Sweep_source='', Polarity_Sweep_measure='', Heat_Test_source='', Heat_Test_measure=''):
# 		"""
# 		IV curve properties

# 		Takes either lists (when pulling data from iv files) or strings (when pulling data from SMU) for IV_source_up, IV_measure_up, IV_measure_down

# 		Currents are as entered into labview sweep parameter ((1-5)E-9 to (1-5)E-3) from SMU
# 		Voltages are read directly as 1 ... 0.1 ... 0.01 ... etc. from SMU

# 		When cast using float() the currents will be in Amps and the voltages in Volts when pulling directly from SMU strings.

# 		Note that when pulling data from IV files, the voltages are in mV and the currents are in uA. This init function converts them to Volts and Amps for postprocessing.

# 		Returns
# 		-------
# 		None.
# 		"""

# 		is_list = isinstance(IV_source_up, list)
# 		self.IV_Iup = []

# 		if is_list:
# 			for I in IV_source_up:
# 				self.IV_Iup.append(float(I)/1E6) #from .iv file, convert to Amps
# 		else:
# 			for I in IV_source_up.replace('\r', '').replace('\n', '').split(','):
# 				self.IV_Iup.append(float(I))
				
# 		self.IV_Iup = list(map(abs, self.IV_Iup))

# 		is_list = isinstance(IV_measure_up, list)
# 		self.IV_Vup = []

# 		if is_list:
# 			for V in IV_measure_up:
# 				self.IV_Vup.append(float(V)/1E3) #from .iv file, convert to Volts
# 		else:
# 			for V in IV_measure_up.replace('\r', '').replace('\n', '').split(','):
# 				self.IV_Vup.append(float(V))
				
# 		self.IV_Vup = list(map(abs, self.IV_Vup))

# 		is_list = isinstance(IV_measure_down, list)
# 		self.IV_Vdown = []

# 		if is_list:
# 			for V in IV_measure_down:
# 				self.IV_Vdown.append(float(V)/1E3) #from .iv file, convert to Volts
# 		else:
# 			for V in IV_measure_down.replace('\r', '').replace('\n', '').split(','):
# 				self.IV_Vdown.append(float(V))
# 			self.IV_Vdown.reverse() #Only needed for SMU output. .iv file data formatted in the correct order.
			
# 		self.IV_Vdown = list(map(abs, self.IV_Vdown))

# 		if len(self.IV_Iup) == 21:
# 			self.points_per_decade = '5'
# 		elif len(self.IV_Iup) == 41:
# 			self.points_per_decade = '10'
# 		elif len(self.IV_Iup) == 101:
# 			self.points_per_decade = '25'
# 		elif len(self.IV_Iup) == 201:
# 			self.points_per_decade = '50'

# 		self.IV_Vavg = []
# 		for Vup, Vdown in zip(self.IV_Vup, self.IV_Vdown):
# 			self.IV_Vavg.append((Vup + Vdown)/ 2)

# 		if Reverse_Breakdown_source == '':
# 			self.I_reverse_breakdown = '0.0'
# 		else:
# 			self.I_reverse_breakdown = abs(float(Reverse_Breakdown_source.replace('\r', '').replace('\n', '').split(',')[-1]))
# 			#last value of reverse breakdown current list

# 		if Reverse_Breakdown_measure == '':
# 			self.V_reverse_breakdown  = '0.0'
# 		else:
# 			self.V_reverse_breakdown = abs(float(Reverse_Breakdown_measure.replace('\r', '').replace('\n', '').split(',')[-1]))
# 			#last value of reverse breakdown voltage list

# 		self.V_polarity_sweep = Polarity_Sweep_source.replace('\r', '').replace('\n', '').split(',') #haven't written any functions to use this yet
# 		self.I_polarity_sweep = Polarity_Sweep_measure.replace('\r', '').replace('\n', '').split(',') #haven't written any functions to use this yet

# 		if Heat_Test_measure != '' and Heat_Test_source != '':
# 			self.heat_test_currents = []
# 			self.heat_test_voltages = []
# 			for current in Heat_Test_source.replace('\r', '').replace('\n', '').split(','):
# 				self.heat_test_currents.append(float(current))
# 			for voltage in Heat_Test_measure.replace('\r', '').replace('\n', '').split(','):
# 				self.heat_test_voltages.append(float(voltage))

# 	def calc_IV_parameters(self, T=293):
# 		"""
# 		Calculate IV parameters

# 		Returns
# 		-------

# 		"""
		
# 		VT = k*T/e

# 		Rst = np.linspace(.1, 100, 10000)

# 		data = {
# 			"Vavg" : self.IV_Vavg,
# 			"I" : self.IV_Iup,
# 			"Vup" : self.IV_Vup,
# 			"Vdown" : self.IV_Vdown
# 		}

# 		df = pd.DataFrame(data)

# 		logI = np.log(np.abs(df["I"].values))
# 		Vavg = np.abs(df["Vavg"].values)
# 		I = np.abs(df["I"].values)

# 		V_diode = Vavg[None, :] - Rst[:, None] * I[None, :] #Replaces previous for loop calculating over every value

# 		x_mean = V_diode.mean(axis=1)
# 		y_mean = logI.mean()

# 		x_centered = V_diode - x_mean[:,None]
# 		y_centered = logI - y_mean

# 		cov_xy = np.sum(x_centered * y_centered, axis=1)
# 		var_x = np.sum(x_centered**2, axis=1)
# 		m = cov_xy/var_x

# 		b = y_mean - m * x_mean

# 		y_predicted = m[:, None] * V_diode + b[:, None]

# 		residuals = np.sum((logI - y_predicted)**2, axis=1)

# 		ss_total = np.sum((logI - y_mean)**2)
		
# 		R_squared_error = 1 - residuals / ss_total

# 		min_index = np.argmin(residuals)

# 		m_best_fit = m[min_index]
# 		y0_best_fit = b[min_index]

# 		self.mse = (residuals / len(logI))[min_index]
# 		self.Rs = Rst[min_index]
# 		self.R_sqr = R_squared_error[min_index]
# 		self.eta = 1/(m_best_fit*VT)
# 		self.Is = np.exp(y0_best_fit)

# 		df.loc[:,"Hysteresis"] = np.abs(df["Vup"]*1000 - df["Vdown"]*1000) #in mV
		

# 		self.hys_STD = df["Hysteresis"].std(ddof=0)
# 		self.hys_mean = df["Hysteresis"].mean()
# 		self.hys_max = df["Hysteresis"].max()
# 		self.hys_min = df["Hysteresis"].min()
		
# 		if f"{self.IV_Iup[-1]:E}"[0:1] not in ['1', '2', '3', '4', '5']:
# 			self.source_polarity = '-'
# 			current_display = f"{self.IV_Iup[-1]:E}"[1:2]
# 		else:
# 			self.source_polarity = '+'
# 			current_display = f"{self.IV_Iup[-1]:E}"[0:1]

# 		Ipts = np.array([int(current_display) * 0.1E-6, int(current_display) * 1E-6, int(current_display) * 10E-6, 
# 						int(current_display) * 100E-6, int(current_display) * 1000E-6, df["I"].max(), df["I"].max()/10, df["I"].max()/100])

# 		self.dfIpts = pd.DataFrame()
# 		self.dfIpts["I"] = Ipts

# 		self.dfIpts["V"] = np.interp(self.dfIpts["I"], df["I"], df["Vavg"])

# 		self.dv1 = self.dfIpts.loc[4] - self.dfIpts.loc[3] #dV1 for I from 100uA to 1000uA
# 		self.dv2 = self.dfIpts.loc[3] - self.dfIpts.loc[2] #dV2 for I from 10uA to 100uA
# 		self.dv3 = self.dfIpts.loc[2] - self.dfIpts.loc[1] #dV3 for I from 1uA to 10 uA
# 		self.dv4 = self.dfIpts.loc[5] - self.dfIpts.loc[6] #dV4 for I from Imax/10 to Imax
# 		self.dv5 = self.dfIpts.loc[6] - self.dfIpts.loc[7] #dV5 for I from Imax/100 to Imax/10

# 		self.Rs_1 = (self.dv1["V"] - self.dv2["V"]) / (self.dv1["I"])
# 		self.Rs_3pt = (self.dv4["V"] - self.dv5["V"]) / (self.dv4["I"])
# 		self.Rs_4pt = (self.dv1["V"] - self.dv3["V"]) / (self.dv1["I"])

# 		I_uA = []

# 		for current in self.IV_Iup:
# 			I_uA.append(f"{(current * 1E6):.6f}") #Convert current values to microamps and truncate @ 6 decimal places, preventing scientific notation

# 		Vdown_mV = []

# 		for voltage in self.IV_Vdown:
# 			Vdown_mV.append(f"{(voltage * 1E3):.6f}") #Convert voltage values to millivolts and truncate @ 6 decimals places, preventing scientific notation

# 		Vup_mV = []

# 		for voltage in self.IV_Vup:
# 			Vup_mV.append(f"{(voltage * 1E3):.6f}") #Convert voltage values to millivolts and truncate @ 6 decimals places, preventing scientific notation
		
# 		self.var_dict = {'n (ideality)': f"{self.eta:.6f}", 
# 						'Is': f"{self.Is:.6e}",
# 						'Rs': f"{self.Rs:.6f}",
# 						'Rs_1': f"{self.Rs_1:.6f}",
# 						'Rs 3pt': f"{self.Rs_3pt:.6f}",
# 						'Rs_4pt': f"{self.Rs_4pt:.6f}",
# 						'Mean Square Error': f"{self.mse:.6e}", #previously str(dfr["Mean Square Error"].loc[min_index])
# 						'R^2 Error': f"{self.R_sqr:.6f}",
# 						'Polarity': self.source_polarity,
# 						'Hysteresis SD (mV)': f"{self.hys_STD:.6f}",
# 						'Hysteresis Mean (mV)': f"{self.hys_mean:.6f}",
# 						'Hysteresis Max (mV)': f"{self.hys_max:.6f}",
# 						'Hysteresis Min (mV)': f"{self.hys_min:.6f}",
# 						'Reverse Current (uA)': f"{float(self.I_reverse_breakdown)*1E6:.6f}",
# 						'Reverse Voltage (V)': f"{float(self.V_reverse_breakdown):.6f}",
# 						'dV1': f"{self.dv1['V']:.6f}",
# 						'dV2': f"{self.dv2['V']:.6f}",
# 						'dV3': f"{self.dv3['V']:.6f}",
# 						'dV4': f"{self.dv4['V']:.6f}",
# 						'dV5': f"{self.dv5['V']:.6f}",
# 						'mV @ Imax': f"{self.dfIpts['V'].loc[5]:.6f}",
# 						'mV @ Imax/10': f"{self.dfIpts['V'].loc[6]:.6f}",
# 						'mV @ Imax/100': f"{self.dfIpts['V'].loc[7]:.6f}",
# 						f'mV @ {current_display}mA': f"{self.dfIpts['V'].loc[4]:.6f}",
# 						f'mV @ {current_display}00uA': f"{self.dfIpts['V'].loc[3]:.6f}",
# 						f'mV @ {current_display}0uA': f"{self.dfIpts['V'].loc[2]:.6f}",
# 						f'mV @ {current_display}uA': f"{self.dfIpts['V'].loc[1]:.6f}",
# 						f'mV @ {current_display}00nA': f"{self.dfIpts['V'].loc[0]:.6f}",
# 						'Points/Decade': self.points_per_decade,
# 						'I (uA)': I_uA,
# 						'Vup (mV)': Vup_mV,
# 						'Vdown (mV)': Vdown_mV,
# 						'Imax': current_display}
		
		
# 		print("Postprocessing finished.")
		
# 		return self.var_dict

# 	def calc_heat_parameters(self, heat_test_currents, heat_test_voltages, n):
# 		T = []
# 		cold_voltages_strings = heat_test_voltages[0:10]
# 		cold_voltages = [float(voltage) for voltage in cold_voltages_strings]
# 		average_cold_voltage = statistics.mean(cold_voltages)

# 		for current, voltage in zip(heat_test_currents[-100:], heat_test_voltages[-100:]):
# 			current = float(current)
# 			voltage = float(voltage)

# 			strange_temperature = abs(voltage - average_cold_voltage) * 849 / n + 25
# 			T.append(strange_temperature)
# 		return T
			
# 	def find_polarity(self):
# 		first_current_abs_value = abs(float(self.I_polarity_sweep[0]))
# 		last_current_abs_value = abs(float(self.I_polarity_sweep[-1]))

# 		if (first_current_abs_value > last_current_abs_value) and (first_current_abs_value / last_current_abs_value > 5):
# 			polarity = '-'
# 		elif (last_current_abs_value > first_current_abs_value) and (last_current_abs_value / first_current_abs_value > 5):
# 			polarity = '+'
# 		else:
# 			polarity = 'bidirectional'
# 		return polarity