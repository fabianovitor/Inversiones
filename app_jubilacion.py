import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re

st.set_page_config(page_title="Estrategia Jubilación Pro", layout="wide")

SHEET_ID = '1zgByQdqcNFUzXJmwbHu8TxxiLMzcD2CawB_ZEGOathU'
URL = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv'

def force_numeric(x):
    """Extrae solo los números y maneja el caos de puntos y comas."""
    if pd.isna(x) or x == '': return 0.0
    # Quitamos todo lo que no sea dígito
    s = re.sub(r'[^0-9]', '', str(x))
    if not s: return 0.0
    val = float(s)
    # Si el número es enorme (ej. 250000 para un 25%), lo ajustamos
    # Esta es una técnica para normalizar datos mal importados
    if val > 100000: val = val / 10000 # Caso de importación tipo 25.0000
    elif val > 1000: val = val / 100    # Caso de importación tipo 25,00
    return val

@st.cache_data(ttl=300)
def load_data():
    try:
        df = pd.read_csv(URL)
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        df.columns = [str(c).strip() for c in df.columns]
        
        # Limpieza profunda
        df['Cantidad'] = df['Cantidad'].apply(force_numeric)
        df['Precio Medio'] = df['Precio Medio'].apply(force_numeric) / 100 # Ajuste para moneda
        df['Objetivo %'] = df['Objetivo %'].apply(force_numeric)
        
        # FILTRO: Solo posiciones abiertas
        df = df[df['Cantidad'] > 0].copy()
        return df
    except:
        return None

st.title("🛡️ Dashboard de Jubilación - Precisión Final")

df = load_data()

if df is not None:
    # --- PRECIOS ---
    if st.sidebar.button('Actualizar Mercado 🚀'):
        precios = []
        for t in df['Ticker']:
            try:
                tk = str(t).replace('.B', '-B')
                val = yf.Ticker(tk).fast_info['lastPrice']
                precios.append(val)
            except: precios.append(0.0)
        df['Precio_Actual'] = precios
    else:
        df['Precio_Actual'] = df['Precio Medio']

    # --- LÓGICA DE EXCLUSIÓN ERIC-B ---
    df['Valor_Posicion'] = (df['Precio_Actual'] * df['Cantidad'])
    
    # Portafolio Estándar (Sin ERIC-B)
    df_std = df[df['Ticker'] != 'ERIC-B'].copy()
    total_std = df_std['Valor_Posicion'].sum()
    
    # Calculamos % Real solo para los que no son ERIC-B
    def calc_pct(row):
        if row['Ticker'] == 'ERIC-B' or total_std == 0:
            return 0.0
        return (row['Valor_Posicion'] / total_std) * 100

    df['% Real'] = df.apply(calc_pct, axis=1)
    df['Dif %'] = (df['% Real'] - df['Objetivo %'])

    # --- MÉTRICAS ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Patrimonio Estándar", f"${total_std:,.2f}")
    c2.metric("Valor ERIC-B", f"${df[df['Ticker']=='ERIC-B']['Valor_Posicion'].sum():,.2f}")
    c3.metric("Activos", len(df))

    # --- TABLA ---
    st.subheader("📊 Análisis de Precisión")
    
    def style_dif(val):
        # Rojo si falta comprar (negativo), Verde si ya cumpliste (positivo)
        color = '#f8d7da' if val < -0.1 else '#d4edda'
        return f'background-color: {color}'

    st.dataframe(
        df[['Ticker', 'Cantidad', 'Precio Medio', 'Precio_Actual', 'Objetivo %', '% Real', 'Dif %']].style.format({
            'Cantidad': '{:.4f}', 'Precio Medio': '${:.4f}', 'Precio_Actual': '${:.4f}',
            'Objetivo %': '{:.4f}%', '% Real': '{:.4f}%', 'Dif %': '{:.4f}%'
        }).applymap(style_dif, subset=['Dif %']),
        use_container_width=True
    )

    # --- GRÁFICO ---
    st.plotly_chart(px.bar(df[df['Ticker'] != 'ERIC-B'], x='Ticker', y=['Objetivo %', '% Real'], 
                           barmode='group', title="Cumplimiento de Estrategia (Sin ERIC-B)"), 
                    use_container_width=True)
else:
    st.warning("Cargando datos...")