import enum
from numbers import Number
from sqlalchemy import Column, Integer, Float, String, Boolean, Date, Enum
from app.db.database import Base

class Build_Info(Base):
	__tablename__ = "build_info"
	# MOST BASIC BLOCK INFORMATION - COMPOSITE PRIMARY KEY: block_engraving, block_serial_number, block_revision
	block_engraving = Column(String, nullable=False, primary_key=True)
	block_serial_number = Column(String, nullable=False, primary_key=True)
	block_revision = Column(String, nullable=False, primary_key=True)
	# INSPECTION AND CLEANOUT INFORMATION
	inspection_date = Column(Date)
	inspector_initials = Column(String)
	cleanout_date = Column(Date)
	cleanout_initials = Column(String)
	# PB1 INFORMATION
	pb1_date = Column(Date)
	pb1_initials = Column(String)
	# PB2 INFORMATION
	pb2_date = Column(Date)
	pb2_initials = Column(String)
	pb2_inspector_initials = Column(String)
	pb2_pass_fail = Column(Boolean)
	pb2_bond_pads_number = Column(Integer)
	pb2_components_number = Column(Integer)
	# FULL BUILD INFORMATION
	full_build_date = Column(Date)
	full_build_initials = Column(String)
	full_build_name = Column(String)

class Build_Parts(Base):
	__tablename__ = "build_parts"
	build_id = Column(Integer, foreign_key="build_info.block_engraving,build_info.block_serial_number,build_info.block_revision", nullable=False)
	name = Column(String, nullable=False)
	quantity = Column(Integer, nullable=False)
	type = Column(String, nullable=False)
	weight = Column(Float, nullable=False)
	instance_id = Column(Integer, primary_key=True, autoincrement=True)
	subassembly_tag = Column(String)
	notes = Column(String)

class Polarity(enum.Enum):
	POSITIVE = "positive"
	NEGATIVE = "negative"

class IV_Info(Base):
	__tablename__ = "iv_info"
	build_id = Column(Integer, foreign_key="build_info.block_engraving,build_info.block_serial_number,build_info.block_revision", nullable=False)
	subassembly_tag = Column(String)
	iv_id = Column(Integer, primary_key=True, autoincrement=True)
	iv_date = Column(Date, nullable=False)
	points_per_decade = Column(Integer, nullable=False)
	reverse_saturation_current = Column(Float, nullable=False)
	series_resistance = Column(Float, nullable=False)
	mean_square_area = Column(Float, nullable=False)
	r_squared_error = Column(Float, nullable=False)
	polarity = Column(Enum(Polarity), nullable=False)
	hysteresis_standard_deviation = Column(Float, nullable=False)
	hysteresis_mean = Column(Float, nullable=False)
	hysteresis_maximum = Column(Float, nullable=False)
	hysteresis_minimum = Column(Float, nullable=False)
	reverse_current = Column(Float, nullable=False)
	reverse_voltage = Column(Float, nullable=False)

class IV_Points(Base):
	__tablename__ = "iv_points"
	iv_id = Column(Integer, foreign_key="iv_info.iv_id", nullable=False)
	point_id = Column(Integer, primary_key=True, autoincrement=True)
	voltage_up_mv = Column(Float, nullable=False)
	voltage_down_mv = Column(Float, nullable=False)
	current_ua = Column(Float, nullable=False)

class Note_Type(enum.Enum):
	GENERAL = "general"
	CURRENT_TEST = "current_test"
	PCB_INFORMATION = "pcb_information"
	REWORK_INFORMATION = "rework_information"

class Notes(Base):
	__tablename__ = "notes"
	build_id = Column(Integer, foreign_key="build_info.block_engraving,build_info.block_serial_number,build_info.block_revision", nullable=False)
	note_id = Column(Integer, primary_key=True, autoincrement=True)
	type = Column(Enum(Note_Type), nullable=False)