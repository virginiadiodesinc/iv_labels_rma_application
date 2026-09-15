from app import config
import os

block_file_directory = config.block_file_directory
build_file_directory = config.build_file_directory

def check_labview_file_existence(file_name, directory):
    full_file_path = os.path.join(directory, file_name)
    if os.path.isfile(full_file_path):
        return True
    else:
        return False

def check_block_file_existence(block_file_name):
    return check_labview_file_existence(block_file_name, block_file_directory)

def check_build_file_existence(build_file_name):
    return check_labview_file_existence(build_file_name, build_file_directory)