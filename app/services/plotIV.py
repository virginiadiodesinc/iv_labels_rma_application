import plotly.express as px
import pandas as pd

file_path = "VDI1.0X36SHM_R1 B1-01 G4AP1P9X3_BI13.0FDG769B Cir2p2X3_D A#WR1.9X3 - WM250X36SHMR1_(WR1.0X36SHM) 1-01 In block- COPY.iv"

Vup = [] # in mV
Vdown = [] # in mV
Isource = [] # in uA

Vavg = []

with open(file_path, encoding='utf-8') as f:
    for index, line in enumerate(f):
        if index >= 16:
            Vup.append(line.replace('\n', '').split('\t')[0])
            Vdown.append(line.replace('\n', '').split('\t')[1])
            Isource.append(line.replace('\n', '').split('\t')[2])

for V1, V2 in zip(Vup, Vdown):
    Vavg.append((float(V1) + float(V2)) / 2)

df = pd.DataFrame({
    "Voltage (V)": Vavg,
    "Current (A)": Isource
})

fig = px.scatter(df, x="Voltage (mV)", y="Current (A)", labels={"x": "Voltage(mV)", "y":"Current (uA)"}, title="IV Curve", log_y=True)

fig.update_traces(mode='lines+markers')

if abs(df["Voltage (mV)"].max() - df["Voltage (mV)"].min()) < 100:
    fig.update_xaxes(range=[df["Voltage (mV)"].min() - 25, df["Voltage (mV)"].min() + 75])

fig.write_html("plot.html", auto_open=True)