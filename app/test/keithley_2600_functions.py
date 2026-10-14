"""Keithley 2611B (Series 2600B) SMU driver: GPIB via pyvisa, instrument programmed in TSP.

Same public interface as the 236 driver (see SMUBase there), so iv_routes.py doesn't care which one it gets:
	get_SMU(address)         -> a connected SMU_2611B, or a Fake_SMU if no instrument is found
	smu.update_settings(**)  -> store the settings coming from the web form (nothing is sent to the instrument yet)
	smu.takeIV()             -> (source_up, measure_up, measure_down) as comma-separated strings
	smu.takeReverseBreakdown()
	smu.takePolaritySweep()
	smu.takeHeatTest()       -> not implemented for the 2611B yet
	smu.close()

Every take*() starts with smua.reset() and the shared boilerplate (_CONFIG_COMMANDS), then applies the stored
settings, so nothing carries over between measurements.
"""
import logging
import math
import time
from contextlib import contextmanager
from dataclasses import dataclass

import pyvisa

from app.services.keithley_236_functions import Fake_SMU, SMUBase  # noqa: F401  (Fake_SMU is re-exported for callers)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lookup tables (form value -> instrument value)
# ---------------------------------------------------------------------------
_NPLC = {"Fast": 0.025, "Medium": 0.24, "60Hz": 1.0}  # = 416us / 4ms / 16.7ms at 60Hz, same as the 236's S0/S1/S2
_FILTER_COUNT = {"off": 0, "2": 2, "4": 4, "8": 8, "16": 16, "32": 32}
_POINTS_PER_DECADE = {"5": 5, "10": 10, "25": 25, "50": 50}
_MAX_CURRENT_MA = {"1mA": 1, "2mA": 2, "3mA": 3, "4mA": 4, "5mA": 5}
_POLARITY_SIGN = {"+": 1, "-": -1}

_COMPLIANCE_V_RANGE = (0.1, 4.0)
_SWEEP_DELAY_MS_RANGE = (0, 1000)

# Averaging style used when the filter is on. REPEAT_AVG takes N fresh conversions per reading;
# switch to smua.FILTER_MOVING_AVG here if you want to compare.
_FILTER_TYPE = "smua.FILTER_REPEAT_AVG"

# Boilerplate for every sweep (the "White Keithley" setup).
# NB: measure.autorangei is the *measure* current range; source autoranging is separate (smua.source.autorangei).
_CONFIG_COMMANDS = (
	"display.screen = display.SMUA",
	"display.smua.measure.func = display.MEASURE_DCVOLTS",
	"smua.measure.autorangei = smua.AUTORANGE_ON",
	"format.data = format.ASCII",
	"smua.nvbuffer1.clear()",
	"smua.nvbuffer1.appendmode = 1",
	"smua.nvbuffer1.collectsourcevalues = 1",
)

_PRINT_READINGS = "printbuffer(1, smua.nvbuffer1.n, smua.nvbuffer1.readings)"
_PRINT_SOURCE = "printbuffer(1, smua.nvbuffer1.n, smua.nvbuffer1.sourcevalues)"

# Reverse breakdown (current ramp, opposite polarity to the forward sweep)
_REVERSE_START_A = 1e-7
_REVERSE_POINTS_PER_DECADE = 5

# Polarity sweep (voltage sweep, measure current)
_POLARITY_V_LIMIT = 0.6   # sweeps -0.6V .. +0.6V
_POLARITY_V_STEP = 0.1
_POLARITY_COMPLIANCE_A = 1e-6
_POLARITY_SETTLE_S = 0.05


def _choose(table, key, name, current):
	"""Translate a form value through `table`; keep `current` (and warn) if it isn't recognised."""
	try:
		return table[str(key)]
	except KeyError:
		log.warning("Unknown %s %r, keeping %r", name, key, current)
		return current


def get_SMU(address=None):
	"""Return a connected SMU_2611B, or a Fake_SMU (which raises on measurements) if none is found.

	`address` is the GPIB primary address (int or numeric string from the form). Blank/invalid -> 20.
	"""
	try:
		address = int(address)
	except (TypeError, ValueError):
		address = 20
	smu = SMU_2611B(address)
	return smu if smu.connect() else Fake_SMU()


