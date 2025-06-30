
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
from datetime import datetime
from bess_simulator import simulate_pv_output, generate_load_profile, simulate_energy_balance, COUNTRIES, GENERATOR_MODELS


random_load_set=False
st.set_page_config(layout="wide")
st.title("PV + Diesel Generator Hybrid Simulation")

st.sidebar.header("Simulation Settings")

country = st.sidebar.selectbox("Select Country", list(COUNTRIES.keys()))
start_date = st.sidebar.date_input("Start Date", datetime.today())
num_days = st.sidebar.number_input("Number of Days", min_value=1, max_value=365, value=3)

pv_enabled = st.sidebar.checkbox("Enable PV", value=True)
pv_size_kw = st.sidebar.number_input("PV Size (kWp)", min_value=0.0, value=100.0)

load_input_method = st.sidebar.radio("Load Profile Input", ["Random", "Manual (24H)"])

if load_input_method == "Manual (24H)":
    st.sidebar.markdown("### Enter Hourly Load (kW)")
    manual_loads = []
    cols = st.sidebar.columns(4)
    for i in range(24):
        col = cols[i % 4]
        manual_loads.append(col.number_input(f"H{i}", min_value=0.0, value=50.0, key=f"hour_{i}"))
    load_profile = generate_load_profile(num_days, mode="manual", hourly_values=manual_loads)
else:
    if random_load_set==False:
        load_profile = generate_load_profile(num_days, mode="random")
        random_load_set=True

st.sidebar.header("Generator Settings")
gen_size_kw = st.sidebar.number_input("Generator Size (kW)", min_value=1.0, value=100.0)
gen_model = st.sidebar.selectbox("Generator Model", list(GENERATOR_MODELS.keys()))
min_loading_pct = st.sidebar.slider("Min Generator Loading (%)", 10, 60, 30)
min_gen=gen_size_kw*(min_loading_pct/100)
pv_output_kw, times = simulate_pv_output(country, pv_size_kw, start_date, num_days)
diesel_l_kwh = GENERATOR_MODELS[gen_model]
diesel_price = COUNTRIES[country]["diesel_price"]

results = simulate_energy_balance(
    pv_output=pv_output_kw,
    load_profile=load_profile,
    diesel_l_per_kwh=diesel_l_kwh,
    generator_size_kw=gen_size_kw,
    min_gen_loading_pct=min_loading_pct,
    pv_enabled=pv_enabled,
    gen_size_kw =gen_size_kw 
)

times = times.tz_localize(None)

df = pd.DataFrame({
    "Time": times,
    "Load (kW)": results["total_load"],
    "PV Used (kW)": results["pv_used"],
    "Generator Output (kW)": results["gen_output"],
    "Diesel Consumed (Liters)": results["diesel_liters"]
})

# ROI calculator inputs
st.sidebar.header("ROI Calculator")
capex = st.sidebar.number_input("Solar CAPEX (USD)", value=10000.0)
opex = st.sidebar.number_input("Annual OPEX (USD)", value=500.0)
lifetime = st.sidebar.number_input("Project Lifetime (Years)", value=10)

# Tabs
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "PV Output", "Load Profile", "Generator Output",
    "Energy Contribution", "Power Overview", "Diesel Summary", "ROI & Summary", "Export"
])

def plot_chart(x, y, title, ylabel, label, color='blue'):
    fig, ax = plt.subplots(figsize=(10, 3))
    ax.plot(x, y, label=label, color=color)
    ax.set_ylabel(ylabel)
    ax.set_xlabel("Time")
    ax.legend()
    ax.tick_params(axis='x', rotation=45)
    st.pyplot(fig)

with tab1:
    st.write("### PV Output (kW)")
    plot_chart(df["Time"], df["PV Used (kW)"], "PV Output", "kW", "PV Used", 'blue')

with tab2:
    st.write("### Load Profile (kW)")
    plot_chart(df["Time"], df["Load (kW)"], "Load Profile", "kW", "Load", 'orange')

