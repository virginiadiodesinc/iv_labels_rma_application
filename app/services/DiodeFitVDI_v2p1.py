# -*- coding: utf-8 -*-
"""
Created on Wed Sep  5 10:42:46 2018

@author: treck
"""

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from scipy.constants import e, k
from scipy.stats import linregress
from scipy.optimize import root

def readIVfile(fname):
    with open(fname,mode='r') as fin:
        lines = fin.readlines()
    
    srow = [nn for nn,l in enumerate(lines) if 'voltage up' in l.lower()]
    prow = [nn for nn,l in enumerate(lines) if 'polarity' in l.lower()]
    rcrow = [nn for nn,l in enumerate(lines) if 'reverse current' in l.lower()]
    rvrow = [nn for nn,l in enumerate(lines) if 'reverse voltage' in l.lower()]

    # read some stuff
    name = lines[0].replace('\n','')
    date = lines[1].replace('\n','')  # Maybe make Datetime object?
    polarity = lines[prow[0]].split(': ')[1].strip('\n')
    revI = float(lines[rcrow[0]].split(': ')[1].strip('\n'))
    revV = float(lines[rvrow[0]].split(': ')[1].strip('\n'))

    # import the IV data
    dfiv = pd.read_csv(fname, delimiter='\t',skiprows=srow[0], header=0,
                     names=('Voltage Up (mV)','Voltage Down (mV)','Current (uA)'))
    
    return dfiv

def VtVdBal(Vd, Vt,Is,eta,Rs,VT):
    for vv in range(len(Vd)):
        if (Vd[vv] > Vt):
            Vd[vv] = -Vd
            
#    VdBal = eta*VT*np.log((Vt-Vd)/(Rs*Is)+1) - Vd
    VdBal = Rs*Is*(np.exp((Vd/(eta*VT)))-1) + Vd - Vt
    return(VdBal)

def Idiode(Vt, Is, eta, Rs, VT):
    if (len(Vt) == 1):
        Vdres = root(VtVdBal,Vt*0.9,(Vt,Is,eta,Rs,VT),method='hybr',tol=1e-6)
        Vd = Vdres.x[0]
    else:
        Vd = np.zeros(len(Vt))
        for vv in range(len(Vt)):
            Vdres = root(VtVdBal,Vt[vv]*0.9,(Vt[vv],Is,eta,Rs,VT),method='hybr',tol=1e-9)
            Vd[vv] = Vdres.x[0]
    
    Id = Is*(np.exp(Vd/(eta*VT)) - 1)
    return(Id)

