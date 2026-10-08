import pyvisa

class SMU_K2611B():
	#GPIB address 20 by default
	def __init__(self, address=20, **kwargs):
		rm = pyvisa.ResourceManager()
		gpib_address = f'GPIB0::{address}::INSTR'

		self.inst = rm.open_resource(gpib_address)

		self.inst.write('display.screen = display.SMUA')
		self.inst.write('format.data = format.ASCII')
		self.inst.write('smua.nvbuffer1.clear()')
		self.inst.write('smua.nvbuffer1.appendmode = 1')
		self.inst.write('smua.nvbuffer1.collectsourcevalues = 1')
		self.inst.write('smua.measure.count = 1')
	
	def reset(self):
		self.inst.write('smua.reset()')
		
	def setsourceOn(self):
		self.inst.write('smua.source.output = smua.OUTPUT_ON')
		
	def setsourceOff(self):
		self.inst.write('smua.source.output = smua.OUTPUT_OFF')

	def set_voltage_limit(self, Vmax):
		#voltage in volts
		self.inst.write(f'smua.source.limitv = {Vmax}')

	def set_current_limit(self, Imax):
		#current in amps
		self.inst.write(f'smua.source.limiti = {Imax}')

	def set_voltage_level(self, Vlevel):
		self.inst.write(f'smua.source.levelv = {Vlevel}')

	def set_current_level(self, Ilevel):
		self.inst.write(f'smua.source.leveli = {Ilevel}')

	def set_mode_current_source(self):
		self.inst.write('smua.source.func = smua.OUTPUT_DCAMPS')
		self.inst.write('display.smua.measure.func = display.MEASURE_DCVOLTS')

	def set_mode_voltage_source(self):
		self.inst.write('smua.source.func = smua.OUTPUT_DCVOLTS')
		self.inst.write('display.smua.measure.func = display.MEASURE_DCAMPS')

	def get_current(self):
		self.inst.write('smua.measure.i(smua.nvbuffer1)')

	def get_voltage(self):
		self.inst.write('smua.measure.v(smua.nvbuffer1)')

	# def takeIV(self, Imin=1e-9, Imax=1e-3, Vmax=1, numpts = 101, dtime=0.01):
	#     self.reset()
		
	#     self.inst.write('display.screen = display.SMUA')
	#     self.inst.write('display.smua.measure.func = display.MEASURE_DCVOLTS')
	#     self.inst.write('smua.measure.autorangei = smua.AUTORANGE_ON')
	#     self.inst.write('format.data = format.ASCII')
	#     self.inst.write('smua.nvbuffer1.clear()')
	#     self.inst.write('smua.nvbuffer1.appendmode = 1')
	#     self.inst.write('smua.nvbuffer1.collectsourcevalues = 1')
	#     self.inst.write('smua.measure.count = 1')
	#     self.inst.write('smua.source.func = smua.OUTPUT_DCAMPS')
	#     self.inst.write(f'smua.source.limitv = {Vmax}')
	
	#     self.inst.write(f'smua.source.leveli = {Imin}')
		
	#     self.setsourceOn()
	
	#     irange = np.logspace(np.log10(Imin),np.log10(Imax),numpts)
	#     for ii in irange:
	#         self.inst.write(f'smua.source.leveli = {ii}')
	#         time.sleep(dtime)
	#         self.inst.write('smua.measure.v(smua.nvbuffer1)')
		
	#     # And back down
	#     for ii in reversed(irange):
	#         self.inst.write(f'smua.source.leveli = {ii}')
	#         time.sleep(dtime)
	#         self.inst.write('smua.measure.v(smua.nvbuffer1)')        
	
	#     self.setsourceOff()

	#     # pull data from internal buffer
	#     redvals = self.inst.query_ascii_values('printbuffer(1, smua.nvbuffer1.n, smua.nvbuffer1.readings)')
	#     srcvals = self.inst.query_ascii_values('printbuffer(1, smua.nvbuffer1.n, smua.nvbuffer1.sourcevalues)')
	
	#     df = pd.DataFrame({'Current (A)':srcvals[:numpts], 'Voltage Up (V)': redvals[:numpts], 
	#                        'Voltage Down (V)':[x for x in reversed(redvals[numpts:])]})
		
	#     df['Voltage avg (V)'] = (df['Voltage Up (V)']+df['Voltage Down (V)'])/2
		
	#     return(df)



