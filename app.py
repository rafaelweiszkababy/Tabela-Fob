import streamlit as st
import pandas as pd
import sqlite3
import os

# Configuração da página
st.set_page_config(page_title="Simulador de Importação & PDV", layout="wide")

st.title("🚢 Simulador de Importação & Preço de Venda (PDV)")
st.write("Preencha os dados abaixo para calcular os preços recomendados e salvar no banco de dados.")

# --- BANCO DE DADOS (SQLite) ---
DB_FILE = "historico_produtos.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS calculos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_calculo TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            nome_produto TEXT,
            fob_usd REAL,
            qtd INTEGER,
            peso_kg REAL,
            comprimento_cm REAL,
            largura_cm REAL,
            altura_cm REAL,
            ml_classico_pdv REAL,
            ml_premium_pdv REAL,
            shopee_pdv REAL,
            amazon_pdv REAL,
            magalu_pdv REAL
        )
    ''')
    conn.commit()
    conn.close()

def salvar_no_banco(nome, fob, qtd, peso, comp, larg, alt, resultados_dict):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO calculos (
            nome_produto, fob_usd, qtd, peso_kg, comprimento_cm, largura_cm, altura_cm,
            ml_classico_pdv, ml_premium_pdv, shopee_pdv, amazon_pdv, magalu_pdv
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        nome, fob, qtd, peso, comp, larg, alt,
        resultados_dict.get('Mercado Livre Clássico'),
        resultados_dict.get('Mercado Livre Premium'),
        resultados_dict.get('Shopee'),
        resultados_dict.get('Amazon'),
        resultados_dict.get('Magalu')
    ))
    conn.commit()
    conn.close()

def carregar_historico():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM calculos ORDER BY id DESC", conn)
    conn.close()
    return df

def deletar_registro(id_registro):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM calculos WHERE id = ?", (id_registro,))
    conn.commit()
    conn.close()

# Inicializa o banco de dados
init_db()

# --- REGRAS DE NEGÓCIO E FRETE ---
st.sidebar.header("⚙️ Configurações Globais")
taxa_cambio = st.sidebar.number_input("Taxa de Câmbio (USD/BRL)", value=5.30, step=0.05)
frete_maritimo = st.sidebar.number_input("Frete Marítimo Total (USD)", value=5000.0, step=100.0)
margem_alvo = st.sidebar.number_input("Margem Alvo (%)", value=21.9, step=0.1) / 100.0

WEIGHT_ROWS = [0.3, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 13.0, 17.0, 23.0, 30.0, 40.0]
EXCEL_ML_TABLE_VALUES = [
    22.55, 23.65, 24.65, 24.65, 26.25, 28.35, 30.75, 39.75, 44.05, 48.05,
    49.35, 68.65, 70.25, 105.95, 106.95, 107.05, 110.75
]

def get_frete_ml_matriz(peso_tarifa):
    w_idx = 0
    for i, w in enumerate(WEIGHT_ROWS):
        if peso_tarifa >= w:
            w_idx = i
    return EXCEL_ML_TABLE_VALUES[w_idx]

FRETE_ML_G1_TABELA = [
    (0.3, 19.95), (0.5, 20.45), (1.0, 21.45), (2.0, 22.95), (3.0, 23.95),
    (4.0, 24.95), (5.0, 25.95), (9.0, 41.95), (13.0, 65.95), (17.0, 73.45),
    (23.0, 85.95), (30.0, 98.95), (40.0, 109.45), (999.0, 116.95)
]

def get_frete_ml_g1(peso):
    for limite, valor in FRETE_ML_G1_TABELA:
        if peso <= limite:
            return valor
    return 116.95

def calcular_pdv(fob, qtd, comp, larg, alt, peso_fisico):
    peso_cubado = (comp * larg * alt) / 6000.0
    peso_tarifa = max(peso_fisico, peso_cubado)
    frete_g1 = get_frete_ml_g1(peso_tarifa)
    
    valor_fob_total = fob * qtd * taxa_cambio
    frete_brl = frete_maritimo * taxa_cambio
    valor_aduaneiro = valor_fob_total + frete_brl + 80.0
    
    ii = 0.20 * valor_aduaneiro
    ipi = 0.0325 * (valor_aduaneiro + ii)
    pis = 0.0210 * valor_aduaneiro
    cofins = 0.0965 * valor_aduaneiro
    
    thc = 998.0
    siscomex = 154.23
    afrmm = 0.08 * (frete_brl + thc) + 21.20
    despesas_log = afrmm + 1900.0 + thc + 1800.0 + 650.0 + (50.0 * taxa_cambio) + 4000.0 + siscomex
    icms_imp = (valor_aduaneiro + ii + ipi + pis + cofins + afrmm + siscomex) / (1 - 0.18) * 0.18
    
    total_importacao = valor_aduaneiro + ii + ipi + pis + cofins + icms_imp + despesas_log
    custo_base = (total_importacao - pis - cofins - ipi - icms_imp) / qtd
    fixed_base = custo_base + 2.0
    
    canais = [
        ('Mercado Livre Clássico', 0.115),
        ('Mercado Livre Premium', 0.165),
        ('Shopee', 0.14),
        ('Amazon', 0.12),
        ('Magalu', 0.18)
    ]
    
    resultados = []
    valores_pdv_dict = {}
    for canal, tx_mkt in canais:
        pdv = 300.0
        for _ in range(20):
            if 'Mercado Livre' in canal:
                frete_ml = get_frete_ml_matriz(peso_tarifa)
                j = -frete_ml - 5.0
            elif canal == 'Shopee':
                j = -31.0
            elif canal == 'Amazon':
                j = -5.5 - frete_g1
            elif canal == 'Magalu':
                j = -5.0 - frete_g1
                
            denom = (1.0 - tx_mkt - 0.0925 - 0.18 - margem_alvo)
            pdv = (fixed_base - j) / denom
            
        lucro = pdv * margem_alvo
        valores_pdv_dict[canal] = round(pdv, 2)
        resultados.append({
            "Marketplace": canal,
            "Comissão": f"{tx_mkt*100:.1f}%",
            "Frete / Taxa Fixa": f"R$ {j:.2f}",
            "PDV Recomendado": f"R$ {pdv:.2f}",
            "Lucro Unitário": f"R$ {lucro:.2f}",
            "Margem Resultante": f"{margem_alvo*100:.1f}%"
        })
    return resultados, valores_pdv_dict

# --- NAVEGAÇÃO POR ABAS ---
tab1, tab2 = st.tabs(["🧮 Novo Cálculo", "🗄️ Banco de Dados / Histórico"])

with tab1:
    with st.form("form_produto"):
        col1, col2, col3 = st.columns(3)
        with col1:
            nome_prod = st.text_input("Nome/Código do Produto", value=None, placeholder="Ex: Produto X")
            fob_val = st.number_input("Preço FOB (USD)", min_value=0.0, value=None, step=0.5, placeholder="Ex: 12.50")
        with col2:
            qtd_val = st.number_input("Quantidade no Container", min_value=0, value=None, step=50, placeholder="Ex: 5000")
            peso_val = st.number_input("Peso Físico (kg)", min_value=0.0, value=None, step=0.5, placeholder="Ex: 2.5")
        with col3:
            comp_val = st.number_input("Comprimento (cm)", min_value=0.0, value=None, step=1.0, placeholder="Ex: 20")
            larg_val = st.number_input("Largura (cm)", min_value=0.0, value=None, step=1.0, placeholder="Ex: 15")
            alt_val = st.number_input("Altura (cm)", min_value=0.0, value=None, step=1.0, placeholder="Ex: 10")
            
        submitted = st.form_submit_button("Calcular e Salvar no Banco")

    if submitted:
        if not nome_prod or not fob_val or not qtd_val or not peso_val or not comp_val or not larg_val or not alt_val:
            st.error("Preencha todos os campos obrigatórios para realizar o cálculo.")
        elif fob_val <= 0 or qtd_val <= 0 or peso_val <= 0 or comp_val <= 0 or larg_val <= 0 or alt_val <= 0:
            st.error("Os valores informados devem ser maiores que zero.")
        else:
            res_tabela, pdv_dict = calcular_pdv(fob_val, qtd_val, comp_val, larg_val, alt_val, peso_val)
            
            # Salva automaticamente no banco de dados SQLite
            salvar_no_banco(nome_prod, fob_val, qtd_val, peso_val, comp_val, larg_val, alt_val, pdv_dict)
            
            st.success(f"Cálculo realizado e produto '{nome_prod}' salvo com sucesso no banco de dados!")
            st.subheader(f"Tabela de PDV — Produto: {nome_prod}")
            st.table(res_tabela)

with tab2:
    st.subheader("📦 Produtos Gravados no Banco de Dados")
    df_historico = carregar_historico()
    
    if df_historico.empty:
        st.info("Nenhum produto cadastrado no banco de dados até o momento.")
    else:
        # Renomear colunas para apresentação
        df_display = df_historico.rename(columns={
            "id": "ID",
            "data_calculo": "Data",
            "nome_produto": "Produto",
            "fob_usd": "FOB ($)",
            "qtd": "Qtd Container",
            "peso_kg": "Peso (kg)",
            "comprimento_cm": "Comp (cm)",
            "largura_cm": "Larg (cm)",
            "altura_cm": "Alt (cm)",
            "ml_classico_pdv": "ML Clássico (R$)",
            "ml_premium_pdv": "ML Premium (R$)",
            "shopee_pdv": "Shopee (R$)",
            "amazon_pdv": "Amazon (R$)",
            "magalu_pdv": "Magalu (R$)"
        })
        
        st.dataframe(df_display, use_container_width=True)
        
        # Botão para Baixar CSV
        csv = df_display.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Baixar Histórico em CSV / Excel",
            data=csv,
            file_name="historico_simulacoes_pdv.csv",
            mime="text/csv"
        )
        
        st.divider()
        st.subheader("🗑️ Gerenciar Registros")
        
        col_del1, col_del2 = st.columns([2, 1])
        with col_del1:
            id_para_deletar = st.number_input("Digite o ID do produto que deseja excluir:", min_value=1, step=1)
        with col_del2:
            st.write("")
            st.write("")
            if st.button("Excluir Produto"):
                deletar_registro(id_para_deletar)
                st.warning(f"Registro ID {id_para_deletar} removido com sucesso!")
                st.rerun()
