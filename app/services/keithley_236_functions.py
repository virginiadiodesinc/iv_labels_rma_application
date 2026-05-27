import time
import pyvisa


# FUNCTION TO CHECK FOR REAL OR FAKE KEITHLEY
def get_SMU():
	"""Gets either a real SMU or a fake SMU
	
	This function tries to connect to a real SMU. 
	If it fails, it returns a Fake SMU which can tell you there's no Keithley connected

	@return SMU_K236() or Fake_SMU() (objects)
	"""
	smu = SMU_K236()
	if smu.connect():
		return smu
	else:
		return Fake_SMU()

# DUMMY SMU CLASS FOR USING APP WITHOUT KEITHLEY
class Fake_SMU():
	def update_settings(self, **kwargs):
		return kwargs
	def takeIV(self):
		raise RuntimeError("No Keithley connected")

class SMU_K236():

	def __init__(self, address=16):
		"""
		SMU 236 object parameters.

		Returns
		-------
		None.
		"""
		self.address = address
		self.inst = None

		self.W_command = 'W1' #default delay on
		self.S_command = 'S1' #default integration time 'medium'
		self.P_command = 'P3' #default filter readings '8'
		self.L_command = 'L1.2,0' #default compliance voltage = 1.2V
		self.sign = '' #default polarity positive
		self.points = '0' #default 5 points per decade
		self.points_per_decade = 5 #default 5 points per decade - using this value to add to default sweep delay
		self.user_sweep_delay = '0' #default user sweep delay 0ms
		self.Imin = '100E-9' #default start current = 0.1uA
		self.Imax = '1E-3' #default end current = 1mA
		self.Q_command = 'Q2,'+self.sign+self.Imin+','+self.sign+self.Imax+','+self.points+',0,'+self.user_sweep_delay #logarithmic sweep, default maximum current 1mA, 5 points per decade, user sweep delay 0ms

		self.V_limit_polarity = '0.6' #default polarity sweep voltage limit = 0.6V
		self.voltage_steps = '0.1' #default polarity sweep voltage steps = 0.1V
		self.Q_command_polarity = 'Q1,-'+self.V_limit_polarity+','+self.V_limit_polarity+','+self.voltage_steps+',0,100' #linear sweep
		self.I_compliance_polarity = '1E-6' #default polarity sweep compliance current = 1uA
		self.L_command_polarity = 'L'+self.I_compliance_polarity+',0'

		self.Imin_reverse = '1E-6' #default reverse breakdown start current = 1uA
		self.V_compliance_reverse = '20' #default reverse breakdown compliance voltage = 20V
		self.L_command_reverse = 'L'+self.V_compliance_reverse+',0'
		self.sign_reverse = '-' #default polarity negative
		self.Q_command_reverse = 'Q2,'+self.sign_reverse+self.Imin_reverse+','+self.sign_reverse+'1E-3'+',0,0,0'

		self.instrument_delay = 0.1
		self.default_sweep_delay = .45

	def connect(self):
		try:
			rm = pyvisa.ResourceManager()
			gpib_address = f'GPIB0::{self.address}::INSTR'
			self.inst = rm.open_resource(gpib_address)
			return True
		except Exception as e:
			print("Keithley connection failed")
			self.inst
			return False

	def reset(self):
		"""
		Resets the SMU 236 to defaults.

		Returns
		-------
		None.
		"""
		self.inst.write('J0X')
		time.sleep(self.instrument_delay)

	# BASIC SETTINGS

	def set_default_delay(self, toggle):
		"""
		Toggles SMU 236 default delay: on , off
		Controls the enabling/ disabling of a fixed delay used to compensate for the instrument settling time when measuring resistive loads

		Returns
		-------
		None.
		"""
		if toggle == 'on':
			self.W_command = 'W1'
		elif toggle == 'off':
			self.W_command = 'W0'


	def set_filter(self, count):
		"""
		Set number of filter readings on SMU 236: off, 2, 4, 8, 16, 32.

		Returns
		-------
		None.
		"""
		if count == 'off':
			self.P_command = 'P0'
			self.filter_count = 1
		elif count == '2':
			self.P_command = 'P1'
			self.filter_count = 2
		elif count == '4':
			self.P_command = 'P2'
			self.filter_count = 4
		elif count == '8':
			self.P_command = 'P3'
			self.filter_count = 8
		elif count == '16':
			self.P_command = 'P4'
			self.filter_count = 16
		elif count == '32':
			self.P_command = 'P5'
			self.filter_count = 32

	def set_polarity(self, polarity):
		"""
		Set source current positive (+) or negative (-).

		Returns
		-------
		None.
		"""
		if polarity == '+':
			self.sign = ''
			self.Q_command = 'Q2,'+self.sign+self.Imin+','+self.sign+self.Imax+','+self.points+',0,'+self.user_sweep_delay


		elif polarity == '-':
			self.sign = '-'
			self.Q_command = 'Q2,'+self.sign+self.Imin+','+self.sign+self.Imax+','+self.points+',0,'+self.user_sweep_delay

	def set_compliance_voltage(self, Vmax):
		"""
		Set compliance voltage. I believe MicroA does not exceed Vmax = 4, but the limit can be set to whatever the correct value is.
		Compliance voltage changes in 0.1V increments, so compliance voltage value truncates to a minimum of 0.1 and to a max of 4.0 if out of range.

		Returns
		-------
		None.
		"""
		if 0.1 <= Vmax <= 4.0:
			self.L_command = 'L'+str(Vmax)+',0'
		elif Vmax < 0.1:
			self.L_command = 'L'+str(0.1)+',0'
		elif Vmax > 4.0:
			self.L_command = 'L'+str(4.0)+',0'
		

	def set_maximum_current(self, current):
		"""
		Set current range based on maximum current: 1mA, 2mA, 3mA, 4mA, 5mA

		Returns
		-------
		None.
		"""
		if current == '1mA':
			self.Imin = '100E-9'
			self.Imax = '1E-3'
			self.Q_command = 'Q2,'+self.sign+self.Imin+','+self.sign+self.Imax+','+self.points+',0,'+self.user_sweep_delay
		elif current == '2mA':
			self.Imin = '200E-9'
			self.Imax = '2E-3'
			self.Q_command = 'Q2,'+self.sign+self.Imin+','+self.sign+self.Imax+','+self.points+',0,'+self.user_sweep_delay
		elif current == '3mA':
			self.Imin = '300E-9'
			self.Imax = '3E-3'
			self.Q_command = 'Q2,'+self.sign+self.Imin+','+self.sign+self.Imax+','+self.points+',0,'+self.user_sweep_delay
		elif current == '4mA':
			self.Imin = '400E-9'
			self.Imax = '4E-3'
			self.Q_command = 'Q2,'+self.sign+self.Imin+','+self.sign+self.Imax+','+self.points+',0,'+self.user_sweep_delay
		elif current == '5mA':
			self.Imin = '500E-9'
			self.Imax = '5E-3'
			self.Q_command = 'Q2,'+self.sign+self.Imin+','+self.sign+self.Imax+','+self.points+',0,'+self.user_sweep_delay

	
	def set_polarity_sweep_voltage_steps(self, Vstep):
		"""
		Set diode IV polarity sweep voltage step

		Returns
		-------
		None.
		"""
		self.voltage_steps = Vstep
		self.Q_command_polarity = 'Q1,-'+self.V_limit+','+self.V_limit+','+self.voltage_steps+',0,100'

	
	def set_polarity_sweep_voltage_limit(self, Vlim):
		"""
		Set diode IV polarity sweep voltage limits

		Returns
		-------
		None.
		"""
		self.V_limit_polarity = Vlim
		self.Q_command_polarity = 'Q1,-'+self.V_limit_polarity+','+self.V_limit_polarity+','+self.voltage_steps+',0,100'

	def set_polarity_sweep_compliance_current(self, Imax):
		"""
		Set diode IV polarity sweep compliance current

		Returns
		-------
		None.
		"""
		self.I_compliance_polarity = Imax
		self.L_command_polarity = 'L'+self.I_compliance_polarity+',0'

	def takePolaritySweep(self):
		"""
		SMU 236 Diode IV Polarity Sweep Sequence

		Returns
		-------
		source_values: a list of voltage values forced across the diode.
		measure_values: a list of current values measured through the diode.
		"""
		self.reset() 

		self.inst.write('F0,1X') #Sources voltage, measures current (sweep)
		time.sleep(self.instrument_delay)

		print(self.L_command_polarity)
		self.inst.write(self.L_command_polarity+'X')
		time.sleep(self.instrument_delay)

		print(self.Q_command_polarity)
		self.inst.write(self.Q_command_polarity+'X')
		time.sleep(self.instrument_delay)

		self.inst.write('N1X') #Operate mode
		time.sleep(self.instrument_delay)
	
		self.inst.write('M2,0X') #Generate service request when sweep is finished and instrument is idle
		time.sleep(self.instrument_delay)

		self.inst.write('H0X') #Execute sweep
		time.sleep(1)

		self.inst.write('N0X') #Standby mode
		time.sleep(self.instrument_delay)

		source_values = self.inst.query("G1,2,2X") #Voltage values
		time.sleep(self.instrument_delay)
		measure_values = self.inst.query("G4,2,2X") #Current values
		time.sleep(self.instrument_delay)
		
		return source_values, measure_values
	
	def set_reverse_polarity(self):
		"""
		Set current polarity for reverse breakdown test.

		Returns
		-------
		None.
		"""
		if self.sign == '':
			self.sign_reverse = '-'
			self.Q_command_reverse = 'Q2,'+self.sign_reverse+self.Imin_reverse+','+self.sign_reverse+'1E-3'+',0,0,0'
		elif self.sign == '-':
			self.sign_reverse = ''
			self.Q_command_reverse = 'Q2,'+self.sign_reverse+self.Imin_reverse+','+self.sign_reverse+'1E-3'+',0,0,0'

	def set_reverse_polarity_end_current(self, Imax):
		"""
		Set end current for reverse breakdown test current ramp. Add an upper limit for the start current?

		Returns
		-------
		None.
		"""
		self.Imax_reverse = str(Imax) + 'E-6'
		self.Q_command_reverse = 'Q2,' + self.sign_reverse + '1E-7' + ',' + self.sign_reverse + self.Imax_reverse + ',0,0,0'

	def set_reverse_compliance_voltage(self, Vmax):
		"""
		Set upper voltage limit for reverse breakdown test. Add an upper limit to the compliance voltage?

		Returns
		-------
		None.
		"""
		self.V_compliance_reverse = str(Vmax)
		self.L_command_reverse = 'L'+self.V_compliance_reverse+',0'


	# ADVANCED SETTINGS

	def set_user_sweep_delay(self, sweep_delay):
		"""
		Set sweep delay, lower limit 0ms, upper limit 1s? (change if needed)

		Returns
		-------
		None.
		"""
		if 0 <= sweep_delay <= 1000:
			self.user_sweep_delay = str(sweep_delay)
			self.Q_command = 'Q2,'+self.sign+self.Imin+','+self.sign+self.Imax+','+self.points+',0,'+self.user_sweep_delay
		elif sweep_delay < 0:
			self.user_sweep_delay = '0'
			self.Q_command = 'Q2,'+self.sign+self.Imin+','+self.sign+self.Imax+','+self.points+',0,'+self.user_sweep_delay
		elif sweep_delay > 1000:
			self.user_sweep_delay = '1000'
			self.Q_command = 'Q2,'+self.sign+self.Imin+','+self.sign+self.Imax+','+self.points+',0,'+self.user_sweep_delay


	def set_gpib_address(self, address):
		self.address = address


	def set_points_per_decade(self, points_per_decade):
		"""
		Set points per decade: 5, 10, 25, or 50 points per decade

		Returns
		-------
		None.
		"""
		if points_per_decade == '5':
			self.points = '0'
			self.points_per_decade = 5
			self.Q_command = 'Q2,'+self.sign+self.Imin+','+self.sign+self.Imax+','+self.points+',0,'+self.user_sweep_delay
		elif points_per_decade == '10':
			self.points = '1'
			self.points_per_decade = 10
			self.Q_command = 'Q2,'+self.sign+self.Imin+','+self.sign+self.Imax+','+self.points+',0,'+self.user_sweep_delay
		elif points_per_decade == '25':
			self.points = '2'
			self.points_per_decade = 25
			self.Q_command = 'Q2,'+self.sign+self.Imin+','+self.sign+self.Imax+','+self.points+',0,'+self.user_sweep_delay
		elif points_per_decade == '50':
			self.points = '3'
			self.points_per_decade = 50
			self.Q_command = 'Q2,'+self.sign+self.Imin+','+self.sign+self.Imax+','+self.points+',0,'+self.user_sweep_delay


	def set_integration_time(self, option):
		"""
		Set integration time: 60Hz, Medium, Fast

		Returns
		-------
		None.
		"""
		if option == '60Hz':
			self.S_command = 'S2' #16.67ms
		elif option == 'Medium':
			self.S_command = 'S1' #4ms
		elif option == 'Fast':
			self.S_command = 'S0' #416usec


	# UPDATE ALL SETTINGS

	def update_settings(self, 
					 # BASIC SETTINGS
						compliance_voltage = 4.0, polarity = '+', maximum_current = '1mA', reverse_polarity_start_current = 10.0, reverse_compliance_voltage = 100.0,
					 # ADVANCED SETTINGS
						gpib_address = 16, default_delay = 'on', integration_time = 'Medium', filter_readings = '8', sweep_delay = 0, points_per_decade = '5'):
		# BASIC SETTINGS
		self.set_compliance_voltage(compliance_voltage)
		self.set_polarity(polarity)
		self.set_reverse_polarity()
		self.set_maximum_current(maximum_current)
		self.set_reverse_polarity_end_current(reverse_polarity_start_current)
		self.set_reverse_compliance_voltage(reverse_compliance_voltage)
		# ADVANCED SETTINGS
		self.set_default_delay(default_delay)
		self.set_user_sweep_delay(sweep_delay)
		self.set_filter(filter_readings)
		self.set_integration_time(integration_time)
		self.set_points_per_decade(points_per_decade)
		self.set_gpib_address(gpib_address)


		settings_dict = {
			# BASIC SETTINGS
			"compliance_voltage": compliance_voltage,
			"polarity": polarity,
			"maximum_current": maximum_current,
			"reverse_polarity_start_current": reverse_polarity_start_current,
			"reverse_compliance_voltage": reverse_compliance_voltage,
			#ADVANCED SETTINGS
			"points_per_decade": points_per_decade,
			"sweep_delay": sweep_delay,
			"gpib_address": gpib_address,
			"default_delay": default_delay,
			"integration_time": integration_time,
			"filter_readings": filter_readings
		}

		print(settings_dict)
		return settings_dict
	
	# SWEEPS
	
	def takeIV(self):
		"""
		SMU 236 IV Sequence

		Returns
		-------
		source_values_up: a list of current values fed to the diode, ramping up.
		measure_values_up: a list of voltage values measured across the diode during ramp up current.
		source_values_down: a list of current values fed to the diode, ramping down.
		measure_values_down: a list of voltage values measured across the diode during ramp down current.
		"""
		start_time = time.time()
		num_points = self.points_per_decade * 4 + 1
		filter_count = self.filter_count
		sweep_delay = num_points * filter_count * .0125

		self.reset()

		self.inst.write('F1,1X') #Sources current, measures voltage (sweep)
		time.sleep(self.instrument_delay)

		self.inst.write(self.W_command+':'+self.S_command+':'+self.P_command+':'+self.L_command+'X')
		time.sleep(self.instrument_delay)

		self.inst.write(self.Q_command+'X')
		time.sleep(self.instrument_delay)

		self.inst.write('N1X') #Operate mode
		time.sleep(self.instrument_delay)

		self.inst.write('M2,0X') #Generate service request when sweep is finished and instrument is idle
		time.sleep(self.instrument_delay)

		self.inst.write('H0X') #Execute sweep
		time.sleep(sweep_delay) # Variable based on the the total number of points and delay time

		self.inst.write('N0X') #Standby mode
		time.sleep(self.instrument_delay)

		source_values_up = self.inst.query("G1,2,2X") #Current values
		time.sleep(self.instrument_delay)
		measure_values_up = self.inst.query("G4,2,2X") #Voltage values
		time.sleep(self.instrument_delay)

		self.Q_command = 'Q2,'+self.sign+self.Imax+','+self.sign+self.Imin+','+self.points+',0,'+self.user_sweep_delay #prepare down sweep

		self.inst.write(self.Q_command+'X')

		self.inst.write('N1X') #Operate mode
		time.sleep(self.instrument_delay)

		self.inst.write('M2,0X') #Generate service request when sweep is finished and instrument is idle
		time.sleep(self.instrument_delay)

		self.inst.write('H0X') #Execute sweep
		time.sleep(sweep_delay) # Variable based on the the total number of points and delay time

		self.inst.write('N0X') #Standby mode
		time.sleep(self.instrument_delay)

		#source_values_down = self.inst.query("G1,2,2X") #Current values, these are identical to source_values_up but in reverse, so this is redundant
		#time.sleep(self.instrument_delay)
		measure_values_down = self.inst.query("G4,2,2X") #Voltage values
		time.sleep(self.instrument_delay)

		self.Q_command = 'Q2,'+self.sign+self.Imin+','+self.sign+self.Imax+','+self.points+',0,'+self.user_sweep_delay #return to up sweep

		end_time = time.time()
		elapsed_time = end_time - start_time
		print(f"IV sweep completed in {elapsed_time:.2f} seconds.")
		
		return source_values_up, measure_values_up, measure_values_down
	

	def takeReverseBreakdown(self):
		"""
		SMU 236 Reverse Breakdown Measurement Sequence

		Returns
		-------
		source_values: the current values sourced for the reverse breakdown test
		measure_values: the voltage values measured for the reverse breakdown test
		"""
		self.reset()

		self.inst.write('F1,1X') #Sources current, measures voltage (sweep)
		time.sleep(self.instrument_delay)

		self.inst.write('S1X') #Integration time medium
		time.sleep(self.instrument_delay)

		print(self.L_command_reverse)
		self.inst.write(self.L_command_reverse+'X')
		time.sleep(self.instrument_delay)

		print(self.Q_command_reverse)
		self.inst.write(self.Q_command_reverse+'X')
		time.sleep(self.instrument_delay)

		self.inst.write('N1X') #Operate mode
		time.sleep(self.instrument_delay)

		self.inst.write('M2,0X') #Generate service request when sweep is finished and instrument is idle
		time.sleep(self.instrument_delay)

		self.inst.write('H0X') #Execute sweep
		time.sleep(self.default_sweep_delay) #Should probably be variable and depend on the the total number of points and delay time

		self.inst.write('N0X') #Standby mode
		time.sleep(self.instrument_delay)

		source_values = self.inst.query("G1,2,2X") #Current values
		time.sleep(self.instrument_delay)
		measure_values = self.inst.query("G4,2,2X") #Voltage values
		time.sleep(self.instrument_delay)

		return source_values, measure_values