import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

# --- 1. Carregar dados ---

arquivo = r'C:\Users\gabri\Desktop\Pasta Sistema\Planilha completa.xlsx'
df = pd.read_excel(arquivo)

print("Colunas do arquivo:")
print(df.columns)

# --- 2. Converter colunas numéricas ---

cols_numericas = ['Consumo de materia natural_Cocho', 'Consumo_bebedouro', 'Peso médio']
for col in cols_numericas:
    if col in df.columns:
        df[col] = df[col].astype(str).str.replace(',', '.').astype(float)
    else:
        print(f"Aviso: coluna '{col}' não encontrada.")

# --- 3. Converter coluna Data para datetime, com tratamento de erros ---

df['Data'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce')
num_datas_invalidas = df['Data'].isna().sum()
print(f"Datas inválidas (NaT): {num_datas_invalidas}")

# Remove linhas com data inválida
df = df.dropna(subset=['Data'])

# --- 4. Função para converter tempo (HH:MM:SS) para minutos ---

def tempo_para_minutos(t):
    if pd.isnull(t):
        return 0
    if isinstance(t, str):
        try:
            h, m, s = map(int, t.split(':'))
            return h*60 + m + s/60
        except:
            return 0
    elif hasattr(t, 'hour') and hasattr(t, 'minute') and hasattr(t, 'second'):
        return t.hour * 60 + t.minute + t.second / 60
    else:
        return 0

tempo_cols = ['tempo de consumo_bebedouro', 'Tempo de consumo_cocho']
for col in tempo_cols:
    if col in df.columns:
        df[col + '_min'] = df[col].apply(tempo_para_minutos)
    else:
        print(f"Aviso: coluna '{col}' não encontrada para conversão de tempo.")

# --- 5. Ordenar por TAG e Data e calcular dias de permanência ---

if 'TAG' not in df.columns:
    raise KeyError("Coluna 'TAG' não encontrada no DataFrame.")

df = df.sort_values(['TAG', 'Data']).reset_index(drop=True)
df['dias_permanencia'] = df.groupby('TAG')['Data'].transform(lambda x: (x - x.min()).dt.days)

# --- 6. Calcular ganho de peso diário (GPD) ---

if 'Peso médio' in df.columns:
    df['peso_anterior'] = df.groupby('TAG')['Peso médio'].shift(1)
    df['dias_diff'] = df.groupby('TAG')['dias_permanencia'].diff()
    df['GPD'] = (df['Peso médio'] - df['peso_anterior']) / df['dias_diff']
    df['GPD'] = df['GPD'].fillna(0)
else:
    print("Coluna 'Peso médio' não encontrada, pulando cálculo de GPD.")
    df['GPD'] = 0

# --- 7. Filtrar dados a partir de uma data (exemplo: 01/05/2023) ---

data_inicio = pd.to_datetime('2023-05-01')
df = df[df['Data'] >= data_inicio]

if df.empty:
    raise ValueError("DataFrame está vazio após filtro por data. Verifique os dados e filtro.")

# --- 8. Criar resumo por TAG ---

colunas_resumo = {
    'Consumo de materia natural_Cocho': 'consumo_cocho_kg_dia',
    'Consumo_bebedouro': 'consumo_bebedouro_l_dia',
    'Numero de visitar com consumo_Cocho': 'visitas_cocho',
    'Numero de visitas_Bebedouro': 'visitas_bebedouro',
    'Tempo de consumo_cocho_min': 'tempo_cocho_min',
    'tempo de consumo_bebedouro_min': 'tempo_bebedouro_min',
    'Peso médio': 'peso_medio',
    'GPD': 'ganho_peso_diario'
}

# Ajustar para colunas com nomes exatos
colunas_existentes = {}
for k, v in colunas_resumo.items():
    if k in df.columns:
        colunas_existentes[k] = v
    elif k.lower() in (c.lower() for c in df.columns):  # ignorar case
        # encontra a coluna com case insensitive
        col_found = [c for c in df.columns if c.lower() == k.lower()][0]
        colunas_existentes[col_found] = v

resumo = df.groupby('TAG').agg({k: 'mean' for k in colunas_existentes.keys()}).rename(columns=colunas_existentes).reset_index()

print("Resumo por TAG:")
print(resumo.head())

# --- 9. Visualização exemplo: evolução peso médio de um animal ---

tag_exemplo = resumo['TAG'].iloc[0]
df_tag = df[df['TAG'] == tag_exemplo]

plt.figure(figsize=(10, 5))
plt.plot(df_tag['dias_permanencia'], df_tag['Peso médio'], marker='o')
plt.title(f'Evolução do Peso Médio - TAG {tag_exemplo}')
plt.xlabel('Dias de permanência')
plt.ylabel('Peso Médio (kg)')
plt.grid(True)
plt.show()

# --- 10. Salvar resumo em Excel ---

os.makedirs('resultado', exist_ok=True)
resumo.to_excel('resultado/resumo_por_tag.xlsx', index=False)
print("Resumo salvo em 'resultado/resumo_por_tag.xlsx'")

# --- 11. Salvar gráfico exemplo ---

plt.figure(figsize=(10, 5))
plt.plot(df_tag['dias_permanencia'], df_tag['Peso médio'], marker='o')
plt.title(f'Evolução do Peso Médio - TAG {tag_exemplo}')
plt.xlabel('Dias de permanência')
plt.ylabel('Peso Médio (kg)')
plt.grid(True)
plt.tight_layout()
plt.savefig('resultado/evolucao_peso_tag_exemplo.png')
plt.close()
print("Gráfico salvo em 'resultado/evolucao_peso_tag_exemplo.png'")

# --- 12. Visualização consumo vs ganho de peso (scatter) ---

plt.figure(figsize=(10, 6))
sns.scatterplot(data=resumo, x='consumo_cocho_kg_dia', y='ganho_peso_diario', hue='TAG', legend=False)
plt.title('Consumo no Cocho vs Ganho de Peso Diário')
plt.xlabel('Consumo Cocho (kg/dia)')
plt.ylabel('Ganho de Peso Diário (kg)')
plt.tight_layout()
plt.savefig('resultado/consumo_vs_ganho_peso.png')
plt.close()
print("Gráfico salvo em 'resultado/consumo_vs_ganho_peso.png'")

# --- 13. GRÁFICOS EXTRAS PARA ANÁLISE COMPLETA ---

# Gráfico 1: Consumo de Cocho por TAG (barras)
plt.figure(figsize=(12, 6))
sns.barplot(data=resumo, x='TAG', y='consumo_cocho_kg_dia')
plt.title('Consumo de Cocho por TAG (kg/dia)')
plt.xlabel('TAG')
plt.ylabel('Consumo Cocho (kg/dia)')
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig('resultado/consumo_cocho_por_tag.png')
plt.close()

# Gráfico 2: Consumo Bebedouro por TAG (barras)
plt.figure(figsize=(12, 6))
sns.barplot(data=resumo, x='TAG', y='consumo_bebedouro_l_dia')
plt.title('Consumo Bebedouro por TAG (litros/dia)')
plt.xlabel('TAG')
plt.ylabel('Consumo Bebedouro (litros/dia)')
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig('resultado/consumo_bebedouro_por_tag.png')
plt.close()

# Gráfico 3: Tempo médio de consumo no Cocho por TAG (barras)
plt.figure(figsize=(12, 6))
sns.barplot(data=resumo, x='TAG', y='tempo_cocho_min')
plt.title('Tempo Médio de Consumo no Cocho por TAG (minutos)')
plt.xlabel('TAG')
plt.ylabel('Tempo Consumo Cocho (minutos)')
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig('resultado/tempo_cocho_por_tag.png')
plt.close()

# Gráfico 4: Tempo médio de consumo no Bebedouro por TAG (barras)
plt.figure(figsize=(12, 6))
sns.barplot(data=resumo, x='TAG', y='tempo_bebedouro_min')
plt.title('Tempo Médio de Consumo no Bebedouro por TAG (minutos)')
plt.xlabel('TAG')
plt.ylabel('Tempo Consumo Bebedouro (minutos)')
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig('resultado/tempo_bebedouro_por_tag.png')
plt.close()

# Gráfico 5: Ganho de peso diário por TAG (barras)
plt.figure(figsize=(12, 6))
sns.barplot(data=resumo, x='TAG', y='ganho_peso_diario')
plt.title('Ganho de Peso Diário por TAG (kg/dia)')
plt.xlabel('TAG')
plt.ylabel('Ganho de Peso Diário (kg/dia)')
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig('resultado/ganho_peso_diario_por_tag.png')
plt.close()

# Gráfico 6: Visitas ao Cocho vs Visitas ao Bebedouro (scatter)
if 'visitas_cocho' in resumo.columns and 'visitas_bebedouro' in resumo.columns:
    plt.figure(figsize=(10, 6))
    sns.scatterplot(data=resumo, x='visitas_cocho', y='visitas_bebedouro', hue='TAG', legend=False)
    plt.title('Visitas ao Cocho vs Visitas ao Bebedouro')
    plt.xlabel('Visitas ao Cocho')
    plt.ylabel('Visitas ao Bebedouro')
    plt.tight_layout()
    plt.savefig('resultado/visitas_cocho_vs_bebedouro.png')
    plt.close()

print("Gráficos extras salvos na pasta 'resultado'")
