from app.services.keithley_2600_functions import SMU_2611B, Fake_SMU, get_SMU
import pandas as pd

def main():
    smu = get_SMU()
    smu.takeIV()

if __name__ == "__main__":
    main()