import time
import pyvisa

# FUNCTION TO CHECK FOR REAL OR FAKE KEITHLEY
def get_SMU():
	"""Gets either a real SMU or a fake SMU
	
	This function tries to connect to a real SMU. 
	If it fails, it returns a Fake SMU which can tell you there's no Keithley connected

	@return SMU_K236() or Fake_SMU() (objects)
	"""
	smu = SMU_2611B()
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
	def takePolaritySweep(self):
		raise RuntimeError("No Keithley connected")

class SMU_2611B():

	def __init__(self, address=20):
		"""
		SMU 236 object parameters.

		Returns
		-------
		None.
		"""
		self.address = address
		self.inst = None

		self.default_delay = -1 #default delay on
		self.integration_time = .24 #default integration time 'medium'/4ms
		self.filter_readings = 8 #default filter readings '8'
		self.compliance_voltage = 4.0 #default compliance voltage = 4.0V
		self.polarity = 1 #default polarity positive
		self.total_points = 21 #default 5 points per decade
		self.points_per_decade = 5 #default 5 points per decade
		self.user_sweep_delay = 0 #default user sweep delay 0ms
		self.minimum_current = 1e-7 #default start current = 0.1uA
		self.maximum_current = 1e-3 #default end current = 1mA



		self.V_limit_polarity = '0.6' #default polarity sweep voltage limit = 0.6V
		self.voltage_steps = '0.1' #default polarity sweep voltage steps = 0.1V
		self.Q_command_polarity = 'Q1,-'+self.V_limit_polarity+','+self.V_limit_polarity+','+self.voltage_steps+',0,100' #linear sweep
		self.I_compliance_polarity = '1E-6' #default polarity sweep compliance current = 1uA
		self.L_command_polarity = 'L'+self.I_compliance_polarity+',0'

		self.Imin_reverse = '1E-6' #default reverse breakdown start current = 1uA
		self.V_compliance_reverse = '20' #default reverse breakdown compliance voltage = 20V
		self.L_command_reverse = 'L'+self.V_compliance_reverse+',0'
		self.reverse_polarity = -1 #default polarity negative

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
		self.inst.write('smu.reset()')

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
			self.default_delay = -1
		elif toggle == 'off':
			self.default_delay = 0

	def set_filter(self, count):
		"""
		Set number of filter readings on SMU 236: off, 2, 4, 8, 16, 32.

		Returns
		-------
		None.
		"""
		if count == 'off':
			self.filter_readings = 0
		elif count in [2, 4, 8, 16, 32]:
			self.filter_readings = count

	def set_polarity(self, polarity):
		"""
		Set source current positive (+) or negative (-).

		Returns
		-------
		None.
		"""
		if polarity == '+':
			self.polarity = 1
		elif polarity == '-':
			self.polarity = -1
		elif polarity in [1, -1]:
			self.polarity = polarity

	def set_compliance_voltage(self, max_voltage):
		"""
		Set compliance voltage. I believe MicroA does not exceed Vmax = 4, but the limit can be set to whatever the correct value is.
		Compliance voltage changes in 0.1V increments, so compliance voltage value truncates to a minimum of 0.1 and to a max of 4.0 if out of range.

		Returns
		-------
		None.
		"""
		if 0.1 <= max_voltage <= 4.0:
			self.compliance_voltage = max_voltage
		elif max_voltage < 0.1:
			self.compliance_voltage = 0.1
		elif max_voltage > 4.0:
			self.compliance_voltage = 4.0

	def set_maximum_current(self, max_current):
		"""
		Set current range based on maximum current: 1mA, 2mA, 3mA, 4mA, 5mA

		Returns
		-------
		None.
		"""
		self.maximum_current = max_current

	
	# def set_polarity_sweep_voltage_steps(self, Vstep):
	# 	"""
	# 	Set diode IV polarity sweep voltage step

	# 	Returns
	# 	-------
	# 	None.
	# 	"""
	# 	self.voltage_steps = Vstep
	# 	self.Q_command_polarity = 'Q1,-'+self.V_limit+','+self.V_limit+','+self.voltage_steps+',0,100'

	
	# def set_polarity_sweep_voltage_limit(self, Vlim):
	# 	"""
	# 	Set diode IV polarity sweep voltage limits

	# 	Returns
	# 	-------
	# 	None.
	# 	"""
	# 	self.V_limit_polarity = Vlim
	# 	self.Q_command_polarity = 'Q1,-'+self.V_limit_polarity+','+self.V_limit_polarity+','+self.voltage_steps+',0,100'

	# def set_polarity_sweep_compliance_current(self, Imax):
	# 	"""
	# 	Set diode IV polarity sweep compliance current

	# 	Returns
	# 	-------
	# 	None.
	# 	"""
	# 	self.I_compliance_polarity = Imax
	# 	self.L_command_polarity = 'L'+self.I_compliance_polarity+',0'

	# def takePolaritySweep(self):
	# 	"""
	# 	SMU 236 Diode IV Polarity Sweep Sequence

	# 	Returns
	# 	-------
	# 	source_values: a list of voltage values forced across the diode.
	# 	measure_values: a list of current values measured through the diode.
	# 	"""
	# 	self.reset() 

	# 	self.inst.write('F0,1X') #Sources voltage, measures current (sweep)

	# 	print(self.L_command_polarity)
	# 	self.inst.write(self.L_command_polarity+'X')

	# 	print(self.Q_command_polarity)
	# 	self.inst.write(self.Q_command_polarity+'X')

	# 	self.inst.write('N1X') #Operate mode

	# 	self.inst.write('M2,0X') #Generate service request when sweep is finished and instrument is idle

	# 	self.inst.write('H0X') #Execute sweep
	# 	self.wait_for_sweep_done()

	# 	self.inst.write('N0X') #Standby mode

	# 	source_values = self.inst.query("G1,2,2X") #Voltage values
	# 	measure_values = self.inst.query("G4,2,2X") #Current values
		
	# 	return source_values, measure_values
	
	def set_reverse_polarity(self):
		"""
		Set current polarity for reverse breakdown test.

		Returns
		-------
		None.
		"""
		self.reverse_polarity = self.polarity * -1 

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
		if points_per_decade in [5, 10, 25, 50]:
			self.points_per_decade = points_per_decade
			self.total_points = points_per_decade * 4 + 1


	def set_integration_time(self, option):
		"""
		Set integration time: 60Hz, Medium, Fast

		Returns
		-------
		None.
		"""
		if option == '60Hz':
			self.S_command = 'S2' #16.67ms
			self.integration_time = 0.01667
		elif option == 'Medium':
			self.S_command = 'S1' #4ms
			self.integration_time = 0.04
		elif option == 'Fast':
			self.S_command = 'S0' #416usec
			self.integration_time = 0.000416

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

		self.inst.write('display.screen = display.SMUA')
		self.inst.write('display.smua.measure.func = display.MEASURE_DCVOLTS')
		self.inst.write('smua.measure.autorangei = smua.AUTORANGE_ON')
		self.inst.write('format.data = format.ASCII')
		self.inst.write('smua.nvbuffer1.clear()')
		self.inst.write('smua.nvbuffer1.appendmode = 1')
		self.inst.write('smua.nvbuffer1.collectsourcevalues = 1')
		self.inst.write('smua.measure.delay = smua.DELAY_AUTO')
		self.inst.write('smua.source.highc = smua.ENABLE')

		self.inst.write(f'smua.source.limitv = {self.compliance_voltage}')
		self.inst.write(f'SweepILogMeasureV(smua, {self.minimum_current}, {self.maximum_current}, 0, {self.total_points})')
		currents = self.inst.query_ascii_values('printbuffer(1, smua.nvbuffer1.n, smua.nvbuffer1.sourcevalues)')
		voltages = self.inst.query_ascii_values('printbuffer(1, smua.nvbuffer1.n, smua.nvbuffer1.readings)')
		print(currents, voltages)

		self.inst.write(f'SweepILogMeasureV(smua, {self.maximum_current}, {self.minimum_current}, .075, {self.total_points})')
		currents = self.inst.query_ascii_values('printbuffer(1, smua.nvbuffer1.n, smua.nvbuffer1.sourcevalues)')
		voltages = self.inst.query_ascii_values('printbuffer(1, smua.nvbuffer1.n, smua.nvbuffer1.readings)')
		print(currents, voltages)
	
	def takeHeatTest(self):
		"""
		SMU 236 Heat Test

		Returns
		-------
		source_values: the current values sourced for the heat test
		measure_values: the voltage values measured for the heat test
		"""

		self.reset() #J0X

		"""
		F1,1 source current measure voltage
		O0 local sense for V-source feedback and measurement
		P0 filter disabled
		Z0 disable suppression
		S0 integration time fast
		W0 disable default delay
		B0.0E+0,0,0 bias level zero, range zero, delay zero
		L6.0E+0,2 set voltage compliance to 6V and source current range to 10nA
		X execute
		M0, sum of zero binary bits and delay/idle period conditions for service request
		X execute
		M2, sum of two binary bits and delay/idle period conditions for service request
		X execute
		"""
		self.inst.write('F1,1O0P0Z0S0W0B0.0E+0,0,0L6.0E+0,2XM0,XM2,X') 

		self.inst.write('U4X') #send measurement parameters and execute

		self.inst.write('B0.0E+0,,Q0,' + self.sign + '1.0E-4,9,0,10X') #Bias level zero, range zero, delay zero; Fixed level sweep at +/-100uA, 100mA range, 0mS delay, 10 cycles and execute

		self.inst.write('U4X') #send measurement parameters and execute

		self.inst.write('B0.0E+0,,Q6,' + self.sign + '5.0E-2,9,0,300X') #Bias level zero, range zero, delay zero; Append fixed level sweep at +/-50mA, 100mA range, 0mS delay, 300 cycles and execute

		self.inst.write('U4X') #send measurement parameters and execute

		self.inst.write('B0.0E+0,,Q6,' + self.sign + '1.0E-4,9,0,100X') #Bias level zero, range zero, delay zero; Append fixed level sweep at +/-100uA, 100mA range, 0mS delay, 100 cycles and execute

		self.inst.write('N1X') #Operate mode

		self.inst.write('M2,0X') #Generate service request when sweep is finished and instrument is idle

		self.inst.write('H0X') #Execute sweep
		self.wait_for_sweep_done()

		self.inst.write('U4X') #send measurement parameters and execute

		source_values = self.inst.query("G1,2,2X") #Current values
		measure_values = self.inst.query("G4,2,2X") #Voltage values

		heat_data = self.inst.query('G15,2,2U8X') #Include all items in string, ASCII data no prefix no suffix, all lines of sweep data per talk; send defined sweep size and execute

		return source_values, measure_values

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

		self.inst.write('S1X') #Integration time medium

		print(self.L_command_reverse)
		self.inst.write(self.L_command_reverse+'X')

		print(self.Q_command_reverse)
		self.inst.write(self.Q_command_reverse+'X')

		self.inst.write('N1X') #Operate mode

		self.inst.write('M2,0X') #Generate service request when sweep is finished and instrument is idle

		self.inst.write('H0X') #Execute sweep
		self.wait_for_sweep_done()

		self.inst.write('N0X') #Standby mode

		source_values = self.inst.query("G1,2,2X") #Current values
		measure_values = self.inst.query("G4,2,2X") #Voltage values

		return source_values, measure_values

	# WAIT FUNCTION 
	def wait_for_sweep_done(self, timeout=10, poll_interval=0.02):
		"""
		SMU 236 Wait for Sweep/SRQ Polling Function

		Returns
		-------
		"""
		start = time.time()
		while True:
			status_byte = self.inst.read_stb()
			if status_byte & 0x02: # Sweep Done bit
				return status_byte
			if time.time() - start > timeout:
				raise TimeoutError("Sweep did not complete in time")
			time.sleep(poll_interval)