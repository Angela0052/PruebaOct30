import streamlit as st
import pandas as pd
from influxdb_client import InfluxDBClient
import plotly.express as px
import math

# --- Config general ---
st.set_page_config(page_title="Umi 🌱", page_icon="🌱", layout="wide")

# --- Conexión InfluxDB ---
INFLUXDB_URL = "https://us-east-1-1.aws.cloud2.influxdata.com"
INFLUXDB_TOKEN = "TU_TOKEN_AQUI"  # pon el del profe acá
INFLUXDB_ORG = "0925ccf91ab36478"
INFLUXDB_BUCKET = "EXTREME_MANUFACTURING"

client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
query_api = client.query_api()

# --- Sidebar ---
with st.sidebar:
    st.title("Umi 🌱")
    st.caption("Monitoreo de tu cultivo en casa")

    sensor = st.selectbox("Sensor:", ["DHT22", "MPU6050"])

    start = st.slider("Inicio (días hacia atrás):", 1, 15, 15)
    stop = st.slider("Fin (días hacia atrás):", 1, 15, 9)

# asegurar rango coherente
if start <= stop:
    start, stop = stop, start

# --- Título principal ---
st.title("Panel de datos de tu cultivo")
st.write("Visualización de temperatura, humedad y movimiento a partir de InfluxDB.")

# --- Query según sensor ---
if sensor == "DHT22":
    measurement = "studio-dht22"
    fields_filter = '''
        r._field == "humedad" or
        r._field == "temperatura" or
        r._field == "sensacion_termica"
    '''
else:
    measurement = "mpu6050"
    fields_filter = '''
        r._field == "accel_x" or r._field == "accel_y" or r._field == "accel_z" or
        r._field == "gyro_x" or r._field == "gyro_y" or r._field == "gyro_z" or
        r._field == "temperature"
    '''

query = f'''
from(bucket: "{INFLUXDB_BUCKET}")
  |> range(start: -{start}d, stop: -{stop}d)
  |> filter(fn: (r) => r._measurement == "{measurement}")
  |> filter(fn: (r) => {fields_filter})
'''

# --- Cargar datos ---
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

# --- Últimos valores (para alertas) ---
last_values = (
    df.sort_values("Tiempo")
      .groupby("Variable")
      .tail(1)
      .set_index("Variable")["Valor"]
)

st.subheader("🚨 Alertas")

if sensor == "DHT22":
    temp = last_values.get("temperatura")
    hum = last_values.get("humedad")

    if temp is not None:
        if temp > 30:
            st.error("🔥 Temperatura alta para tu cultivo.")
        elif temp < 15:
            st.warning("❄️ Temperatura baja para un crecimiento óptimo.")

    if hum is not None:
        if hum < 40:
            st.warning("💧 Humedad baja, revisa el riego.")
        elif hum > 80:
            st.warning("💦 Humedad muy alta, posible riesgo de hongos.")
else:
    accel_total = None
    if all(v in last_values for v in ["accel_x", "accel_y", "accel_z"]):
        ax = last_values["accel_x"]
        ay = last_values["accel_y"]
        az = last_values["accel_z"]
        accel_total = math.sqrt(ax**2 + ay**2 + az**2)

    if accel_total is not None and accel_total > 2:
        st.warning("⚠️ Movimiento / vibración inusual detectada.")
    elif accel_total is not None:
        st.info("✅ Sin vibraciones fuertes detectadas.")

# --- Gráficos ---
st.subheader("📈 Visualización de variables")

for var in df["Variable"].unique():
    sub_df = df[df["Variable"] == var]
    fig = px.line(
        sub_df,
        x="Tiempo",
        y="Valor",
        title=var,
        template="plotly_dark"  # combina con tema oscuro si lo usas
    )
    st.plotly_chart(fig, use_container_width=True)

# --- Resumen estadístico ---
with st.expander("Ver resumen estadístico"):
    st.dataframe(df.describe())

