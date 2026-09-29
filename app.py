import streamlit as st
import pandas as pd
import requests

# Configuração da página
st.set_page_config(page_title="Simulador de Importação & PDV", layout="wide")

# URL do seu Google Apps Script
URL_GOOGLE_SHEETS = "https://script.google.com/macros/s/AKfycbxrylmS1PozdeKeYqCgfhzuCAd8H8sxiEW_vQwFtMzI4nqykh3ApJmH-DkIs2sv1suW/exec"

st.title("🚢 Simulador de Importação & Preço de Venda (PDV)")
st.write("Conectado ao Google Sheets para persistência permanente dos dados.")

def salvar_no_google_sheets(fabrica, nome, fob, qtd, peso, comp, larg, alt, resultados_dict):
    if not URL_GOOGLE_SHEETS or "SUA_URL" in URL_GOOGLE_SHEETS:
        st.warning("Insira a URL do seu Google Apps Script no código para salvar na planilha.")
        return False
        
    payload = {
        "fabrica": fabrica,
        "nome_produto": nome,
        "fob_usd": fob,
        "qtd": qtd,
        "peso_kg": peso,
        "comprimento_cm": comp,
        "largura_cm": larg,
        "altura_cm": alt,
        "ml_classico_pdv": resultados_dict.get('Mercado Livre Clássico'),
        "ml_premium_pdv": resultados_dict.get('Mercado Livre Premium'),
        "shopee_pdv": resultados_dict.get('Shopee'),
        "amazon_pdv": resultados_dict.get('Amazon'),
        "magalu_pdv": resultados_dict.get('Magalu')
    }
    try:
        res = requests.post(URL_GOOGLE_SHEETS, json=payload, allow_redirects=True)
        return res.status_code == 200
    except Exception as e:
        st.error(f"Erro ao salvar no Google Sheets: {e}")
        return False

def carregar_do_google_sheets():
    if not URL_GOOGLE_SHEETS or "SUA_URL" in URL_GOOGLE_SHEETS:
        return pd.DataFrame()
    try:
        res = requests.get(URL_GOOGLE_SHEETS, allow_redirects=True)
        if res.status_code == 200:
            try:
                data = res.json()
                if isinstance(data, list) and len(data) > 1:
                    headers = data[0]
                    rows = data[1:]
                    df = pd.DataFrame(rows, columns=headers)
                    return df.iloc[::-1]  # Inverte para mostrar os mais recentes primeiro
            except Exception:
                st.warning("Aguardando permissão do Google Apps Script. Verifique se o acesso está configurado como 'Qualquer pessoa'.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao carregar do Google Sheets: {e}")
        return pd.DataFrame()

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

def get_taxas_canal(canal, peso_tarifa, frete_g1):
    if canal == 'Mercado Livre Clássico':
        tx_mkt = 0.115
        frete_ml = get_frete_ml_matriz(peso_tarifa)
        j = -frete_ml - 5.0
    elif canal == 'Mercado Livre Premium':
        tx_mkt = 0.165
        frete_ml = get_frete_ml_matriz(peso_tarifa)
        j = -frete_ml - 5.0
    elif canal == 'Shopee':
        tx_mkt = 0.14
        j = -31.0
    elif canal == 'Amazon':
        tx_mkt = 0.12
        j = -5.5 - frete_g1
    elif canal == 'Magalu':
        tx_mkt = 0.18
        j = -5.0 - frete_g1
    return tx_mkt, j

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
    
    canais_nomes = ['Mercado Livre Clássico', 'Mercado Livre Premium', 'Shopee', 'Amazon', 'Magalu']
    resultados = []
    valores_pdv_dict = {}
    
    for canal in canais_nomes:
        tx_mkt, j = get_taxas_canal(canal, peso_tarifa, frete_g1)
        pdv = 300.0
        for _ in range(20):
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

def calcular_fob_inverso(pdv_alvo, canal_ref, qtd, comp, larg, alt, peso_fisico):
    peso_cubado = (comp * larg * alt) / 6000.0
    peso_tarifa = max(peso_fisico, peso_cubado)
    frete_g1 = get_frete_ml_g1(peso_tarifa)
    
    tx_mkt, j = get_taxas_canal(canal_ref, peso_tarifa, frete_g1)
    
    denom = (1.0 - tx_mkt - 0.0925 - 0.18 - margem_alvo)
    fixed_base = (pdv_alvo * denom) + j
    custo_base = fixed_base - 2.0
    
    frete_brl = frete_maritimo * taxa_cambio
    thc = 998.0
    siscomex = 154.23
    afrmm = 0.08 * (frete_brl + thc) + 21.20
    despesas_log = afrmm + 1900.0 + thc + 1800.0 + 650.0 + (50.0 * taxa_cambio) + 4000.0 + siscomex
    
    custo_total_base = custo_base * qtd
    valor_aduaneiro = (custo_total_base - despesas_log) / 1.20
    fob_total_brl = valor_aduaneiro - frete_brl - 80.0
    fob_usd_max = fob_total_brl / (qtd * taxa_cambio)
    
    return max(0.0, fob_usd_max)

# --- NAVEGAÇÃO POR ABAS ---
tab1, tab2, tab3 = st.tabs(["🧮 Cálculo Direto (FOB → PDV)", "🔄 Cálculo Inverso (PDV → FOB)", "📊 Histórico Google Sheets"])

