"""Keithley 236 Source Measure Unit driver (GPIB via pyvisa).

Public interface (used by iv_routes.py and intended to be shared by other SMU drivers):
	get_SMU(address)         -> a connected SMU_K236, or a Fake_SMU if no instrument is found
	smu.close()              -> release the VISA resource (call in a `finally`, or use `with get_SMU() as smu:`)
	smu.update_settings(**)  -> apply the settings coming from the web form
	smu.takeIV()             -> (source_up, measure_up, measure_down)
	smu.takeReverseBreakdown()
	smu.takeHeatTest()
	smu.takePolaritySweep()

Everything prefixed with an underscore is an implementation detail of the 236.
"""
import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

import pyvisa

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 236 command lookup tables (form value -> GPIB code)
# ---------------------------------------------------------------------------
_POLARITY_SIGN = {"+": "", "-": "-"}
_INTEGRATION_CODE = {"Fast": "S0", "Medium": "S1", "60Hz": "S2"}
_FILTER_CODE = {"off": "P0", "2": "P1", "4": "P2", "8": "P3", "16": "P4", "32": "P5"}
_POINTS_PER_DECADE_CODE = {"5": 0, "10": 1, "25": 2, "50": 3}  # 4th parameter of the Q2 (log sweep) command
_MAX_CURRENT_MA = {"1mA": 1, "2mA": 2, "3mA": 3, "4mA": 4, "5mA": 5}

_COMPLIANCE_V_RANGE = (0.1, 4.0)  # forward-sweep voltage compliance limits
_SWEEP_DELAY_MS_RANGE = (0, 1000)

# Data read-back commands: item (1 = source value, 4 = measure value), ASCII format, all sweep lines
_READ_SOURCE = "G1,2,2X"
_READ_MEASURE = "G4,2,2X"

# Polarity sweep (voltage sweep, measure current)
_POLARITY_V_LIMIT = "0.6"  # sweeps -0.6V .. +0.6V
_POLARITY_V_STEP = "0.1"
_POLARITY_COMPLIANCE_A = "1E-6"

# Reverse breakdown (current ramp, opposite polarity to the forward sweep)
_REVERSE_START_A = "1E-7"

# Heat test
_HEAT_SETUP = (
	"F1,1"            # source current, measure voltage (sweep)
	"O0"              # local sense
	"P0"              # filter off
	"Z0"              # suppression off
	"S0"              # fast integration
	"W0"              # default delay off
	"B0.0E+0,0,0"     # bias level 0, range auto, delay 0
	"L6.0E+0,2"       # 6V compliance, 10nA source range
	"X"
	"M0,X"            # clear SRQ mask
	"M2,X"            # SRQ on sweep done
)
# (Q command, level in A, cycles). Q0 creates a fixed-level sweep, Q6 appends one. Range 9 = 100mA.
_HEAT_SEGMENTS = (
	("Q0", "1.0E-4", 10),
	("Q6", "5.0E-2", 300),
	("Q6", "1.0E-4", 100),
)


def _split_at(keithley_string, index):
	"""Split a Keithley data string ("1,2,3,4") after `index` values into two comma-separated strings.

	_split_at("1,2,3,4", 2) -> ("1,2", "3,4")
	"""
	values = [v for v in re.split(r"[,\s]+", keithley_string.strip()) if v]
	if len(values) < index:
		raise RuntimeError(f"Expected at least {index} sweep points, got {len(values)}")
	return ",".join(values[:index]), ",".join(values[index:])


def _clamp(value, low, high):
	return max(low, min(high, value))


def _lookup(table, key, name, current):
	"""Translate a form value through `table`; keep `current` (and warn) if it isn't recognised."""
	try:
		return table[str(key)]
	except KeyError:
		log.warning("Unknown %s %r, keeping %r", name, key, current)
		return current


