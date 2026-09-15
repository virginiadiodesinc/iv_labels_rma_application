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
    print("current_list: ", current_list)
    print("voltage_up_list: ", voltage_up_list)
    print("voltage_down_list: ", voltage_down_list)
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
        'Is': f"{saturation_current:2e}",
        'Rs': series_resistance,
        'Rs_1': rs_1,
        'Rs 3pt': rs_3,
        'Rs_4pt': rs_4,
        'Mean Square Error': f"{mean_squared_error:2e}",
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

def calculate_all_parameters(current_list, voltage_up_list, voltage_down_list, 
                             heat_current_list=None, heat_voltage_list=None,
                             reverse_current_list=None, reverse_voltage_list=None):
    parameters_dict = calculate_iv_parameters(current_list, voltage_up_list, voltage_down_list)

    if heat_current_list and heat_voltage_list:
        temperature_list = calculate_heat_parameters(heat_current_list, heat_voltage_list)
        parameters_dict["temperature_list"] = temperature_list

    if reverse_current_list and reverse_voltage_list:
        max_reverse_current, max_reverse_voltage = get_reverse_breakdown_values(reverse_current_list, reverse_voltage_list)
        parameters_dict["reverse_current"] = max_reverse_current
        parameters_dict["reverse_voltage"] = max_reverse_voltage

    return parameters_dict
