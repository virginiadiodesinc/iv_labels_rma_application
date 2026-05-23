import enum
from numbers import Number
from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, Boolean, Date, Enum, DateTime, CheckConstraint, ForeignKey
from app.db.database import Base

class Build_Info(Base):
	__tablename__ = "build_info"
	block_id = Column(String, nullable=False, primary_key=True) #Concatenated version of block_engraving, block_serial_number, and block_revision to avoid ForeignKeyConstraint
	# MOST BASIC BLOCK INFORMATION - COMPOSITE PRIMARY KEY: block_engraving, block_serial_number, block_revision
	block_engraving = Column(String, nullable=False)
	block_serial_number = Column(String, nullable=False)
	block_revision = Column(String, nullable=False)
	# INSPECTION AND CLEANOUT INFORMATION
	inspection_date = Column(Date, nullable=True)
	inspection_initials = Column(String)
	cleanout_date = Column(Date, nullable=True)
	cleanout_initials = Column(String)
	# PB1 INFORMATION
	pb1_build_name = Column(String)
	pb1_date = Column(Date, nullable=True)
	pb1_initials = Column(String)
	# PB2 INFORMATION
	pb2_build_name = Column(String)
	pb2_date = Column(Date, nullable=True)
	pb2_initials = Column(String)
	pb2_inspection_initials = Column(String)
	# FULL BUILD INFORMATION
	full_build_date = Column(Date, nullable=True)
	full_build_initials = Column(String)
	full_build_name = Column(String)
	# FILE PATHS
	block_file_path = Column(String)
	build_file_path = Column(String)


class Build_Parts(Base):
	__tablename__ = "build_parts"
	instance_id = Column(Integer, primary_key=True, autoincrement=True)
	block_id = Column(String, ForeignKey("build_info.block_id"), nullable=False)
	part_name = Column(String, nullable=False)
	quantity = Column(Integer, nullable=False)
	part_type = Column(String, nullable=False)
	part_lot = Column(String, nullable=False)
	#weight = Column(Float, nullable=False) not yet implemented
	#subassembly_tag = Column(String) not yet implemented

class Polarity(enum.Enum):
	POSITIVE = "positive"
	NEGATIVE = "negative"

class IV_Info(Base):
	__tablename__ = "iv_info"
	build_id = Column(Integer, ForeignKey("build_info.block_id"), nullable=False)
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
	iv_file_path = Column(String)

class IV_Points(Base):
	__tablename__ = "iv_points"
	iv_id = Column(Integer, ForeignKey("iv_info.iv_id"), nullable=False)
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
	build_id = Column(Integer, ForeignKey("build_info.block_id"), nullable=False)
	note_id = Column(Integer, primary_key=True, autoincrement=True)
	type = Column(Enum(Note_Type), nullable=False)

class Feedback(Base):
	__tablename__ = 'feedback'
	feedback_id = Column(Integer, primary_key=True, autoincrement=True)
	user_initials = Column(String(3), nullable=False)
	user_feedback = Column(String, nullable=False)
	resolution_status = Column(String, nullable=False, default="Unresolved")
	submission_datetime = Column(DateTime, nullable=False, default=datetime.utcnow)
	__table_args__ = (
		CheckConstraint("length(user_initials) = 3", name="initials_length_check"),
	)