# ---------------------------------------------------------------------------
# Common interface
# ---------------------------------------------------------------------------
class SMUBase(ABC):
	"""What iv_routes.py expects from any SMU driver (236, 2611B, fake...)."""

	def __enter__(self):
		return self

	def __exit__(self, *exc_info):
		self.close()

	@abstractmethod
	def connect(self): ...

	@abstractmethod
	def close(self): ...

	@abstractmethod
	def update_settings(self, **kwargs): ...

	@abstractmethod
	def takeIV(self): ...

	@abstractmethod
	def takeReverseBreakdown(self): ...

	@abstractmethod
	def takeHeatTest(self): ...

	@abstractmethod
	def takePolaritySweep(self): ...


def get_SMU(address=None):
	"""Return a connected SMU_K236, or a Fake_SMU (which raises on measurements) if none is found.

	`address` is the GPIB primary address (int or numeric string from the form). Blank/invalid -> 16.
	"""
	try:
		address = int(address)
	except (TypeError, ValueError):
		address = 16
	smu = SMU_K236(address)
	return smu if smu.connect() else Fake_SMU()


class Fake_SMU(SMUBase):
	"""Stand-in used when no instrument is connected, so the app still runs."""

	def connect(self):
		return False

	def close(self):
		pass

	def update_settings(self, **kwargs):
		return kwargs

	def _no_keithley(self):
		raise RuntimeError("No Keithley connected")

	def takeIV(self):
		self._no_keithley()

	def takeReverseBreakdown(self):
		self._no_keithley()

	def takeHeatTest(self):
		self._no_keithley()

	def takePolaritySweep(self):
		self._no_keithley()


# ---------------------------------------------------------------------------
# Keithley 236
# ---------------------------------------------------------------------------
@dataclass
class _Settings:
	"""User-facing settings, stored in plain units. GPIB strings are built from these on demand."""
	compliance_voltage: float = 4.0
	sign: str = ""                       # "" = positive current, "-" = negative
	max_current_ma: int = 1
	reverse_end_current_ua: float = 10.0
	reverse_compliance_v: float = 100.0
	default_delay: bool = True
	integration_code: str = "S1"
	filter_key: str = "8"
	points_per_decade: str = "5"
	sweep_delay_ms: float = 0


