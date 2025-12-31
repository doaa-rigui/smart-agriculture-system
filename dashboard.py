"""
Smart Agriculture Dashboard - Frontend
Streamlit-based user interface for farmers
"""

import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:8000"

st.set_page_config(page_title="Smart Agriculture Dashboard", layout="wide")

# Title
st.title("🌱 Smart Agriculture Decision Support System")

# Sidebar - Sensor Simulator
st.sidebar.header("📊 Sensor Input Simulator")
st.sidebar.write("Simulate IoT sensor readings:")

soil_moisture = st.sidebar.slider("Soil Moisture (%)", 0, 100, 50)
temperature = st.sidebar.slider("Temperature (°C)", -10, 50, 25)
humidity = st.sidebar.slider("Humidity (%)", 0, 100, 60)

if st.sidebar.button("Submit Sensor Data"):
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/sensors/data",
            json={
                "soil_moisture": soil_moisture,
                "temperature": temperature,
                "humidity": humidity
            }
        )
        if response.status_code == 201:
            st.sidebar.success("✅ Data submitted successfully!")
        else:
            st.sidebar.error(f"❌ Error: {response.status_code}")
    except Exception as e:
        st.sidebar.error(f"❌ Connection error: {e}")

# Main Dashboard - Current Sensor Data
col1, col2, col3 = st.columns(3)

try:
    response = requests.get(f"{API_BASE_URL}/api/sensors/latest")
    if response.status_code == 200:
        latest_data = response.json()
        
        with col1:
            st.metric(
                label="💧 Soil Moisture",
                value=f"{latest_data['soil_moisture']:.1f}%"
            )
        
        with col2:
            st.metric(
                label="🌡️ Temperature",
                value=f"{latest_data['temperature']:.1f}°C"
            )
        
        with col3:
            st.metric(
                label="💨 Humidity",
                value=f"{latest_data['humidity']:.1f}%"
            )
        
        st.caption(f"Last updated: {latest_data['timestamp']}")
    else:
        st.warning("No sensor data available. Submit readings using the sidebar.")
except Exception as e:
    st.error(f"Cannot connect to backend: {e}")

st.divider()

# Recommendations Section
st.header("💡 Recommendations")

try:
    response = requests.get(f"{API_BASE_URL}/api/recommendations")
    if response.status_code == 200:
        recommendations = response.json()
        
        for rec in recommendations:
            rec_type = rec['type']
            
            # Color based on urgency
            if rec_type == "irrigation":
                if "immediately" in rec['action'].lower():
                    st.error(f"🚨 **{rec['action']}**")
                elif "stop" in rec['action'].lower():
                    st.warning(f"⚠️ **{rec['action']}**")
                else:
                    st.info(f"ℹ️ **{rec['action']}**")
            elif rec_type == "fertilization":
                st.success(f"🌿 **{rec['action']}**")
            else:
                st.info(f"✅ **{rec['action']}**")
            
            with st.expander("📖 Why this recommendation?"):
                st.write(rec['reason'])
                st.caption(f"Confidence: {rec['confidence']*100:.0f}% | Generated: {rec['timestamp']}")
    else:
        st.warning("No recommendations available.")
except Exception as e:
    st.error(f"Cannot fetch recommendations: {e}")

st.divider()

# Historical Data
st.header("📈 Sensor History")

try:
    response = requests.get(f"{API_BASE_URL}/api/sensors/history?limit=50")
    if response.status_code == 200:
        history_data = response.json()
        history = history_data['data']
        
        if history:
            df = pd.DataFrame(history)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Line chart
            st.line_chart(df.set_index('timestamp')[['soil_moisture', 'temperature', 'humidity']])
            
            # Data table
            with st.expander("View Raw Data"):
                st.dataframe(df, use_container_width=True)
        else:
            st.info("No historical data yet.")
except Exception as e:
    st.error(f"Cannot fetch history: {e}")

# Footer
st.divider()
st.caption("Smart Agriculture System v1.0 | Vibe Coding Lab Project")
