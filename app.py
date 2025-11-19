import streamlit as st
import pandas as pd
from influxdb_client import InfluxDBClient
import plotly.express as px
import math

# --- Configuración de conexión ---
INFLUXDB_URL = "https://us-east-1-1.aws.cloud2.influxdata.com"
INFLUXDB_TOKEN = "JcKXoXE30JQvV9Ggb4-zv6sQc0Zh6B6Haz5eMRW0FrJEduG2KcFJN9-7RoYvVORcFgtrHR-Q_ly-52pD7IC6JQ=="  # ⚠️ No subir el token real a GitHub
INFLUXDB_ORG = "0925ccf91ab36478"
INFLUXDB_BUCKET = "EXTREME_MANUFACTURING"

client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
query_api = client.query_api()

# --- Interfaz de usuario ---
st.set_page_config(page_title="Umi 🌱", layout="wide")

st.title("¡Bienvenido a Umi 🌱!")
st.write("Umi te da una visualización de los datos más importantes para tu cultivo en casa en tiempo real.")

sensor = st.selectbox("Selecciona el sensor:", ["DHT22", "MPU6050"])

col_start, col_stop = st.columns(2)
with col_start:
    start = st.slider(
        "Selecciona el rango de tiempo de inicio (start, días hacia atrás):",
        min_value=1, max_value=15, value=15
    )

with col_stop:
    stop = st.slider(
        "Selecciona el rango de tiempo de finalización (stop, días hacia atrás):",
        min_value=1, max_value=14, value=5
    )

# Aseguramos que start > stop para que el rango en Influx tenga sentido
if start <= stop:
    st.warning("El valor de *start* debe ser mayor que *stop*. Corrigiendo automáticamente.")
    start, stop = stop, start

# --- Consulta dinámica ---
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

# --- Limpieza de datos ---
if df.empty:
    st.warning("⚠️ No se encontraron datos para el rango seleccionado.")
    st.stop()

df = df[["_time", "_field", "_value"]]
df = df.rename(columns={"_time": "Tiempo", "_field": "Variable", "_value": "Valor"})
df["Tiempo"] = pd.to_datetime(df["Tiempo"])

# --- Métricas de último valor ---
st.subheader("📊 Últimos valores registrados")

# Tomamos el último valor en el tiempo para cada variable
last_values = (
    df.sort_values("Tiempo")
      .groupby("Variable")
      .tail(1)
      .set_index("Variable")["Valor"]
)

cols = st.columns(min(4, len(last_values)))  # hasta 4 métricas por fila
for i, (var, val) in enumerate(last_values.items()):
    with cols[i % len(cols)]:
        st.metric(label=var, value=f"{val:.2f}")

# Si es MPU6050 calculamos aceleración total como indicador extra
accel_total = None
if sensor == "MPU6050" and all(a in last_values for a in ["accel_x", "accel_y", "accel_z"]):
    ax = last_values["accel_x"]
    ay = last_values["accel_y"]
    az = last_values["accel_z"]
    accel_total = math.sqrt(ax**2 + ay**2 + az**2)
    st.info(f"Aceleración total actual: **{accel_total:.2f}** (unidad relativa)")

# --- Alertas básicas ---
st.subheader("🚨 Alertas")

if sensor == "DHT22":
    temp = last_values.get("temperatura", None)
    hum = last_values.get("humedad", None)

    if temp is not None:
        if temp > 30:
            st.error("🔥 Temperatura alta para tu cultivo.")
        elif temp < 15:
            st.warning("❄️ Temperatura baja, el crecimiento puede ser más lento.")

    if hum is not None:
        if hum < 40:
            st.warning("💧 Humedad baja, podría resecarse el sustrato.")
        elif hum > 80:
            st.warning("💦 Humedad muy alta, riesgo de hongos.")

else:  # MPU6050
    if accel_total is not None and accel_total > 2:  # umbral ejemplo
        st.warning("⚠️ Movimiento / vibración inusual detectada en el cultivo.")

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

# Resumen estadístico (útil para el informe)
with st.expander("Ver resumen estadístico de los datos"):
    st.dataframe(df.groupby("Variable")["Valor"].describe())


