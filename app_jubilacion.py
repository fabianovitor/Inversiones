import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Mi Plan de Jubilación", layout="wide")

# --- CONEXIÓN ---
# He usado el ID que aparece en tus capturas
SHEET_ID = '1zgByQdqcNFUzXJmwbHu8TxxiLMzcD2CawB_ZEGOathU'
# Usamos el formato de exportación directa a CSV que es más estable
URL = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv'

@st.cache_data(ttl=600)
def load_data():
    try:
        # Forzamos a pandas a leerlo como CSV puro
        df = pd.read_csv(URL, on_bad_lines='skip') 
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except Exception as e:
        st.error(f"⚠️ Error de Acceso: Asegúrate de que la planilla esté compartida como 'Cualquier persona con el enlace'.")
        st.info(f"Detalle técnico: {e}")
        return None

st.title("🛡️ Dashboard de Jubilación")

df_raw = load_data()

if df_raw is not None and not df_raw.empty:
    df = df_raw.copy()
    
    # Validamos que existan las columnas para que no de KeyError
    columnas_base = ['Ticker', 'Cantidad', 'Precio Medio', 'Objetivo %']
    for col in columnas_base:
        if col not in df.columns:
            df[col] = 0

    # Sidebar
    if st.sidebar.button('Sincronizar Mercado 🚀'):
        with st.spinner('Conectando con Yahoo Finance...'):
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

    # Cálculos
    df['Valor_Total'] = pd.to_numeric(df['Precio_Actual'], errors='coerce') * pd.to_numeric(df['Cantidad'], errors='coerce')
    total = df['Valor_Total'].sum()
    df['% Real'] = (df['Valor_Total'] / total * 100) if total > 0 else 0

    # Dashboard
    st.metric("Patrimonio Total", f"${total:,.2f}")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("Análisis de Cartera")
        st.dataframe(df[['Ticker', 'Cantidad', 'Precio Medio', 'Precio_Actual', '% Real', 'Objetivo %']])
    with col2:
        st.subheader("Distribución")
        fig = px.pie(df, values='Valor_Total', names='Ticker', hole=0.3)
        st.plotly_chart(fig, use_container_width=True)

    st.plotly_chart(px.bar(df, x='Ticker', y=['Objetivo %', '% Real'], barmode='group'), use_container_width=True)
else:
    st.warning("No hay datos disponibles. Revisa los permisos de compartir en Google Sheets.")