class SMU_K236(SMUBase):

	def __init__(self, address=16):
		self.address = address
		self.inst = None
		self._rm = None
		self._settings = _Settings()

	# -- connection ---------------------------------------------------------
	def connect(self):
		self.close()
		try:
			self._rm = pyvisa.ResourceManager()
			self.inst = self._rm.open_resource(f"GPIB0::{self.address}::INSTR")
			return True
		except Exception:
			log.exception("Keithley connection failed")
			self.close()
			return False

	def close(self):
		"""Release the VISA resource and its resource manager. Safe to call more than once."""
		for name in ("inst", "_rm"):
			resource = getattr(self, name)
			setattr(self, name, None)
			if resource is not None:
				try:
					resource.close()
				except Exception:
					log.exception("Error closing %s", name)

	# -- settings -----------------------------------------------------------
	def update_settings(self,
			# BASIC SETTINGS
			compliance_voltage=4.0, polarity="+", maximum_current="1mA",
			reverse_polarity_start_current=10.0,  # NB: despite the name, this is the END current (uA) of the reverse ramp
			reverse_compliance_voltage=100.0,
			# ADVANCED SETTINGS
			gpib_address=None,  # accepted for compatibility; the address is chosen when connecting: get_SMU(address)
			default_delay="on", integration_time="Medium", filter_readings="8",
			sweep_delay=0, points_per_decade="5"):
		"""Apply the settings from the web form. Unrecognised choices keep their current value."""
		s = self._settings

		s.compliance_voltage = _clamp(float(compliance_voltage), *_COMPLIANCE_V_RANGE)
		s.sign = _lookup(_POLARITY_SIGN, polarity, "polarity", s.sign)
		s.max_current_ma = _lookup(_MAX_CURRENT_MA, maximum_current, "maximum current", s.max_current_ma)
		s.reverse_end_current_ua = float(reverse_polarity_start_current)
		s.reverse_compliance_v = float(reverse_compliance_voltage)

		s.default_delay = default_delay != "off"
		s.sweep_delay_ms = _clamp(float(sweep_delay), *_SWEEP_DELAY_MS_RANGE)
		s.integration_code = _lookup(_INTEGRATION_CODE, integration_time, "integration time", s.integration_code)
		if str(filter_readings) in _FILTER_CODE:
			s.filter_key = str(filter_readings)
		else:
			log.warning("Unknown filter setting %r, keeping %r", filter_readings, s.filter_key)
		if str(points_per_decade) in _POINTS_PER_DECADE_CODE:
			s.points_per_decade = str(points_per_decade)
		else:
			log.warning("Unknown points per decade %r, keeping %r", points_per_decade, s.points_per_decade)

		return {
			"compliance_voltage": compliance_voltage,
			"polarity": polarity,
			"maximum_current": maximum_current,
			"reverse_polarity_start_current": reverse_polarity_start_current,
			"reverse_compliance_voltage": reverse_compliance_voltage,
			"points_per_decade": points_per_decade,
			"sweep_delay": sweep_delay,
			"gpib_address": gpib_address,
			"default_delay": default_delay,
			"integration_time": integration_time,
			"filter_readings": filter_readings,
		}

	# -- command builders -----------------------------------------------------
	def _current_limits(self):
		"""(start, stop) of the forward sweep as GPIB number strings, e.g. ('100E-9', '1E-3')."""
		ma = self._settings.max_current_ma
		return f"{ma * 100}E-9", f"{ma}E-3"

	def _setup_command(self):
		"""Default delay / integration time / filter / compliance, in one write."""
		s = self._settings
		delay = "W1" if s.default_delay else "W0"
		filt = _FILTER_CODE[s.filter_key]
		return f"{delay}:{s.integration_code}:{filt}:L{s.compliance_voltage},0X"

	def _log_sweep_command(self, start, stop, append=False):
		"""Q2 = create a logarithmic staircase sweep, Q8 = append one to the sweep already in memory.

		Parameters: start, stop, points/decade code, range (0 = auto), delay (ms).
		"""
		s = self._settings
		points = _POINTS_PER_DECADE_CODE[s.points_per_decade]
		kind = "Q8" if append else "Q2"
		return f"{kind},{s.sign}{start},{s.sign}{stop},{points},0,{s.sweep_delay_ms:g}X"

	def _reverse_sweep_command(self):
		s = self._settings
		sign = "" if s.sign == "-" else "-"  # opposite polarity to the forward sweep
		return f"Q2,{sign}{_REVERSE_START_A},{sign}{s.reverse_end_current_ua:g}E-6,0,0,0X"

	# -- low-level instrument access -------------------------------------------
	def _require_connection(self):
		if self.inst is None:
			raise RuntimeError("No Keithley connected")

	def _write(self, command):
		self._require_connection()
		log.debug("236 <- %s", command)
		self.inst.write(command)

	def _query(self, command):
		self._require_connection()
		log.debug("236 <- %s", command)
		return self.inst.query(command)

	def _reset(self):
		self._write("J0X")

	def _read_sweep_data(self):
		"""Read back the sweep buffer: (source_values, measure_values)."""
		source = self._query(_READ_SOURCE)
		measure = self._query(_READ_MEASURE)
		return source, measure

	def _run_sweep(self, timeout=10):
		"""Trigger the programmed sweep, wait for it to finish, and always return to standby."""
		self._write("N1X")    # operate
		self._write("M2,0X")  # SRQ when sweep is done and instrument idle
		self._write("H0X")    # trigger sweep
		try:
			self._wait_for_sweep_done(timeout)
		finally:
			self._write("N0X")  # standby

	def _wait_for_sweep_done(self, timeout=10, poll_interval=0.02):
		"""Poll the serial-poll status byte until the 'sweep done' bit is set."""
		start = time.monotonic()
		while True:
			status_byte = self.inst.read_stb()
			if status_byte & 0x02:
				return status_byte
			if time.monotonic() - start > timeout:
				raise TimeoutError("Sweep did not complete in time")
			time.sleep(poll_interval)

	def _points_per_sweep(self):
		"""Points in one 4-decade log sweep: 4 decades * points/decade + 1 (the end point), e.g. 21 at 5/decade."""
		return int(self._settings.points_per_decade) * 4 + 1

	def _sweep_timeout(self, passes=1):
		"""Worst-case duration (~12.5ms per filtered reading plus user delay), doubled, minimum 10s.

		`passes` is how many 4-decade sweeps are in the sweep list (2 for up + down).
		"""
		s = self._settings
		points = self._points_per_sweep() * passes
		filter_count = 1 if s.filter_key == "off" else int(s.filter_key)
		estimate = points * (filter_count * 0.0125 + s.sweep_delay_ms / 1000)
		return max(10, 2 * estimate)

	# -- measurements -----------------------------------------------------------
	def takeIV(self):
		"""Forward IV: one sweep list made of a log current sweep up, with the same sweep appended back down.

		Returns (source_values_up, measure_values_up, measure_values_down) as comma-separated strings.
		(The source values on the way down are the up values reversed, so they aren't returned.)
		"""
		start_time = time.monotonic()
		low, high = self._current_limits()

		self._reset()
		self._write("F1,1X")  # source current, measure voltage (sweep)
		self._write(self._setup_command())
		self._write(self._log_sweep_command(low, high))                 # up (create)
		self._write(self._log_sweep_command(high, low, append=True))    # down (append)
		self._run_sweep(self._sweep_timeout(passes=2))

		# The sweep list is [up points][down points]; split after the first sweep's worth of points.
		n = self._points_per_sweep()
		source, measure = self._read_sweep_data()
		source_up, _ = _split_at(source, n)
		measure_up, measure_down = _split_at(measure, n)
		n_down = measure_down.count(",") + 1 if measure_down else 0
		if n_down != n:
			log.warning("IV sweep: expected %d points on the way down, got %d", n, n_down)

		log.info("IV sweep completed in %.2f seconds.", time.monotonic() - start_time)
		return source_up, measure_up, measure_down

	def takeReverseBreakdown(self):
		"""Reverse-polarity current ramp. Returns (source_values, measure_values)."""
		s = self._settings
		self._reset()
		self._write("F1,1X")
		self._write("S1X")  # medium integration
		self._write(f"L{s.reverse_compliance_v:g},0X")
		self._write(self._reverse_sweep_command())
		self._run_sweep()
		return self._read_sweep_data()

	def takeHeatTest(self):
		"""Fixed-level current pulses used to estimate junction temperature. Returns (source_values, measure_values)."""
		sign = self._settings.sign
		self._reset()
		self._write(_HEAT_SETUP)
		for command, level, cycles in _HEAT_SEGMENTS:
			# bias 0, range auto, delay 0; 100mA range (9), 0ms delay
			self._write(f"B0.0E+0,,{command},{sign}{level},9,0,{cycles}X")
		self._run_sweep()
		return self._read_sweep_data()

	def takePolaritySweep(self):
		"""Quick voltage sweep to determine diode orientation. Returns (source_values, measure_values)."""
		self._reset()
		self._write("F0,1X")  # source voltage, measure current (sweep)
		self._write(f"L{_POLARITY_COMPLIANCE_A},0X")
		self._write(f"Q1,-{_POLARITY_V_LIMIT},{_POLARITY_V_LIMIT},{_POLARITY_V_STEP},0,100X")
		self._run_sweep()
		return self._read_sweep_data()