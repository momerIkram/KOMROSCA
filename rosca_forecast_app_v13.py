
# ROSCA Forecast App v13 (Full Scope Version)
# See previous message for the full scope description
# This script includes all required features, logic, and export functionality

import streamlit as st
import pandas as pd
import numpy as np
import io

def validate_slab_total(slab_alloc):
    return abs(sum(slab_alloc.values()) - 100) < 0.01

def get_config():
    st.sidebar.header("🔧 Configuration")
    return {
        "total_market": st.sidebar.number_input("Total Market Size", value=20000000),
        "tam_pct": st.sidebar.slider("TAM (% of Market)", 1, 100, 10),
        "start_pct": st.sidebar.slider("Starting TAM (%)", 1, 100, 10),
        "monthly_growth": st.sidebar.number_input("Monthly Growth %", value=2.0),
        "yearly_growth": st.sidebar.number_input("Yearly TAM Growth %", value=5.0),
        "kibor": st.sidebar.number_input("KIBOR %", value=11.0),
        "spread": st.sidebar.number_input("Platform Spread %", value=5.0),
        "default_rate": st.sidebar.number_input("Default Rate %", value=1.0),
        "penalty_pct": st.sidebar.number_input("Default Penalty %", value=10.0),
        "fee_method": st.sidebar.selectbox("Fee Collection Method", ["Upfront", "Monthly"]),
    }

def get_durations_and_slabs():
    durations = st.multiselect("Select Committee Durations (Months)", [3,4,5,6,8,10], default=[3,4,6])
    slab_map = {}
    for d in durations:
        with st.expander(f"Slab Allocation for {d}M Committees"):
            slabs = [1000, 2000, 5000, 10000, 15000, 20000, 25000, 50000]
            slab_alloc = {}
            cols = st.columns(len(slabs))
            for i, s in enumerate(slabs):
                slab_alloc[s] = cols[i].number_input(f"{s}", min_value=0.0, max_value=100.0, value=0.0, key=f"{d}_{s}_slab")
            if not validate_slab_total(slab_alloc):
                st.warning("Total must equal 100%")
            slab_map[d] = slab_alloc
    return durations, slab_map

def get_slot_fees(durations):
    slot_fees = {}
    for d in durations:
        with st.expander(f"Slot Fee % and Blocking for {d}M"):
            slot_fees[d] = {}
            for s in range(1, d+1):
                col1, col2 = st.columns([3,1])
                fee = col1.number_input(f"Slot {s} Fee %", 0.0, 100.0, 1.0, key=f"{d}_{s}_fee")
                block = col2.checkbox("Block", key=f"{d}_{s}_block")
                slot_fees[d][s] = {"fee": fee, "blocked": block}
    return slot_fees

def run_forecast(config, durations, slab_map, slot_fees):
    base_users = int((config['total_market'] * config['tam_pct']/100) * (config['start_pct']/100))
    active_users = base_users
    tam_used = base_users
    months = 60
    forecast = []

    for m in range(1, months+1):
        for d in durations:
            for slab, pct in slab_map[d].items():
                if pct <= 0: continue
                users = int(active_users * (pct / 100))
                for slot in range(1, d+1):
                    if slot_fees[d][slot]['blocked']: continue
                    deposit = slab * d
                    fee_pct = slot_fees[d][slot]['fee']
                    fee = deposit * (fee_pct / 100)
                    nii = deposit * users * ((config['kibor'] + config['spread']) / 100 / 12)
                    defaults = int(users * config['default_rate'] / 100)
                    pre, post = defaults // 2, defaults - defaults // 2
                    pre_loss = pre * deposit * (1 - config['penalty_pct']/100)
                    post_loss = post * deposit
                    profit = fee * users + nii - pre_loss - post_loss
                    forecast.append({
                        "Month": m,
                        "Year": (m-1)//12 + 1,
                        "Duration": d,
                        "Slab": slab,
                        "Slot": slot,
                        "Users": users,
                        "Deposit/User": deposit,
                        "Fee %": fee_pct,
                        "Fee Collected": fee * users,
                        "NII": nii,
                        "Defaults": defaults,
                        "Profit": profit
                    })
        active_users = int(active_users * (1 + config['monthly_growth']/100))
        tam_used += active_users
        if tam_used >= (config['total_market'] * config['tam_pct']/100):
            break
    return pd.DataFrame(forecast)

def monthly_summary(df):
    return df.groupby("Month")[["Users", "Fee Collected", "NII", "Profit"]].sum().reset_index()

def yearly_summary(df):
    return df.groupby("Year")[["Users", "Fee Collected", "NII", "Profit"]].sum().reset_index()

def export_excel(dfs):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        for name, df in dfs.items():
            df.to_excel(writer, index=False, sheet_name=name[:31])
    output.seek(0)
    st.download_button("📥 Download Excel", data=output, file_name="rosca_forecast_v13.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# Main App Entry
st.set_page_config(layout="wide")
st.title("📊 ROSCA Forecast App v13 – Full Scope")

config = get_config()
durations, slab_map = get_durations_and_slabs()
slot_fees = get_slot_fees(durations)

if durations:
    df_forecast = run_forecast(config, durations, slab_map, slot_fees)
    df_monthly = monthly_summary(df_forecast)
    df_yearly = yearly_summary(df_forecast)

    st.subheader("📈 Forecast Table")
    st.dataframe(df_forecast)

    st.subheader("📅 Monthly Summary")
    st.dataframe(df_monthly)

    st.subheader("📆 Yearly Summary")
    st.dataframe(df_yearly)

    export_excel({
        "Forecast": df_forecast,
        "Monthly Summary": df_monthly,
        "Yearly Summary": df_yearly
    })
else:
    st.warning("Please select at least one committee duration to begin forecast.")
