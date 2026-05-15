import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title='Dashboard de Jubilación', layout='wide')

def load_data():
    data = {
        'Ticker': ['SCHD', 'VOO', 'QQQM', 'VXUS', 'O', 'VICI', 'WPC', 'STAG', 'EPRT', 'ADC', 'BSBR', 'BBSEY', 'PEP', 'ENB', 'MO', 'MAIN', 'ERIC-B'],
        'Objetivo_Pct': [25, 20, 10, 5, 5, 5, 4, 3, 4, 3, 3, 2, 3, 2, 3, 3, 25],
        'Precio_Compra': [31.80, 687.73, 296.37, 85.02, 61.96, 27.88, 73.69, 38.04, 30.58, 75.28, 5.45, 7.00, 148.67, 56.22, 72.41, 50.69, 12.61],
        'Cantidad': [34, 1.0194, 0.681, 3, 3, 10, 3, 3, 5, 2, 21, 21, 0, 0, 0, 0, 2.79]
    }
    return pd.DataFrame(data)

df = load_data()

st.sidebar.header('Actualización')
if st.sidebar.button('Actualizar Mercado'):
    with st.spinner('Cargando datos...'):
        prices, divs = [], []
        for t in df['Ticker']:
            try:
                s = yf.Ticker(t)
                prices.append(s.fast_info['lastPrice'])
                divs.append(s.info.get('trailingAnnualDividendRate', 0))
            except:
                prices.append(0); divs.append(0)
        df['Precio_Actual'] = prices
        df['Div_TTM'] = divs
else:
    df['Precio_Actual'] = df['Precio_Compra']
    df['Div_TTM'] = [2.85, 6.55, 1.27, 2.29, 3.15, 1.70, 4.40, 1.50, 1.12, 3.00, 0.44, 0.86, 5.20, 3.50, 3.80, 2.80, 0.40]

df['Valor_Total'] = df['Precio_Actual'] * df['Cantidad']
total_cartera = df['Valor_Total'].sum()
df['Pct_Actual'] = (df['Valor_Total'] / total_cartera) * 100
df['YOC'] = (df['Div_TTM'] / df['Precio_Compra']) * 100
df['Ingreso_Anual'] = df['Div_TTM'] * df['Cantidad']

st.title('🛡️ Dashboard de Jubilación')
st.metric('Valor Cartera', f'${total_cartera:,.2f}')

c1, c2 = st.columns(2)
with c1:
    st.plotly_chart(px.pie(df, values='Valor_Total', names='Ticker', hole=0.4), use_container_width=True)
with c2:
    fig = go.Figure(data=[go.Bar(name='Obj', x=df['Ticker'], y=df['Objetivo_Pct']), go.Bar(name='Act', x=df['Ticker'], y=df['Pct_Actual'])])
    st.plotly_chart(fig, use_container_width=True)

st.write(df)