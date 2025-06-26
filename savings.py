
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from bess_simulator import simulate_pv_output, generate_load_profile, simulate_energy_balance, COUNTRIES, GENERATOR_MODELS

st.title("PV + Diesel Generator Hybrid Simulation")

# Sidebar Inputs
st.sidebar.header("Simulation Settings")

country = st.sidebar.selectbox("Select Country", list(COUNTRIES.keys()))
start_date = st.sidebar.date_input("Start Date", datetime.today())
num_days = st.sidebar.number_input("Number of Days", min_value=1, max_value=365, value=3)

pv_enabled = st.sidebar.checkbox("Enable PV", value=True)
pv_size_kw = st.sidebar.number_input("PV Size (kWp)", min_value=0.0, value=100.0)

load_input_method = st.sidebar.radio("Load Profile Input", ["Random", "Manual"])

if load_input_method == "Manual":
    st.sidebar.info("Enter hourly load (24 x Days rows).")
    load_csv = st.file_uploader("Upload Load Profile CSV", type="csv")
    if load_csv:
        load_profile = pd.read_csv(load_csv, header=None).squeeze()
    else:
        st.warning("Please upload a valid CSV for manual input.")
        st.stop()
else:
    load_profile = generate_load_profile(num_days, mode="random")

# Generator Settings
st.sidebar.header("Generator Settings")
gen_size_kw = st.sidebar.number_input("Generator Size (kW)", min_value=1.0, value=100.0)
gen_model = st.sidebar.selectbox("Generator Model", list(GENERATOR_MODELS.keys()))
min_loading_pct = st.sidebar.slider("Min Generator Loading (%)", 10, 60, 30)

# Run Simulation
pv_output_kw, times = simulate_pv_output(country, pv_size_kw, start_date, num_days)
diesel_l_kwh = GENERATOR_MODELS[gen_model]
diesel_price = COUNTRIES[country]["diesel_price"]

results = simulate_energy_balance(
    pv_output=pv_output_kw,
    load_profile=load_profile,
    diesel_l_per_kwh=diesel_l_kwh,
    generator_size_kw=gen_size_kw,
    min_gen_loading_pct=min_loading_pct,
    pv_enabled=pv_enabled
)

df = pd.DataFrame({
    "Time": times,
    "Load (kW)": results["total_load"],
    "PV Used (kW)": results["pv_used"],
    "Generator Output (kW)": results["gen_output"],
    "Diesel Consumed (Liters)": results["diesel_liters"]
})

st.subheader("Simulation Results")

# Charts
st.line_chart(df.set_index("Time")[["PV Used (kW)"]])
st.line_chart(df.set_index("Time")[["Load (kW)"]])
st.line_chart(df.set_index("Time")[["Generator Output (kW)"]])

coverage_df = pd.DataFrame({
    "Time": times,
    "PV Contribution (%)": (df["PV Used (kW)"] / df["Load (kW)"]).fillna(0).clip(0, 1) * 100,
    "Gen Contribution (%)": (df["Generator Output (kW)"] / df["Load (kW)"]).fillna(0).clip(0, 1) * 100
}).set_index("Time")

st.area_chart(coverage_df)

# Diesel Consumption & Savings
total_liters = df["Diesel Consumed (Liters)"].sum()
if pv_enabled:
    pv_off_results = simulate_energy_balance(
        pv_output=pv_output_kw,
        load_profile=load_profile,
        diesel_l_per_kwh=diesel_l_kwh,
        generator_size_kw=gen_size_kw,
        min_gen_loading_pct=min_loading_pct,
        pv_enabled=False
    )
    baseline_liters = pd.Series(pv_off_results["diesel_liters"]).sum()
    saved_liters = baseline_liters - total_liters
    usd_savings = saved_liters * diesel_price

    st.metric("Total Diesel Saved (L)", f"{saved_liters:.2f}")
    st.metric("USD Savings", f"${usd_savings:.2f}")

st.line_chart(df.set_index("Time")[["Diesel Consumed (Liters)"]])
