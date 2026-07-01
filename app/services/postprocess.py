import numpy as np
import pandas as pd
from scipy.constants import e,k

class IV_curve():
    def __init__(self, IV_source_up, IV_measure_up, IV_measure_down, Reverse_Breakdown_source='', Reverse_Breakdown_measure='', Polarity_Sweep_source='', Polarity_Sweep_measure='',):
        """
        IV curve properties

        Takes either lists (when pulling data from iv files) or strings (when pulling data from SMU) for IV_source_up, IV_measure_up, IV_measure_down

        Currents are as entered into labview sweep parameter ((1-5)E-9 to (1-5)E-3) from SMU
        Voltages are read directly as 1 ... 0.1 ... 0.01 ... etc. from SMU

        When cast using float() the currents will be in Amps and the voltages in Volts when pulling directly from SMU strings.

        Note that when pulling data from IV files, the voltages are in mV and the currents are in uA. This init function converts them to Volts and Amps for postprocessing.

        Returns
        -------
        None.
        """

        is_list = isinstance(IV_source_up, list)
        self.IV_Iup = []

        if is_list:
            for I in IV_source_up:
                self.IV_Iup.append(float(I)/1E6) #from .iv file, convert to Amps
        else:
            for I in IV_source_up.replace('\r', '').replace('\n', '').split(','):
                self.IV_Iup.append(float(I))
                
        self.IV_Iup = list(map(abs, self.IV_Iup))

        is_list = isinstance(IV_measure_up, list)
        self.IV_Vup = []

        if is_list:
            for V in IV_measure_up:
                self.IV_Vup.append(float(V)/1E3) #from .iv file, convert to Volts
        else:
            for V in IV_measure_up.replace('\r', '').replace('\n', '').split(','):
                self.IV_Vup.append(float(V))
                
        self.IV_Vup = list(map(abs, self.IV_Vup))

        is_list = isinstance(IV_measure_down, list)
        self.IV_Vdown = []

        if is_list:
            for V in IV_measure_down:
                self.IV_Vdown.append(float(V)/1E3) #from .iv file, convert to Volts
        else:
            for V in IV_measure_down.replace('\r', '').replace('\n', '').split(','):
                self.IV_Vdown.append(float(V))
            self.IV_Vdown.reverse() #Only needed for SMU output. .iv file data formatted in the correct order.
            
        self.IV_Vdown = list(map(abs, self.IV_Vdown))

        if len(self.IV_Iup) == 21:
            self.points_per_decade = '5'
        elif len(self.IV_Iup) == 41:
            self.points_per_decade = '10'
        elif len(self.IV_Iup) == 101:
            self.points_per_decade = '25'
        elif len(self.IV_Iup) == 201:
            self.points_per_decade = '50'

        self.IV_Vavg = []
        for Vup, Vdown in zip(self.IV_Vup, self.IV_Vdown):
            self.IV_Vavg.append((Vup + Vdown)/ 2)

        if Reverse_Breakdown_source == '':
            self.I_reverse_breakdown = '0.0'
        else:
            self.I_reverse_breakdown = abs(float(Reverse_Breakdown_source.replace('\r', '').replace('\n', '').split(',')[0]))
            #last value of reverse breakdown current list

        if Reverse_Breakdown_measure == '':
            self.V_reverse_breakdown  = '0.0'
        else:
            self.V_reverse_breakdown = abs(float(Reverse_Breakdown_measure.replace(r'\r', '').replace('\n', '').split(',')[len(Reverse_Breakdown_measure.replace('\r', '').replace('\n', '').split(',')) - 1]))
            #last value of reverse breakdown voltage list

        self.V_polarity_sweep = Polarity_Sweep_source.replace('\r', '').replace('\n', '').split(',') #haven't written any functions to use this yet
        self.I_polarity_sweep = Polarity_Sweep_measure.replace('\r', '').replace('\n', '').split(',') #haven't written any functions to use this yet

    def calc_IV_parameters(self, T=293):
        """
        Calculate IV parameters

        Returns
        -------

        """
        
        VT = k*T/e

        Rst = np.linspace(.1, 100, 10000)

        data = {
            "Vavg" : self.IV_Vavg,
            "I" : self.IV_Iup,
            "Vup" : self.IV_Vup,
            "Vdown" : self.IV_Vdown
        }

        df = pd.DataFrame(data)

        logI = np.log(np.abs(df["I"].values))
        Vavg = np.abs(df["Vavg"].values)
        I = np.abs(df["I"].values)

        V_diode = Vavg[None, :] - Rst[:, None] * I[None, :] #Replaces previous for loop calculating over every value

        x_mean = V_diode.mean(axis=1)
        y_mean = logI.mean()

        x_centered = V_diode - x_mean[:,None]
        y_centered = logI - y_mean

        cov_xy = np.sum(x_centered * y_centered, axis=1)
        var_x = np.sum(x_centered**2, axis=1)
        m = cov_xy/var_x

        b = y_mean - m * x_mean

        y_predicted = m[:, None] * V_diode + b[:, None]

        residuals = np.sum((logI - y_predicted)**2, axis=1)

        ss_total = np.sum((logI - y_mean)**2)
        
        R_squared_error = 1 - residuals / ss_total

        min_index = np.argmin(residuals)

        m_best_fit = m[min_index]
        y0_best_fit = b[min_index]

        self.mse = (residuals / len(logI))[min_index]
        self.Rs = Rst[min_index]
        self.R_sqr = R_squared_error[min_index]
        self.eta = 1/(m_best_fit*VT)
        self.Is = np.exp(y0_best_fit)

        df.loc[:,"Hysteresis"] = np.abs(df["Vup"]*1000 - df["Vdown"]*1000) #in mV
        

        self.hys_STD = df["Hysteresis"].std(ddof=0)
        self.hys_mean = df["Hysteresis"].mean()
        self.hys_max = df["Hysteresis"].max()
        self.hys_min = df["Hysteresis"].min()
        
        if f"{self.IV_Iup[-1]:E}"[0:1] not in ['1', '2', '3', '4', '5']:
            self.source_polarity = '-'
            current_display = f"{self.IV_Iup[-1]:E}"[1:2]
        else:
            self.source_polarity = '+'
            current_display = f"{self.IV_Iup[-1]:E}"[0:1]

        Ipts = np.array([int(current_display) * 0.1E-6, int(current_display) * 1E-6, int(current_display) * 10E-6, 
                         int(current_display) * 100E-6, int(current_display) * 1000E-6, df["I"].max(), df["I"].max()/10, df["I"].max()/100])

        self.dfIpts = pd.DataFrame()
        self.dfIpts["I"] = Ipts

        self.dfIpts["V"] = np.interp(self.dfIpts["I"], df["I"], df["Vavg"])

        self.dv1 = self.dfIpts.loc[4] - self.dfIpts.loc[3] #dV1 for I from 100uA to 1000uA
        self.dv2 = self.dfIpts.loc[3] - self.dfIpts.loc[2] #dV2 for I from 10uA to 100uA
        self.dv3 = self.dfIpts.loc[2] - self.dfIpts.loc[1] #dV3 for I from 1uA to 10 uA
        self.dv4 = self.dfIpts.loc[5] - self.dfIpts.loc[6] #dV4 for I from Imax/10 to Imax
        self.dv5 = self.dfIpts.loc[6] - self.dfIpts.loc[7] #dV5 for I from Imax/100 to Imax/10

        self.Rs_1 = (self.dv1["V"] - self.dv2["V"]) / (self.dv1["I"])
        self.Rs_3pt = (self.dv4["V"] - self.dv5["V"]) / (self.dv4["I"])
        self.Rs_4pt = (self.dv1["V"] - self.dv3["V"]) / (self.dv1["I"])

        I_uA = []

        for current in self.IV_Iup:
            I_uA.append(f"{(current * 1E6):.6f}") #Convert current values to microamps and truncate @ 6 decimal places, preventing scientific notation

        Vdown_mV = []

        for voltage in self.IV_Vdown:
            Vdown_mV.append(f"{(voltage * 1E3):.6f}") #Convert voltage values to millivolts and truncate @ 6 decimals places, preventing scientific notation

        Vup_mV = []

        for voltage in self.IV_Vup:
            Vup_mV.append(f"{(voltage * 1E3):.6f}") #Convert voltage values to millivolts and truncate @ 6 decimals places, preventing scientific notation
        
        self.var_dict = {'n (ideality)': f"{self.eta:.6f}", 
                         'Is': f"{self.Is:.6e}",
                         'Rs': f"{self.Rs:.6f}",
                         'Rs_1': f"{self.Rs_1:.6f}",
                         'Rs 3pt': f"{self.Rs_3pt:.6f}",
                         'Rs_4pt': f"{self.Rs_4pt:.6f}",
                         'Mean Square Error': f"{self.mse:.6e}", #previously str(dfr["Mean Square Error"].loc[min_index])
                         'R^2 Error': f"{self.R_sqr:.6f}",
                         'Polarity': self.source_polarity,
                         'Hysteresis SD (mV)': f"{self.hys_STD:.6f}",
                         'Hysteresis Mean (mV)': f"{self.hys_mean:.6f}",
                         'Hysteresis Max (mV)': f"{self.hys_max:.6f}",
                         'Hysteresis Min (mV)': f"{self.hys_min:.6f}",
                         'Reverse Current (uA)': f"{float(self.I_reverse_breakdown)*1E6:.6f}",
                         'Reverse Voltage (V)': f"{float(self.V_reverse_breakdown):.6f}",
                         'dV1': f"{self.dv1['V']:.6f}",
                         'dV2': f"{self.dv2['V']:.6f}",
                         'dV3': f"{self.dv3['V']:.6f}",
                         'dV4': f"{self.dv4['V']:.6f}",
                         'dV5': f"{self.dv5['V']:.6f}",
                         'mV @ Imax': f"{self.dfIpts['V'].loc[5]:.6f}",
                         'mV @ Imax/10': f"{self.dfIpts['V'].loc[6]:.6f}",
                         'mV @ Imax/100': f"{self.dfIpts['V'].loc[7]:.6f}",
                         f'mV @ {current_display}mA': f"{self.dfIpts['V'].loc[4]:.6f}",
                         f'mV @ {current_display}00uA': f"{self.dfIpts['V'].loc[3]:.6f}",
                         f'mV @ {current_display}0uA': f"{self.dfIpts['V'].loc[2]:.6f}",
                         f'mV @ {current_display}uA': f"{self.dfIpts['V'].loc[1]:.6f}",
                         f'mV @ {current_display}00nA': f"{self.dfIpts['V'].loc[0]:.6f}",
                         'Points/Decade': self.points_per_decade,
                         'I (uA)': I_uA,
                         'Vup (mV)': Vup_mV,
                         'Vdown (mV)': Vdown_mV,
                         'Imax': current_display}
        
        
        print("Postprocessing finished.")
        
        return self.var_dict