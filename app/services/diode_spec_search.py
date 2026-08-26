import pandas as pd
import win32com.client as win32
import win32gui
import win32con
import pythoncom
import os
import threading
import time
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


def _bring_dialog_to_front(stop_event, timeout_seconds=20):
    """
    Runs on a background thread while the main thread is blocked inside
    Workbooks.Open(). Polls for a newly-appeared top-level window whose
    title suggests it's Excel's password prompt (or another blocking
    alert) and forces it to the foreground, so the user doesn't have to
    hunt for it behind other windows.
    """
    deadline = time.time() + timeout_seconds
    keywords = ("password", "microsoft excel")

    def enum_handler(hwnd, _):
        if stop_event.is_set():
            return
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if title and any(k in title.lower() for k in keywords):
            try:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
                stop_event.set()
            except Exception:
                pass

    while not stop_event.is_set() and time.time() < deadline:
        win32gui.EnumWindows(enum_handler, None)
        time.sleep(0.25)


def get_spec_sheet_from_file(spec_file_path):
    # COM requires the calling thread to be initialized, especially important
    # if this ever runs inside a web request handler / worker thread.
    pythoncom.CoInitialize()

    excel = None
    wb = None
    stop_event = threading.Event()
    watcher = threading.Thread(target=_bring_dialog_to_front, args=(stop_event,), daemon=True)

    try:
        # DispatchEx (not Dispatch) forces a brand-new, isolated Excel process
        # instead of attaching to whatever Excel instance is already running
        # on the machine. This is what prevents us from closing/hiding a
        # user's unrelated, already-open workbooks.
        excel = win32.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False  # auto-dismiss non-critical prompts (format warnings, etc.)

        watcher.start()

        #FileName, UpdateLinks, ReadOnly, Format, Password
        wb = excel.Workbooks.Open(spec_file_path, False, True, None)

        stop_event.set()  # no need to keep polling once Open() has returned

        iv_sheet = wb.Sheets("IV Spec")
        iv_spec_data = iv_sheet.UsedRange.Value
        spec_df = pd.DataFrame(iv_spec_data)

        return spec_df
    
    finally:
        stop_event.set()
        if wb is not None:
            try:
                wb.Close(False)
            except Exception:
                pass
        if excel is not None:
            try:
                excel.Quit()  # safe now: this Quit() only affects our private, isolated instance
            except Exception:
                pass
        pythoncom.CoUninitialize()


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
