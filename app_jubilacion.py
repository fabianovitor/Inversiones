import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Mi Plan de Jubilación", layout="wide")

# --- CONEXIÓN DIRECTA ---
SHEET_ID = '1zgByQdqcNFUzXJmwbHu8TxxiLMzcD2CawB_ZEGOathU'
URL = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Hoja1'

@st.cache_data(ttl=600)
def load_data():
    try:
        df = pd.read_csv(URL)
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except:
        return None

st.title("🛡️ Dashboard de Jubilación")

df = load_data()

if df is not None:
    # 1. Asegurar que las columnas existan con nombres básicos
    for col in ['Ticker', 'Cantidad', 'Precio Medio', 'Objetivo %']:
        if col not in df.columns:
            df[col] = 0

    # 2. Obtener precios de Yahoo Finance solo si se presiona el botón
    if st.sidebar.button('Actualizar Mercado'):
        precios = []
        for t in df['Ticker']:
            try:
                tk = str(t).split(':')[-1] if ':' in str(t) else str(t)
                precios.append(yf.Ticker(tk).fast_info['lastPrice'])
            except:
                precios.append(0)
        df['Precio_Actual'] = precios
    else:
        df['Precio_Actual'] = df['Precio Medio']

    # 3. Cálculos Simples
    df['Valor_Total'] = df['Precio_Actual'] * df['Cantidad']
    total = df['Valor_Total'].sum()
    df['% Actual'] = (df['Valor_Total'] / total * 100) if total > 0 else 0
    df['Dif %'] = df['% Actual'] - df['Objetivo %']

    # 4. Métricas principales
    st.metric("Patrimonio Total", f"${total:,.2f}")

    # 5. Tabla de datos (Sin estilos complejos para evitar errores)
    st.subheader("Estado de la Cartera")
    st.dataframe(df[['Ticker', 'Cantidad', 'Precio Medio', 'Precio_Actual', '% Actual', 'Objetivo %', 'Dif %']])

    # 6. Gráfico de Rebalanceo
    fig = px.bar(df, x='Ticker', y=['Objetivo %', '% Actual'], barmode='group', title="Meta vs Real")
    st.plotly_chart(fig, use_container_width=True)

else:
    st.error("No se pudo leer la planilla. Revisa que el ID sea correcto y esté pública.")