class DiodeIV():
    
    def __init__(self, filename='', df=pd.DataFrame(), D=1e-6, T=293, vsweep='mean'):
        # IV data
        self.dfiv = pd.DataFrame()   
        
        self.vsweep = vsweep
       
        self.VT = k*T/e
        self.Arich = 8.6  # 1/(cm-K)^2 (Richardson's constant)
        
        # Anode size, for Cheung Analysis
        self.D = D      # m
        self.Aeff = np.pi*(D/2)**2   # m^2
        self.T = T  # K
        
        # Parameters
        # metadata
        self.name = ''
        self.date = ''  
        self.polarity = '+'
        self.revI = 0
        self.revV = 0
        
        # Fit results
        self.Rs = 0
        self.eta = 0         # Ideality
        self.Is = 0          # Saturation current
        self.Rsqr = 0
        
        # Cheung fit results
        self.eta2 = 0
        self.Rs2 = 0
        self.Rs3 = 0
        self.Is2 = 0
        self.Vbi = 0        
        
        # Hysteresis 
        self.hys_STD = 0     
        self.hys_mean = 0    
        self.hys_max = 0     
        self.hys_min = 0
        
        # Diode points
        self.dv1 = 0
        self.dv2 = 0
        self.dv3 = 0
        self.dv4 = 0
        self.dv5 = 0
        
        # extra Rs'
        self.rs_1 = 0
        self.rs_3pt = 0
        self.rs_4pt = 0     
        
        self.fitParams = {'Rs':self.Rs,
                          'Is':self.Is,
                          'eta':self.eta}
        
        if len(filename) > 0:   # read and IV fine
            self.readIVfile(filename)
        elif len(df) > 0:       # process dataframe in the style of IV datafile
            self.dfiv = df
        
        # do the fit
        self.calcIV()
        
        self.fitString = 'Rs: {:.1f} Ohm\nIsat: {:0.1e} A\neta: {:.2f}'.format(self.fitParams['Rs'],self.fitParams['Is'],self.fitParams['eta'])
        
    def readIVfile(self, fname):
        with open(fname,mode='r') as fin:
            lines = fin.readlines()
        
        srow = [nn for nn,l in enumerate(lines) if 'voltage up' in l.lower()]
        prow = [nn for nn,l in enumerate(lines) if 'polarity' in l.lower()]
        rcrow = [nn for nn,l in enumerate(lines) if 'reverse current' in l.lower()]
        rvrow = [nn for nn,l in enumerate(lines) if 'reverse voltage' in l.lower()]

        # read some stuff
        self.name = lines[0].replace('\n','')
        self.date = lines[1].replace('\n','')  # Maybe make Datetime object?
        self.polarity = lines[prow[0]].split(': ')[1].strip('\n')
        self.revI = float(lines[rcrow[0]].split(': ')[1].strip('\n'))
        self.revV = float(lines[rvrow[0]].split(': ')[1].strip('\n'))

        # import the IV data
        self.dfiv = pd.read_csv(fname, delimiter='\t',skiprows=srow[0], header=0,
                         names=('Voltage Up (mV)','Voltage Down (mV)','Current (uA)'))
        
        # Convert to Volt and Amps
        self.dfiv['Voltage Up (mV)'] = self.dfiv['Voltage Up (mV)'] * 1e-3
        self.dfiv['Voltage Down (mV)'] = self.dfiv['Voltage Down (mV)'] * 1e-3
        self.dfiv['Current (uA)'] = self.dfiv['Current (uA)'] * 1e-6
        
        self.dfiv = self.dfiv.rename(columns={'Voltage Up (mV)':'Voltage Up (V)',
                                               'Voltage Down (mV)':'Voltage Down (V)',
                                               'Current (uA)':'Current (A)'})
        
    def calcIV(self):
        # Adapted from DNK's Labview DiodeIV program
        # Neglects the '- 1' component of the diode equation
        # Sweeps Rs, fitting a line to (V-I*Rs,ln(I)) which should be linear
        # slope is proportional to eta
        # y-intercept is ln(Is)
        
        df = self.dfiv
        
        # convert to Volts and Amps and make mean voltage
        if self.vsweep == 'Up':
            df['V'] = df['Voltage Up (V)']
        elif self.vsweep == 'Down':
            df['V'] = df['Voltage Down (V)']        
        else:
            df['V'] = (df['Voltage Up (V)'] + df['Voltage Down (V)'])/(2)

        df['I'] = df['Current (A)']
                  
        Rst = np.linspace(.1,10000,1000)
        rsweep = []
        for R in Rst:    
            Vd = df['V'] - df['I']*R      # calculate the diode voltage 
            
            try:
                m, y0, r_value, _, _ = linregress(Vd, np.log(df['I']))
            except:
                return

            rsweep.append({'Rs':R, 'Rsqr':r_value**2, 'fit':(m, y0)})

        dfr = pd.DataFrame(rsweep)

        if dfr['Rsqr'].max() < 0.95:  # only fit the good ones
            return

        # Find Rs minum residual and pull the slope and y-intercept
        minidx = dfr['Rsqr'].idxmax()
        m = dfr.loc[minidx].fit[0]
        y0 = dfr.loc[minidx].fit[1]
        
        # Calculate diode parameters
        self.Rs = dfr['Rs'].loc[minidx]
        self.eta = 1/(m*self.VT)
        self.Is = np.exp(y0)
        self.Rsqr = dfr['Rsqr'].loc[minidx]
        
        # Calculate hysteresis 
        df['hys'] = np.abs(df['Voltage Up (V)'] - df['Voltage Down (V)'])           
        self.hys_STD = df['hys'].std(ddof=0)
        self.hys_mean = df['hys'].mean()
        self.hys_max = df['hys'].max()
        self.hys_min = df['hys'].min()
        
        # diode points of interest
        Ipts = np.array([0.1e-6, 1e-6, 10e-6, 100e-6, 1000e-6, 
                         df['Current (A)'].max(),
                         df['Current (A)'].max()/10,
                         df['Current (A)'].max()/100]) # A
        self.dfIpts = pd.DataFrame()
        self.dfIpts['I'] = Ipts
        self.dfIpts['V'] = np.interp(self.dfIpts['I'], df['Current (A)'], df['Voltage Up (V)'])
        
        # additional series resistance calcs
        self.dv1 = self.dfIpts.loc[4] - self.dfIpts.loc[3]
        self.dv2 = self.dfIpts.loc[3] - self.dfIpts.loc[2]
        self.dv3 = self.dfIpts.loc[2] - self.dfIpts.loc[1]
        self.dv4 = self.dfIpts.loc[5] - self.dfIpts.loc[6]
        self.dv5 = self.dfIpts.loc[6] - self.dfIpts.loc[7]
        
        self.rs_1 = (self.dv1-self.dv2) / (self.dv1['I'] / 1000)
        self.rs_3pt = (self.dv4-self.dv5) / (self.dv4['I'] / 1000)
        self.rs_4pt = (self.dv1-self.dv3) / (self.dv1['I'] / 1000)
    
        self.fitParams = {'Rs':self.Rs,
                          'Is':self.Is,
                          'eta':self.eta}
    
        self.CalcIVCheung()
        
        
    def CalcFit(self):
        outcols = ['Voltage Up (V)', 'Voltage Down (V)', 'Current (A)']
        dfout = self.dfiv[outcols].copy()
        dfout['Fit (A)'] = Idiode(self.dfiv['V'], self.Is, self.eta, self.Rs, self.VT)
        return(dfout)
    
    def CalcIVCheung(self):
        # From Cheung 1986
        # Extracts Built-in voltage based on IV and anode size
        
        self.dfiv['J'] = self.dfiv['I']/(self.Aeff/1e-8)  # A/cm^2
        self.dfiv['lnJ'] = np.log(self.dfiv['J'])

        v = self.dfiv['V'].values
        lnJ = self.dfiv['lnJ'].values
        dv = v[1:]-v[:-1]
        dlnJ = lnJ[1:]-lnJ[:-1]
        
        try:
            (pfit, _, _, _, _,) =  np.polyfit(self.dfiv['J'].values[:-1],  dv/dlnJ, 1, full=True)
        except:
            return

        self.eta2 = pfit[1]/self.VT
        self.Rs2 = pfit[0]/(self.Aeff/1e-8)

        self.dfiv['H'] = self.dfiv['V'] - pfit[1]*np.log(self.dfiv['J']/(self.Arich*self.T**2))

        ir = self.dfiv['J']>1e-11
        (pfit2, _, _, _, _,) =  np.polyfit(self.dfiv['J'].loc[ir].values, self.dfiv['H'].loc[ir], 1, full=True)
        
        self.Vbi = pfit2[1]/self.eta2
        self.Rs3 = pfit2[0]/(self.Aeff/1e-8)
        self.Is2 = (self.Aeff/1e-8) * self.Arich * self.T**2 * np.exp(-self.Vbi/self.VT)

        # p = np.poly1d(pfit2) 
        # plt.figure(104)
        # # plt.cla()
        # plt.plot(self.dfiv['J'], self.dfiv['H'])
        # plt.plot(self.dfiv['J'], p(self.dfiv['J']),'r:')
        # plt.xlabel('J (A/cm$^2$)')
        # plt.ylabel('H (volts)')
        

if __name__ == '__main__':
    fname = r'I:\VDI4.3\VDI4.3SHMG4_R7 B3-026 A4APED11.5FG1111 CirWR4.3SHM_REV_202005-CX1A-Z2.5X_Lot20251110 A#G4 + WR4.3R7 3-026 closed block +.iv'
    
    d = DiodeIV(filename = fname, D=1.6e-6)
    dfit = d.CalcFit()
    
    print('Standard Curve Fit')
    print('R1:   {:.1f} Ohms'.format(d.Rs))
    print('eta1: {:.2f}'.format(d.eta))
    print('Isat: {:.2e} A'.format(d.Is))
    print('Cheung Analysis')
    print('R3:   {:.1f} Ohms'.format(d.Rs3))
    print('eta2: {:.2f}'.format(d.eta2))
    print('Isat2: {:.2e} A'.format(d.Is2))  
    print('Vbi: {:.2f} V'.format(d.Vbi))
    
    

