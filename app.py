import streamlit as st
import pandas as pd
from influxdb_client import InfluxDBClient
import plotly.express as px
import math

# --- Configuración general de la página ---
st.set_page_config(
    page_title="Umi 🌱",
    page_icon="🌱",
    layout="wide"
)

st.markdown("""
    <style>
    /* Fondo principal de la app */
    .main {
        background-color: #0b1116;   /* cambia este color de fondo */
        color: #ffffff;              /* color de texto principal */
    }

    /* Sidebar (barra lateral) */
    section[data-testid="stSidebar"] {
        background-color: #141a1f;   /* color de fondo del sidebar */
    }


    /* Sliders */
    .stSlider > div > div > div {
        background: #ff6b6b;  /* color de la barrita del slider */
    }
    </style>
""", unsafe_allow_html=True)

# --- Configuración de conexión ---
INFLUXDB_URL = "https://us-east-1-1.aws.cloud2.influxdata.com"
INFLUXDB_TOKEN = "JcKXoXE30JQvV9Ggb4-zv6sQc0Zh6B6Haz5eMRW0FrJEduG2KcFJN9-7RoYvVORcFgtrHR-Q_ly-52pD7IC6JQ=="  
INFLUXDB_ORG = "0925ccf91ab36478"
INFLUXDB_BUCKET = "EXTREME_MANUFACTURING"

client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
query_api = client.query_api()

# --- SIDEBAR: selección de sensor y rango de tiempo ---
with st.sidebar:
    st.title("Umi 🌱")
    st.caption("Configura la visualización de tus sensores")

    sensor = st.selectbox("Selecciona el sensor:", ["DHT22", "MPU6050"])

    start = st.slider(
        "Rango de tiempo de inicio (start, días hacia atrás):",
        min_value=1, max_value=15, value=15
    )

    stop = st.slider(
        "Rango de tiempo de finalización (stop, días hacia atrás):",
        min_value=1, max_value=15, value=9
    )

# Nos aseguramos que start > stop para que Influx no se rompa
if start <= stop:
    start, stop = stop, start


st.title("¡Bienvenido a Umi 🌱!")
st.write("Umi te da una visualización de los datos más importantes para tu cultivo en casa en tiempo real")


if sensor == "DHT22":
    query = f'''
    from(bucket: "{INFLUXDB_BUCKET}")
        |> range(start: -{start}d, stop: -{stop}d)
        |> filter(fn: (r) => r._measurement == "studio-dht22")
        |> filter(fn: (r) => r._field == "humedad" or r._field == "temperatura" or r._field == "sensacion_termica")
    '''
else:
    query = f'''
    from(bucket: "{INFLUXDB_BUCKET}")
        |> range(start: -{start}d, stop: -{stop}d)
        |> filter(fn: (r) => r._measurement == "mpu6050")
        |> filter(fn: (r) =>
            r._field == "accel_x" or r._field == "accel_y" or r._field == "accel_z" or
            r._field == "gyro_x" or r._field == "gyro_y" or r._field == "gyro_z" or
            r._field == "temperature")
    '''


try:
    df = query_api.query_data_frame(org=INFLUXDB_ORG, query=query)
    if isinstance(df, list):
        df = pd.concat(df)
except Exception as e:
    st.error(f"Error al cargar datos: {e}")
    st.stop()


if df.empty:
    st.warning("⚠️ No se encontraron datos para el rango seleccionado.")
    st.stop()

df = df[["_time", "_field", "_value"]]
df = df.rename(columns={"_time": "Tiempo", "_field": "Variable", "_value": "Valor"})
df["Tiempo"] = pd.to_datetime(df["Tiempo"])


last_values = (
    df.sort_values("Tiempo")
      .groupby("Variable")
      .tail(1)
      .set_index("Variable")["Valor"]
)


st.subheader("🚨 Alertas para tu cultivo")

if sensor == "DHT22":
    temp = last_values.get("temperatura", None)
    hum = last_values.get("humedad", None)

    if temp is not None:
        if temp > 30:
            st.error("🔥 Temperatura alta para tu cultivo.")
        elif temp < 15:
            st.warning("❄️ Temperatura baja, el crecimiento puede ser más lento.")
        else:
            st.success("🌡️ Temperatura dentro de un rango adecuado.")

    if hum is not None:
        if hum < 40:
            st.warning("💧 Humedad baja, revisa el riego.")
        elif hum > 80:
            st.warning("💦 Humedad muy alta, riesgo de hongos.")
        else:
            st.success("💧 Humedad en un nivel saludable.")
else:
  
    accel_total = None
    if all(k in last_values for k in ["accel_x", "accel_y", "accel_z"]):
        ax = last_values["accel_x"]
        ay = last_values["accel_y"]
        az = last_values["accel_z"]
        accel_total = math.sqrt(ax**2 + ay**2 + az**2)

    if accel_total is not None and accel_total > 2:  # umbral ejemplo
        st.warning("⚠️ Movimiento / vibración inusual detectada en la maceta.")
    elif accel_total is not None:
        st.success("✅ No se detectan vibraciones fuertes en este momento.")

# --- Gráficos ---
st.subheader("📈 Visualización de variables")

for var in df["Variable"].unique():
    sub_df = df[df["Variable"] == var]
    fig = px.line(
        sub_df,
        x="Tiempo",
        y="Valor",
        title=f"{var}",
        template="plotly_dark"  
    )
    st.plotly_chart(fig, use_container_width=True)
    
st.subheader("📊 Resumen estadístico")
st.dataframe(df.describe())
