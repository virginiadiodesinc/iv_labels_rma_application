import pandas as pd
import win32com.client as win32
import os
from app import config

def get_runcode_from_full_part_number(full_part_number):
    # minimum length of 2
    if len(full_part_number) < 2:
        return None

    last_index_of_runcode = -1
    
    # if last character is the runcode letter, keep moving
    if full_part_number[-1].isalpha():
        last_index_of_runcode = -2

    # starting from last number of string, move left until it's no longer numbers
    # and all those numbers will be the full runcode
    first_index_of_runcode = last_index_of_runcode
    while (abs(first_index_of_runcode) < len(full_part_number) and full_part_number[first_index_of_runcode].isdigit()):
        first_index_of_runcode = first_index_of_runcode - 1

    # convert back to positive integers based on length of the full part number
    # for the first index, if you actually matched all the way to the beginning of the part number, it's already correct
    # if you didn't, adjust by 1 because your current index is actually the first non-digit (from the right)
    if (abs(first_index_of_runcode) < len(full_part_number)):
        first_index_of_runcode = len(full_part_number) + first_index_of_runcode + 1
    last_index_of_runcode = len(full_part_number) + last_index_of_runcode

    full_runcode = full_part_number[first_index_of_runcode:last_index_of_runcode + 1]
    return full_runcode

def get_file_path_from_runcode(runcode):
    runcode_file_name = str(runcode) + ".xls"
    runcode_file_path = os.path.join(config.iv_spec_directory, runcode_file_name)
    return runcode_file_path

def get_spec_sheet_from_file(spec_file_path):
    # Open Excel application
    excel = win32.Dispatch("Excel.Application")
    excel.Visible = False

    #FileName, UpdateLinks, ReadOnly, Format, Password
    wb = excel.Workbooks.Open(spec_file_path, False, True, None)
    iv_sheet = wb.Sheets("IV Spec")

    iv_spec_data = iv_sheet.UsedRange.Value
    spec_df = pd.DataFrame(iv_spec_data)

    wb.Close(False)
    excel.Quit()

    return spec_df

def clean_spec_df(spec_df):
    spec_df = spec_df.dropna(axis=1, how='all')
    spec_df = spec_df.dropna(axis=0, how='all')
    spec_df = spec_df.fillna('')
    return spec_df

def get_html_table_from_spec_df(spec_df):
    html_table = spec_df.to_html(index=False, header=False)
    return html_table

def get_html_table_from_full_part_number(full_part_number):
    runcode = get_runcode_from_full_part_number(full_part_number)
    spec_file_path = get_file_path_from_runcode(runcode)

    spec_df = get_spec_sheet_from_file(spec_file_path)
    spec_df = clean_spec_df(spec_df)

    html_table = get_html_table_from_spec_df(spec_df)
    return html_table

def get_html_table_from_runcode(runcode):
    spec_file_path = get_file_path_from_runcode(runcode)
    
    spec_df = get_spec_sheet_from_file(spec_file_path)
    spec_df = clean_spec_df(spec_df)

    html_table = get_html_table_from_spec_df(spec_df)
    return html_table


# def main():
#     diode_list = ["G1SP4D4.8F22N223A", "A2APXD9FGXXX_LOT1174", "1273"]
#     for diode in diode_list:
#         table = get_html_table_from_full_part_number(diode)
#         print(table)
#     return

# if __name__ == "__main__":
#     main()