with tab1:
    st.subheader("Calcular PDV Recomendado por Marketplace")
    with st.form("form_produto_direto"):
        col1, col2, col3 = st.columns(3)
        with col1:
            fabrica_prod = st.text_input("Fábrica", value=None, placeholder="Ex: Fornecedor A")
            nome_prod = st.text_input("Nome/Código do Produto", value=None, placeholder="Ex: Produto X")
            fob_val = st.number_input("Preço FOB (USD)", min_value=0.0, value=None, step=0.5, placeholder="Ex: 12.50")
        with col2:
            qtd_val = st.number_input("Quantidade no Container", min_value=0, value=None, step=50, placeholder="Ex: 5000")
            peso_val = st.number_input("Peso Físico (kg)", min_value=0.0, value=None, step=0.5, placeholder="Ex: 2.5")
        with col3:
            comp_val = st.number_input("Comprimento (cm)", min_value=0.0, value=None, step=1.0, placeholder="Ex: 20")
            larg_val = st.number_input("Largura (cm)", min_value=0.0, value=None, step=1.0, placeholder="Ex: 15")
            alt_val = st.number_input("Altura (cm)", min_value=0.0, value=None, step=1.0, placeholder="Ex: 10")
            
        submitted_direto = st.form_submit_button("Calcular e Salvar na Planilha")

    if submitted_direto:
        if not fabrica_prod or not nome_prod or not fob_val or not qtd_val or not peso_val or not comp_val or not larg_val or not alt_val:
            st.error("Preencha todos os campos obrigatórios para realizar o cálculo.")
        elif fob_val <= 0 or qtd_val <= 0 or peso_val <= 0 or comp_val <= 0 or larg_val <= 0 or alt_val <= 0:
            st.error("Os valores informados devem ser maiores que zero.")
        else:
            res_tabela, pdv_dict = calcular_pdv(fob_val, qtd_val, comp_val, larg_val, alt_val, peso_val)
            ok = salvar_no_google_sheets(fabrica_prod, nome_prod, fob_val, qtd_val, peso_val, comp_val, larg_val, alt_val, pdv_dict)
            if ok:
                st.success(f"Cálculo realizado e salvo na planilha do Google Sheets com sucesso!")
            st.subheader(f"Tabela de PDV — Produto: {nome_prod} ({fabrica_prod})")
            st.table(res_tabela)

with tab2:
    st.subheader("Descobrir o Preço FOB Máximo a partir do PDV Desejado")
    with st.form("form_produto_inverso"):
        col1, col2, col3 = st.columns(3)
        with col1:
            fabrica_inv = st.text_input("Fábrica", value=None, placeholder="Ex: Fornecedor A", key="fab_inv")
            nome_inv = st.text_input("Nome/Código do Produto", value=None, placeholder="Ex: Produto X", key="nome_inv")
            pdv_alvo_val = st.number_input("PDV Desejado (R$)", min_value=0.0, value=None, step=5.0, placeholder="Ex: 150.00")
            canal_ref = st.selectbox("Marketplace de Referência", ['Mercado Livre Clássico', 'Mercado Livre Premium', 'Shopee', 'Amazon', 'Magalu'])
        with col2:
            qtd_inv = st.number_input("Quantidade no Container", min_value=0, value=None, step=50, placeholder="Ex: 5000", key="qtd_inv")
            peso_inv = st.number_input("Peso Físico (kg)", min_value=0.0, value=None, step=0.5, placeholder="Ex: 2.5", key="peso_inv")
        with col3:
            comp_inv = st.number_input("Comprimento (cm)", min_value=0.0, value=None, step=1.0, placeholder="Ex: 20", key="comp_inv")
            larg_inv = st.number_input("Largura (cm)", min_value=0.0, value=None, step=1.0, placeholder="Ex: 15", key="larg_inv")
            alt_inv = st.number_input("Altura (cm)", min_value=0.0, value=None, step=1.0, placeholder="Ex: 10", key="alt_inv")
            
        submitted_inverso = st.form_submit_button("Calcular Preço FOB Máximo")

    if submitted_inverso:
        if not fabrica_inv or not nome_inv or not pdv_alvo_val or not qtd_inv or not peso_inv or not comp_inv or not larg_inv or not alt_inv:
            st.error("Preencha todos os campos obrigatórios.")
        elif pdv_alvo_val <= 0 or qtd_inv <= 0 or peso_inv <= 0 or comp_inv <= 0 or larg_inv <= 0 or alt_inv <= 0:
            st.error("Os valores informados devem ser maiores que zero.")
        else:
            fob_calculado = calcular_fob_inverso(pdv_alvo_val, canal_ref, qtd_inv, comp_inv, larg_inv, alt_inv, peso_inv)
            
            st.metric(label=f"💵 Preço FOB Máximo Recomendado ({fabrica_inv} - {nome_inv})", value=f"USD ${fob_calculado:.2f}")
            st.info(f"Com o preço FOB de **USD ${fob_calculado:.2f}**, você consegue vender no **{canal_ref}** por **R$ {pdv_alvo_val:.2f}** mantendo a margem de {margem_alvo*100:.1f}%.")
            
            res_tabela, pdv_dict = calcular_pdv(fob_calculado, qtd_inv, comp_inv, larg_inv, alt_inv, peso_inv)
            salvar_no_google_sheets(fabrica_inv, nome_inv, round(fob_calculado, 2), qtd_inv, peso_inv, comp_inv, larg_inv, alt_inv, pdv_dict)
            
            st.subheader("Projeção de PDV para todos os Marketplaces com esse FOB:")
            st.table(res_tabela)

with tab3:
    st.subheader("📊 Registros Gravados no Google Sheets")
    df_sheets = carregar_do_google_sheets()
    
    if df_sheets.empty:
        st.info("Nenhum registro encontrado ou a URL do Google Apps Script ainda não foi configurada.")
    else:
        st.dataframe(df_sheets, use_container_width=True)
        
        csv = df_sheets.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Baixar Histórico em CSV / Excel",
            data=csv,
            file_name="historico_simulacoes_pdv.csv",
            mime="text/csv"
        )
