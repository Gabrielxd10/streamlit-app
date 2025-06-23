import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64

# --- 1. Carregar dados ---
@st.cache_data
def load_data():
    arquivo = r'C:\Users\gabri\Desktop\Pasta Sistema\Planilha completa.xlsx'
    df = pd.read_excel(arquivo)
    
    # Conversão colunas numéricas
    cols_numericas = ['Consumo de materia natural_Cocho', 'Consumo_bebedouro', 'Peso médio']
    for col in cols_numericas:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '.').astype(float)
    
    # Converter data e limpar
    df['Data'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['Data'])
    
    # Função para tempo para minutos
    def tempo_para_minutos(t):
        if pd.isnull(t): return 0
        if isinstance(t, str):
            try:
                h,m,s = map(int, t.split(':'))
                return h*60 + m + s/60
            except: return 0
        elif hasattr(t, 'hour'):
            return t.hour*60 + t.minute + t.second/60
        else:
            return 0
    
    tempo_cols = ['tempo de consumo_bebedouro', 'Tempo de consumo_cocho']
    for col in tempo_cols:
        if col in df.columns:
            df[col + '_min'] = df[col].apply(tempo_para_minutos)
    
    # Ordenar e calcular dias permanência
    df = df.sort_values(['TAG', 'Data']).reset_index(drop=True)
    df['dias_permanencia'] = df.groupby('TAG')['Data'].transform(lambda x: (x - x.min()).dt.days)
    
    # Calcular ganho peso diário (GPD)
    if 'Peso médio' in df.columns:
        df['peso_anterior'] = df.groupby('TAG')['Peso médio'].shift(1)
        df['dias_diff'] = df.groupby('TAG')['dias_permanencia'].diff()
        df['GPD'] = (df['Peso médio'] - df['peso_anterior']) / df['dias_diff']
        df['GPD'] = df['GPD'].fillna(0)
    else:
        df['GPD'] = 0
    
    return df

df = load_data()

# --- Sidebar: filtros ---
st.sidebar.title("Filtros")

data_min = df['Data'].min()
data_max = df['Data'].max()

date_range = st.sidebar.date_input("Selecione intervalo de datas", [data_min, data_max])

if len(date_range) == 2:
    start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
else:
    start_date, end_date = data_min, data_max

df_filtered = df[(df['Data'] >= start_date) & (df['Data'] <= end_date)]

tags = df_filtered['TAG'].unique()
selected_tags = st.sidebar.multiselect("Selecione TAG(s)", options=tags, default=tags[:3])

if not selected_tags:
    st.warning("Selecione ao menos uma TAG para análise.")
    st.stop()

df_selected = df_filtered[df_filtered['TAG'].isin(selected_tags)]

# --- Estatísticas resumo ---
st.title("Análise de Consumo e Peso")

st.markdown(f"**Intervalo de datas selecionado:** {start_date.date()} até {end_date.date()}")
st.markdown(f"**TAGs selecionadas:** {', '.join(map(str, selected_tags))}")

def resumo_estatisticas(df):
    return pd.DataFrame({
        'Média': df.mean(),
        'Mediana': df.median(),
        'Desvio Padrão': df.std()
    }).T

colunas_analise = ['Consumo de materia natural_Cocho', 'Consumo_bebedouro', 'Peso médio', 'GPD']
resumo = df_selected.groupby('TAG')[colunas_analise].apply(resumo_estatisticas).unstack()

st.subheader("Estatísticas Resumo por TAG")
st.dataframe(resumo.style.format("{:.3f}"))

# --- Gráficos comparativos ---
st.subheader("Gráficos Comparativos")

def plot_evolucao_peso(df, tags):
    plt.figure(figsize=(10, 5))
    for tag in tags:
        dft = df[df['TAG'] == tag]
        plt.plot(dft['dias_permanencia'], dft['Peso médio'], marker='o', label=f'TAG {tag}')
    plt.title('Evolução do Peso Médio')
    plt.xlabel('Dias de permanência')
    plt.ylabel('Peso Médio (kg)')
    plt.legend()
    plt.grid(True)
    st.pyplot(plt.gcf())
    plt.close()

plot_evolucao_peso(df_selected, selected_tags)

def plot_consumo_vs_gpd(df, tags):
    plt.figure(figsize=(10,6))
    sns.scatterplot(data=df[df['TAG'].isin(tags)],
                    x='Consumo de materia natural_Cocho',
                    y='GPD',
                    hue='TAG',
                    palette='tab10',
                    s=100)
    plt.title('Consumo no Cocho vs Ganho de Peso Diário')
    plt.xlabel('Consumo Cocho (kg/dia)')
    plt.ylabel('Ganho de Peso Diário (kg)')
    plt.grid(True)
    st.pyplot(plt.gcf())
    plt.close()

plot_consumo_vs_gpd(df_selected, selected_tags)

# --- Gráficos extras: Histograma e Boxplot ---
st.subheader("Visualizações Extras")

st.markdown("Histograma do Ganho de Peso Diário (GPD)")
fig, ax = plt.subplots()
sns.histplot(df_selected, x='GPD', hue='TAG', multiple='stack', ax=ax)
st.pyplot(fig)
plt.close()

st.markdown("Boxplot do Consumo no Cocho")
fig2, ax2 = plt.subplots()
sns.boxplot(data=df_selected, x='TAG', y='Consumo de materia natural_Cocho', ax=ax2)
st.pyplot(fig2)
plt.close()

# --- Destaques: alertas GPD negativo ---
st.subheader("Alertas")

tags_gpd_negativo = df_selected[df_selected['GPD'] < 0]['TAG'].unique()
if len(tags_gpd_negativo) > 0:
    st.error(f"⚠️ Atenção! As TAGs {', '.join(map(str, tags_gpd_negativo))} apresentaram ganho de peso diário NEGATIVO em algum momento.")
else:
    st.success("Nenhuma TAG apresentou ganho de peso negativo.")

# --- Download dos dados filtrados e resumo ---
st.subheader("Download")

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Dados Filtrados')
    processed_data = output.getvalue()
    return processed_data

excel_data = to_excel(df_selected)

st.download_button(label="Download dados filtrados em Excel",
                   data=excel_data,
                   file_name='dados_filtrados.xlsx',
                   mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# --- Download gráfico peso evolução como imagem ---
def get_image_download_link(fig, filename, text):
    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode()
    href = f'<a href="data:file/png;base64,{b64}" download="{filename}">{text}</a>'
    return href

fig_peso = plt.figure(figsize=(10,5))
for tag in selected_tags:
    dft = df_selected[df_selected['TAG'] == tag]
    plt.plot(dft['dias_permanencia'], dft['Peso médio'], marker='o', label=f'TAG {tag}')
plt.title('Evolução do Peso Médio')
plt.xlabel('Dias de permanência')
plt.ylabel('Peso Médio (kg)')
plt.legend()
plt.grid(True)

st.markdown(get_image_download_link(fig_peso, 'evolucao_peso.png', 'Download gráfico Evolução do Peso (PNG)'), unsafe_allow_html=True)
plt.close(fig_peso)