with tab3:
    st.write("### Generator Output (kW)")
    plot_chart(df["Time"], df["Generator Output (kW)"], "Generator Output", "kW", "Gen Output", 'green')

with tab4:
    st.write("### Energy Contribution (kWh)")
    fig, ax = plt.subplots(figsize=(10, 3))
    ax.bar(df["Time"], df["PV Used (kW)"], label="PV Used", width=0.02)
    ax.bar(df["Time"], df["Generator Output (kW)"], bottom=df["PV Used (kW)"], label="Gen Output", width=0.02)
    ax.set_ylabel("kWh")
    ax.set_xlabel("Time")
    ax.legend()
    ax.tick_params(axis='x', rotation=45)
    st.pyplot(fig)

with tab5:
    st.write("### Power Overview with Issue Highlights")

    pv = df["PV Used (kW)"]
    gen = df["Generator Output (kW)"]
    load = df["Load (kW)"]
    total_supply = pv + gen

    # Condition 1: PV + Gen < Load (Uncovered Load)
    uncovered_mask = total_supply < load

    # Condition 2: PV > 2x Gen (Undersized Generator)
    undersized_mask = pv > ( gen_size_kw )

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(df["Time"], load, label="Load", color="orange")
    ax.plot(df["Time"], pv, label="PV", color="blue")
    ax.plot(df["Time"], gen, label="Generator", color="green")

    # Highlight uncovered load in red
    ax.fill_between(df["Time"], 0, load, where=uncovered_mask, color='red', alpha=0.3, label="Uncovered Load")

    # Highlight oversized PV vs gen in orange
    ax.fill_between(df["Time"], 0, pv, where=undersized_mask, color='orange', alpha=0.3, label="Undersized Gen")

    ax.set_ylabel("Power (kW)")
    ax.set_xlabel("Time")
    ax.legend()
    ax.tick_params(axis='x', rotation=45)
    st.pyplot(fig)

with tab6:
    st.write("### Diesel Summary")
    plot_chart(df["Time"], df["Diesel Consumed (Liters)"], "Diesel Usage", "Liters", "Diesel (L)", 'red')

with tab7:
    st.write("### Project Summary and ROI")

    baseline = simulate_energy_balance(
        pv_output=pv_output_kw,
        load_profile=load_profile,
        diesel_l_per_kwh=diesel_l_kwh,
        generator_size_kw=gen_size_kw,
        min_gen_loading_pct=min_loading_pct,
        pv_enabled=False
    )

    baseline_liters = pd.Series(baseline["diesel_liters"]).sum()
    actual_liters = df["Diesel Consumed (Liters)"].sum()
    saved_liters = baseline_liters - actual_liters
    usd_savings = saved_liters * diesel_price
    energy_total = df["Load (kW)"].sum()
    pv_energy = df["PV Used (kW)"].sum()
    gen_energy = df["Generator Output (kW)"].sum()

    roi_data = {
        "Total Load (kWh)": energy_total,
        "PV Energy Used (kWh)": pv_energy,
        "Generator Energy (kWh)": gen_energy,
        "Diesel Consumed (L)": actual_liters,
        "Diesel Saved (L)": saved_liters,
        "USD Savings (Annualized)": usd_savings * 365 / num_days
    }

    roi_df = pd.DataFrame.from_dict(roi_data, orient='index', columns=["Value"])
    st.table(roi_df)

    annual_savings = usd_savings * 365 / num_days
    total_cost = capex + (opex * lifetime)
    roi = ((annual_savings * lifetime) - total_cost) / total_cost * 100
    payback = capex / annual_savings if annual_savings > 0 else float("inf")

    st.metric("Annual USD Savings", f"${annual_savings:.2f}")
    st.metric("ROI (%)", f"{roi:.2f}%")
    st.metric("Payback Period (Years)", f"{payback:.2f}")

with tab8:
    st.write("### Export Results")
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Simulation')
    st.download_button("Download Excel", output.getvalue(), file_name="simulation_results.xlsx")
