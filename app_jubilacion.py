import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Estrategia de Jubilación Pro", layout="wide")

# --- CONFIGURACIÓN DE CONEXIÓN ---
SHEET_ID = '1zgByQdqcNFUzXJmwbHu8TxxiLMzcD2CawB_ZEGOathU'
URL = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv'

@st.cache_data(ttl=300)
def load_data():
    try:
        df = pd.read_csv(URL)
        df.columns = [str(c).strip() for c in df.columns]
        
        # LIMPIEZA NUMÉRICA RADICAL (Para asegurar cálculos exactos)
        cols_a_limpiar = ['Cantidad', 'Precio Medio', 'Objetivo %']
        for col in cols_a_limpiar:
            if col in df.columns:
                # Quitamos todo lo que no sea número o punto decimal
                df[col] = df[col].astype(str).str.replace(r'[^0-9.]', '', regex=True)
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        
        return df
    except Exception as e:
        st.error(f"Error al leer datos: {e}")
        return None

st.title("🛡️ Dashboard de Jubilación - Precisión 4D")

df_raw = load_data()

if df_raw is not None:
    df = df_raw.copy()

    # --- MOTOR DE PRECIOS ---
    if st.sidebar.button('Sincronizar con Mercado 🚀'):
        with st.spinner('Obteniendo precios de Yahoo Finance...'):
            precios = []
            for t in df['Ticker']:
                try:
                    tk = str(t).replace('.B', '-B') # Ajuste para ERIC-B
                    val = yf.Ticker(tk).fast_info['lastPrice']
                    precios.append(val)
                except:
                    precios.append(0.0)
            df['Precio_Actual'] = precios
    else:
        # Por defecto usamos el precio medio para evitar valores en cero
        df['Precio_Actual'] = df['Precio Medio']

    # --- CÁLCULOS DE PRECISIÓN (4 DECIMALES) ---
    df['Valor_Mercado'] = (df['Precio_Actual'] * df['Cantidad']).round(4)
    total_patrimonio = df['Valor_Mercado'].sum()
    
    # Calculamos el % Real basado en el valor actual de mercado
    if total_patrimonio > 0:
        df['% Real'] = ((df['Valor_Mercado'] / total_patrimonio) * 100).round(4)
    else:
        df['% Real'] = 0.0

    # DIFERENCIA: Si sale negativa es que falta comprar, si es positiva sobra.
    df['Dif %'] = (df['% Real'] - df['Objetivo %']).round(4)

    # --- MÉTRICAS ---
    m1, m2, m3 = st.columns(3)
    m1.metric("Patrimonio Total", f"${total_patrimonio:,.4f}")
    m2.metric("Desviación Media", f"{df['Dif %'].abs().mean():,.4f}%")
    m3.metric("Activos en Cartera", len(df))

    st.markdown("---")

    # --- TABLA CON FORMATO DE 4 DECIMALES ---
    st.subheader("📊 Análisis de Rebalanceo y Desviación")
    
    # Formateamos la visualización de la tabla
    df_display = df[['Ticker', 'Cantidad', 'Precio Medio', 'Precio_Actual', 'Objetivo %', '% Real', 'Dif %']]
    
    def color_diferencia(val):
        color = '#d4edda' if val >= 0 else '#f8d7da' # Verde si sobra/cumple, Rojo si falta
        return f'background-color: {color}'

    st.dataframe(
        df_display.style.format({
            'Cantidad': '{:.4f}',
            'Precio Medio': '${:.4f}',
            'Precio_Actual': '${:.4f}',
            'Objetivo %': '{:.4f}%',
            '% Real': '{:.4f}%',
            'Dif %': '{:.4f}%'
        }).applymap(color_diferencia, subset=['Dif %']),
        use_container_width=True
    )

    # --- GRÁFICO DE BARRAS ---
    fig = go.Figure(data=[
        go.Bar(name='Meta %', x=df['Ticker'], y=df['Objetivo %'], marker_color='#E5E7EB'),
        go.Bar(name='Real %', x=df['Ticker'], y=df['% Real'], marker_color='#1E40AF')
    ])
    fig.update_layout(
        title="Comparativa Meta vs Realidad (Escala 100%)",
        barmode='group',
        yaxis_title="Porcentaje (%)",
        height=500
    )
    st.plotly_chart(fig, use_container_width=True)

else:
    st.warning("Verifica que la hoja de cálculo esté publicada y el enlace sea correcto.")