@dataclass
class _Settings:
	"""User-facing settings in plain units. TSP commands are built from these when a measurement runs."""
	compliance_voltage: float = 4.0
	sign: int = 1                        # +1 = positive current, -1 = negative
	max_current_ma: int = 1
	reverse_end_current_ua: float = 10.0
	reverse_compliance_v: float = 100.0
	default_delay: bool = True           # True -> smua.DELAY_AUTO measure delay
	nplc: float = 0.24
	filter_count: int = 8                # 0 = filter off
	points_per_decade: int = 5
	sweep_delay_s: float = 0.0           # extra settle time after each source step (the form's "sweep delay")


class SMU_2611B(SMUBase):

	# Optional hold (seconds) at the first source level, output on, before the sweep starts.
	# Lets the output capacitance charge once instead of during the first few points. 0 = off.
	prebias_s = 0.0

	def __init__(self, address=20):
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
		"""Store the settings from the web form. Unrecognised choices keep their current value."""
		s = self._settings

		low, high = _COMPLIANCE_V_RANGE
		s.compliance_voltage = max(low, min(high, float(compliance_voltage)))
		s.sign = _choose(_POLARITY_SIGN, polarity, "polarity", s.sign)
		s.max_current_ma = _choose(_MAX_CURRENT_MA, maximum_current, "maximum current", s.max_current_ma)
		s.reverse_end_current_ua = float(reverse_polarity_start_current)
		s.reverse_compliance_v = float(reverse_compliance_voltage)

		s.default_delay = default_delay != "off"
		low, high = _SWEEP_DELAY_MS_RANGE
		s.sweep_delay_s = max(low, min(high, float(sweep_delay))) / 1000
		s.nplc = _choose(_NPLC, integration_time, "integration time", s.nplc)
		s.filter_count = _choose(_FILTER_COUNT, filter_readings, "filter setting", s.filter_count)
		s.points_per_decade = _choose(_POINTS_PER_DECADE, points_per_decade, "points per decade", s.points_per_decade)

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

	# -- low-level instrument access -------------------------------------------
	def _require_connection(self):
		if self.inst is None:
			raise RuntimeError("No Keithley connected")

	def _write(self, command):
		self._require_connection()
		log.debug("2611B <- %s", command)
		self.inst.write(command)

	def _write_lines(self, commands):
		for command in commands:
			self._write(command)

	def _query(self, command):
		self._require_connection()
		log.debug("2611B <- %s", command)
		return self.inst.query(command).strip()

	@contextmanager
	def _timeout(self, seconds):
		"""Temporarily raise the VISA timeout. A sweep blocks the next query until it finishes."""
		self._require_connection()
		previous = self.inst.timeout
		self.inst.timeout = seconds * 1000
		try:
			yield
		finally:
			self.inst.timeout = previous

	def _raise_on_errors(self):
		"""Raise if the instrument's error queue has anything in it (and empty the queue)."""
		errors = []
		while len(errors) < 20 and int(float(self._query("print(errorqueue.count)"))) > 0:
			errors.append(self._query("print(errorqueue.next())"))
		if errors:
			raise RuntimeError("2611B error(s): " + " | ".join(errors))

	def _reset(self):
		self._write("smua.reset()")
		self._write("errorqueue.clear()")

	def _output_off(self):
		self._write("smua.source.output = smua.OUTPUT_OFF")

	# -- setup builders -------------------------------------------------------------
	def _measure_commands(self):
		"""Integration time, measure delay and filter."""
		s = self._settings
		commands = [
			f"smua.measure.nplc = {s.nplc:g}",
			f"smua.measure.delay = {'smua.DELAY_AUTO' if s.default_delay else 0}",
		]
		if s.filter_count > 1:
			commands += [
				f"smua.measure.filter.type = {_FILTER_TYPE}",
				f"smua.measure.filter.count = {s.filter_count}",
				"smua.measure.filter.enable = smua.FILTER_ON",
			]
		else:
			commands.append("smua.measure.filter.enable = smua.FILTER_OFF")
		return commands

	def _prepare_current_sweep(self, voltage_limit):
		"""Reset, boilerplate, then source current / measure voltage with the stored measure settings."""
		self._reset()
		self._write_lines(_CONFIG_COMMANDS)
		self._write("smua.source.func = smua.OUTPUT_DCAMPS")
		self._write(f"smua.source.limitv = {voltage_limit:g}")
		self._write_lines(self._measure_commands())

	def _settle_time(self):
		"""Seconds to wait after each source step before measuring (the factory sweeps' `stime`).

		This is the main tweak point for the settling problem.
		"""
		return self._settings.sweep_delay_s

	def _sweep_timeout_s(self, points, settle_s):
		"""Generous upper bound on a sweep's duration (50Hz mains assumed), minimum 10s."""
		s = self._settings
		per_point = settle_s + max(1, s.filter_count) * s.nplc / 50 + 0.1  # 0.1s: auto delay / autozero / overhead
		return max(10, 2 * points * per_point)

	def _points_per_sweep(self):
		"""Points in one 4-decade log sweep: 4 decades * points/decade + 1, e.g. 21 at 5/decade."""
		return self._settings.points_per_decade * 4 + 1

	def _prebias(self, level):
		if self.prebias_s > 0:
			self._write(f"smua.source.leveli = {level:g}")
			self._write("smua.source.output = smua.OUTPUT_ON")
			time.sleep(self.prebias_s)

	def _run_factory_sweep(self, call, points, settle_s, with_source=True):
		"""Send a KISweep factory function call and read back the buffers: (source_values, measure_values).

		The sweep blocks the instrument, so the first query only answers when the sweep is finished.
		"""
		self._write(call)
		with self._timeout(self._sweep_timeout_s(points, settle_s) + self.prebias_s):
			measure = self._query(_PRINT_READINGS)
		source = self._query(_PRINT_SOURCE) if with_source else None
		self._raise_on_errors()
		return source, measure

	# -- measurements -----------------------------------------------------------
	def takeIV(self):
		"""Forward IV: log current sweep up, then back down.

		Returns (source_values_up, measure_values_up, measure_values_down) as comma-separated strings.
		(The source values on the way down are the up values reversed, so they aren't returned.)
		"""
		start_time = time.monotonic()
		s = self._settings
		low, high = s.max_current_ma * 1e-7, s.max_current_ma * 1e-3
		sign, points, settle = s.sign, self._points_per_sweep(), self._settle_time()

		self._prepare_current_sweep(s.compliance_voltage)
		self._raise_on_errors()
		try:
			self._prebias(sign * low)
			source_up, measure_up = self._run_factory_sweep(
				f"SweepILogMeasureV(smua, {sign * low:g}, {sign * high:g}, {settle:g}, {points})", points, settle)
			_, measure_down = self._run_factory_sweep(
				f"SweepILogMeasureV(smua, {sign * high:g}, {sign * low:g}, {settle:g}, {points})", points, settle,
				with_source=False)
		finally:
			self._output_off()

		log.info("IV sweep completed in %.2f seconds.", time.monotonic() - start_time)
		return source_up, measure_up, measure_down

	def takeReverseBreakdown(self):
		"""Reverse-polarity current ramp. Returns (source_values, measure_values)."""
		s = self._settings
		stop = s.reverse_end_current_ua * 1e-6
		points = max(2, round(_REVERSE_POINTS_PER_DECADE * math.log10(stop / _REVERSE_START_A)) + 1)
		sign, settle = -s.sign, self._settle_time()  # opposite polarity to the forward sweep

		self._prepare_current_sweep(s.reverse_compliance_v)
		self._raise_on_errors()
		try:
			return self._run_factory_sweep(
				f"SweepILogMeasureV(smua, {sign * _REVERSE_START_A:g}, {sign * stop:g}, {settle:g}, {points})", points, settle)
		finally:
			self._output_off()

	def takePolaritySweep(self):
		"""Quick voltage sweep to determine diode orientation. Returns (source_values, measure_values)."""
		points = round(2 * _POLARITY_V_LIMIT / _POLARITY_V_STEP) + 1

		self._reset()
		self._write_lines(_CONFIG_COMMANDS)
		self._write("smua.source.func = smua.OUTPUT_DCVOLTS")
		self._write(f"smua.source.limiti = {_POLARITY_COMPLIANCE_A:g}")
		self._write("display.smua.measure.func = display.MEASURE_DCAMPS")
		self._write_lines(self._measure_commands())
		self._raise_on_errors()
		try:
			return self._run_factory_sweep(
				f"SweepVLinMeasureI(smua, {-_POLARITY_V_LIMIT:g}, {_POLARITY_V_LIMIT:g}, {_POLARITY_SETTLE_S:g}, {points})",
				points, _POLARITY_SETTLE_S)
		finally:
			self._output_off()

	def takeHeatTest(self):
		raise NotImplementedError("Heat test is not implemented for the 2611B yet")