import numpy as np
import pandas as pd
from scipy.stats import linregress
from scipy.constants import e,k
import time

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
        start_time = time.time()
        is_list = isinstance(IV_source_up, list)
        self.IV_Iup = []

        if is_list:
            for I in IV_source_up:
                self.IV_Iup.append(float(I)/1E6) #from .iv file, convert to Amps
        else:
            for I in IV_source_up.replace(r'\r', '').replace(r'\n', '').split(','):
                self.IV_Iup.append(float(I))

        is_list = isinstance(IV_measure_up, list)
        self.IV_Vup = []

        if is_list:
            for V in IV_measure_up:
                self.IV_Vup.append(float(V)/1E3) #from .iv file, convert to Volts
        else:
            for V in IV_measure_up.replace(r'\r', '').replace(r'\n', '').split(','):
                self.IV_Vup.append(float(V))

        is_list = isinstance(IV_measure_down, list)
        self.IV_Vdown = []

        if is_list:
            for V in IV_measure_down:
                self.IV_Vdown.append(float(V)/1E3) #from .iv file, convert to Volts
        else:
            for V in IV_measure_down.replace(r'\r', '').replace(r'\n', '').split(','):
                self.IV_Vdown.append(float(V))
            self.IV_Vdown.reverse() #Only needed for SMU output. .iv file data formatted in the correct order.


        self.IV_Vavg = []
        for Vup, Vdown in zip(self.IV_Vup, self.IV_Vdown):
            self.IV_Vavg.append((Vup + Vdown)/ 2)

        if Reverse_Breakdown_source == '':
            self.I_reverse_breakdown = '0.0'
        else:
            self.I_reverse_breakdown = Reverse_Breakdown_source.replace(r'\r', '').replace(r'\n', '').split(',')[len(Reverse_Breakdown_source.replace(r'\r', '').replace(r'\n', '').split(',')) - 1] 
            #last value of reverse breakdown current list

        if Reverse_Breakdown_measure == '':
            self.V_reverse_breakdown  = '0.0'
        else:
            self.V_reverse_breakdown = Reverse_Breakdown_measure.replace(r'\r', '').replace(r'\n', '').split(',')[len(Reverse_Breakdown_measure.replace(r'\r', '').replace(r'\n', '').split(',')) - 1] 
            #last value of reverse breakdown voltage list

        self.V_polarity_sweep = Polarity_Sweep_source.replace(r'\r', '').replace(r'\n', '').split(',') #haven't written any functions to use this yet
        self.I_polarity_sweep = Polarity_Sweep_measure.replace(r'\r', '').replace(r'\n', '').split(',') #haven't written any functions to use this yet
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"IV curve initialized in {elapsed_time:.2f} seconds.")

    def calc_IV_parameters(self, T=293):
        """
        Calculate IV parameters

        Returns
        -------

        """
        start_time = time.time()
        VT = k*T/e

        rsweep = [] #To hold a dictionary of IV parameters for each trial resistance in Rst
        Rst = np.linspace(.1, 100, 10000)

        data = {
            "Vavg" : self.IV_Vavg,
            "I" : self.IV_Iup,
            "Vup" : self.IV_Vup,
            "Vdown" : self.IV_Vdown
        }

        df = pd.DataFrame(data)
        
        for R in Rst:
            V_diode = df["Vavg"] - df["I"] * R

            (pfit, resid, _, _, _) = np.polyfit(V_diode, np.log(df["I"]), 1, full=True)

            p = np.poly1d(pfit)

            mse = np.mean((np.log(df["I"]) - p(V_diode))**2)

            _, _, r_value, _, _ = linregress(V_diode, np.log(df["I"]))

            rsweep.append({"Rs":R, "Residual Error":resid[0], "R_sqr":r_value**2, "Mean Square Error":mse, "Fit":pfit})
        
        dfr = pd.DataFrame(rsweep)

        min_index = dfr["Residual Error"].idxmin()

        m = dfr.loc[min_index].Fit[0]
        y0 = dfr.loc[min_index].Fit[1]

        self.Rs = dfr["Rs"].loc[min_index]

        self.R_sqr = dfr["R_sqr"].loc[min_index]

        self.eta = 1/(m*VT)

        self.Is = np.exp(y0)

        df.loc[:,"Hysteresis"] = np.abs(df["Vup"]*1000 - df["Vdown"]*1000) #in mV

        self.hys_STD = df["Hysteresis"].std(ddof=0)
        self.hys_mean = df["Hysteresis"].mean()
        self.hys_max = df["Hysteresis"].max()
        self.hys_min = df["Hysteresis"].min()

        Ipts = np.array([0.1E-6, 1E-6, 10E-6, 100E-6, 1000E-6, df["I"].max(), df["I"].max()/10, df["I"].max()/100])

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

        self.var_dict = {'n (ideality)': str(self.eta), 
                         'Is': str(self.Is),
                         'Rs': str(self.Rs),
                         'Rs_1': str(self.Rs_1),
                         'Rs 3pt': str(self.Rs_3pt),
                         'Rs_4pt': str(self.Rs_4pt),
                         'Mean Square Error': str(dfr["Mean Square Error"].loc[min_index]),
                         'R^2 Error': str(self.R_sqr),
                         'Polarity': 'The plus or the minus',
                         'Hysteresis SD (mV)': str(self.hys_STD),
                         'Hysteresis Mean (mV)': str(self.hys_mean),
                         'Hysteresis Max (mV)': str(self.hys_max),
                         'Hysteresis Min (mV)': str(self.hys_min),
                         'Reverse Current (uA)': str(float(self.I_reverse_breakdown)/1E6),
                         'Reverse Voltage(V)': str(self.V_reverse_breakdown),
                         'dV1': str(self.dv1["V"]),
                         'dV2': str(self.dv2["V"]),
                         'dV3': str(self.dv3["V"]),
                         'dV4': str(self.dv4["V"]),
                         'dV5': str(self.dv5["V"]),
                         'mV @ Imax': str(self.dfIpts["V"].loc[5]),
                         'mV @ Imax/10': str(self.dfIpts["V"].loc[6]),
                         'mV @ Imax/100': str(self.dfIpts["V"].loc[7]),
                         'mV @ 1mA': str(self.dfIpts["V"].loc[4]),
                         'mV @ 100uA': str(self.dfIpts["V"].loc[3]),
                         'mV @ 10uA': str(self.dfIpts["V"].loc[2]),
                         'mV @ 1uA': str(self.dfIpts["V"].loc[1]),
                         'mV @ 100nA': str(self.dfIpts["V"].loc[0]),
                         'Points/Decade': 'pull it from the sweep settings'}
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"IV parameters calculated in {elapsed_time:.2f} seconds.")

        return self.var_dict

