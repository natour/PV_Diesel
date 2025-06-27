
import pandas as pd
import numpy as np
import pvlib
import json
from pvlib.location import Location
from datetime import datetime, timedelta

# Load countries from JSON
with open("countries.json", "r") as f:
    COUNTRIES = json.load(f)

GENERATOR_MODELS = {
    "Cummins C100D5": 0.244,
    "CAT DE110E2": 0.250,
    "Perkins 1104A-44TG2": 0.265,
    "FG Wilson P110-3": 0.248,
    "Doosan D1146T": 0.258
}

def simulate_pv_output(country, system_capacity_kw, start_date, days):
    location = Location(latitude=COUNTRIES[country]['lat'], longitude=COUNTRIES[country]['lon'])
    times = pd.date_range(start=start_date, periods=24 * days, freq='h', tz='UTC')
    irradiance = location.get_clearsky(times)
    efficiency = 1
    pv_output_kw = irradiance['ghi'] * system_capacity_kw * efficiency / 1000
    return pv_output_kw, times

def generate_load_profile(days, mode="random", hourly_values=None):
    if mode == "random":
        return pd.Series(np.random.uniform(30, 70, 24 * days))
    elif mode == "manual" and hourly_values is not None and len(hourly_values) == 24:
        repeated = hourly_values * days
        return pd.Series(repeated)
    else:
        raise ValueError("Invalid load input")

def simulate_energy_balance(pv_output, load_profile, diesel_l_per_kwh, generator_size_kw, min_gen_loading_pct, pv_enabled=True):
    hours = len(load_profile)
    gen_output = np.zeros(hours)
    pv_used = np.zeros(hours)
    diesel_liters = np.zeros(hours)
    min_loading_kw = generator_size_kw * min_gen_loading_pct / 100

    for i in range(hours):
        load = load_profile[i]
        pv = pv_output[i] if pv_enabled else 0

        # if pv >= load:
        #     pv_used[i] = load
        #     gen_output[i] = 0
        #     diesel_liters[i] = 0
        # else:
        if True:
            if load <= min_loading_kw:
                 pv_used[i]=0
                 gen_load = load 
                 gen_output[i]=load
                 diesel_liters[i] = gen_load * diesel_l_per_kwh

            elif load>min_loading_kw:
                if pv>min_loading_kw:
                    pv_used[i]=min(pv,load-min_loading_kw)
                    gen_load = min_loading_kw 
                    gen_output[i]=gen_load -pv_used[i]# min_loading_kw
                    diesel_liters[i] = gen_output[i] * diesel_l_per_kwh
                else:
                    pv_used[i]= min(pv,load-min_loading_kw)
                    gen_output[i]=load-pv
                    gen_load =load-pv_used[i]
                    diesel_liters[i] = gen_load * diesel_l_per_kwh
                    
            #remaining = load - pv
            #gen_load = max(remaining, min_loading_kw)
            #gen_output[i] = gen_load
            #pv_used[i] = pv-gen_output[i]
            
            
            #diesel_liters[i] = gen_load * diesel_l_per_kwh

    return {
        "pv_used": pv_used,
        "gen_output": gen_output,
        "diesel_liters": diesel_liters,
        "total_load": load_profile
    }
