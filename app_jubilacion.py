import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re

st.set_page_config(page_title="Estrategia Jubilación Pro", layout="wide")

# --- LIGACIÓN CON GOOGLE SHEETS ---
SHEET_ID = '1zgByQdqcNFUzXJmwbHu8TxxiLMzcD2CawB_ZEGOathU'
URL = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv'

def clean_numeric(value):
    """Limpia cualquier carácter no numérico excepto el punto decimal."""
    if pd.isna(value) or value == '': return 0.0
    # Elimina todo excepto números y el último punto/coma
    cleaned = re.sub(r'[^0-9,.]', '', str(value))
    if not cleaned: return 0.0
    # Si detecta formato brasileño/europeo (coma como decimal) tras el cambio
    if ',' in cleaned and '.' not in cleaned:
        cleaned = cleaned.replace(',', '.')
    elif ',' in cleaned and '.' in cleaned: # Caso 1,234.56
        cleaned = cleaned.replace(',', '')
    return float(cleaned)

@st.cache_data(ttl=300)
def load_data():
    try:
        df = pd.read_csv(URL)
        df.columns = [str(c).strip() for c in df.columns]
        
        # Aplicamos la limpieza ultra-segura a cada celda
        for col in ['Cantidad', 'Precio Medio', 'Objetivo %']:
            if col in df.columns:
                df[col] = df[col].apply(clean_numeric)
        return df
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None

st.title("🛡️ Dashboard de Jubilación - Precisión 4D")

df_raw = load_data()

if df_raw is not None:
    df = df_raw.copy()

    # --- ACTUALIZACIÓN DE MERCADO ---
    if st.sidebar.button('Sincronizar Mercado 🚀'):
        with st.spinner('Consultando Yahoo Finance...'):
            precios = []
            for t in df['Ticker']:
                try:
                    tk = str(t).replace('.B', '-B')
                    val = yf.Ticker(tk).fast_info['lastPrice']
                    precios.append(val)
                except:
                    precios.append(0.0)
            df['Precio_Actual'] = precios
    else:
        # Por defecto, usamos el precio medio para que los cálculos no den cero
        df['Precio_Actual'] = df['Precio Medio']

    # --- CÁLCULOS MAESTROS ---
    # 1. Valor de cada posición
    df['Valor_Posicion'] = (df['Precio_Actual'] * df['Cantidad']).round(4)
    
    # 2. Patrimonio Total Real
    total_patrimonio = df['Valor_Posicion'].sum()
    
    # 3. % Real (Evitando división por cero)
    if total_patrimonio > 0:
        df['% Real'] = ((df['Valor_Posicion'] / total_patrimonio) * 100).round(4)
    else:
        df['% Real'] = 0.0

    # 4. Diferencia Real (Meta vs Realidad)
    df['Dif %'] = (df['% Real'] - df['Objetivo %']).round(4)

    # --- MÉTRICAS PRINCIPALES ---
    m1, m2, m3 = st.columns(3)
    m1.metric("Patrimonio Total", f"${total_patrimonio:,.4f}")
    m2.metric("Nº de Activos", len(df))
    m3.metric("Estado de Cartera", "Equilibrada" if abs(df['Dif %'].mean()) < 1 else "Rebalancear")

    st.markdown("---")

    # --- TABLA DE CONTROL ---
    st.subheader("📊 Análisis de Desviación")
    
    df_display = df[['Ticker', 'Cantidad', 'Precio Medio', 'Precio_Actual', 'Valor_Posicion', 'Objetivo %', '% Real', 'Dif %']]
    
    def style_dif(val):
        # Rojo si falta comprar (negativo), Verde si ya llegaste o te pasaste (positivo)
        color = '#f8d7da' if val < -0.1 else '#d4edda'
        return f'background-color: {color}'

    st.dataframe(
        df_display.style.format({
            'Cantidad': '{:.4f}',
            'Precio Medio': '${:.4f}',
            'Precio_Actual': '${:.4f}',
            'Valor_Posicion': '${:.2f}',
            'Objetivo %': '{:.4f}%',
            '% Real': '{:.4f}%',
            'Dif %': '{:.4f}%'
        }).applymap(style_dif, subset=['Dif %']),
        use_container_width=True
    )

    # --- GRÁFICOS ---
    fig = go.Figure(data=[
        go.Bar(name='Mi Meta %', x=df['Ticker'], y=df['Objetivo %'], marker_color='#CBD5E1'),
        go.Bar(name='Mi Realidad %', x=df['Ticker'], y=df['% Real'], marker_color='#1E40AF')
    ])
    fig.update_layout(title="Alineación de Estrategia", barmode='group', height=450)
    st.plotly_chart(fig, use_container_width=True)

else:
    st.warning("Asegúrate de que tu Google Sheet tenga el acceso compartido correctamente.")