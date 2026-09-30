import streamlit as st
import pandas as pd
import requests

# Configuração da página
st.set_page_config(page_title="Simulador de Importação & PDV", layout="wide")

# URL do Google Apps Script
URL_GOOGLE_SHEETS = "https://script.google.com/macros/s/AKfycbxry1mS1PozdeKeYqCgfhzuCAd8H8sxiEW_vQwFtMzI4nqykh3ApJmH-DkIs2sv1suW/exec"

st.title("🚢 Simulador de Importação & Preço de Venda (PDV)")
st.write("Conectado ao Google Sheets para persistência permanente dos dados.")

# --- FUNÇÕES DE RESET DE FORMULÁRIO ---
def reset_tab1():
    st.session_state["fab_dir"] = None
    st.session_state["nome_dir"] = None
    st.session_state["fob_dir"] = None
    st.session_state["qtd_dir"] = None
    st.session_state["peso_dir"] = None
    st.session_state["comp_dir"] = None
    st.session_state["larg_dir"] = None
    st.session_state["alt_dir"] = None

def reset_tab2():
    st.session_state["fab_inv"] = None
    st.session_state["nome_inv"] = None
    st.session_state["pdv_inv"] = None
    st.session_state["qtd_inv"] = None
    st.session_state["peso_inv"] = None
    st.session_state["comp_inv"] = None
    st.session_state["larg_inv"] = None
    st.session_state["alt_inv"] = None

# --- INTEGRAÇÃO GOOGLE SHEETS ---
def salvar_no_google_sheets(fabrica, nome, fob, qtd, peso, comp, larg, alt, resultados_dict):
    payload = {
        "fabrica": fabrica,
        "nome_produto": nome,
        "fob_usd": round(fob, 2),
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

def deletar_do_google_sheets(row_index):
    payload = {
        "action": "delete",
        "row_index": int(row_index)
    }
    try:
        res = requests.post(URL_GOOGLE_SHEETS, json=payload, allow_redirects=True)
        return res.status_code == 200
    except Exception as e:
        st.error(f"Erro ao deletar no Google Sheets: {e}")
        return False

def carregar_do_google_sheets():
    try:
        res = requests.get(URL_GOOGLE_SHEETS, allow_redirects=True)
        if res.status_code == 200:
            try:
                data = res.json()
                if isinstance(data, list) and len(data) > 1:
                    headers = ["ID"] + data[0]
                    rows = []
                    for idx, row in enumerate(data[1:], start=2):
                        rows.append([idx] + row)
                    df = pd.DataFrame(rows, columns=headers)
                    return df.iloc[::-1]
            except Exception:
                st.warning("Verifique se o Google Apps Script está configurado com permissão de acesso para 'Qualquer pessoa'.")
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

# --- MÓDULO EXCLUSIVO REVISADO: MERCADO LIVRE CLÁSSICO E PREMIUM ---
def calcular_taxas_mercado_livre(canal, peso_tarifa):
    """
    Módulo dedicado e isolado para o cálculo exato do Mercado Livre (Clássico e Premium).
    - Clássico: Comissão de 11.5% + Frete de Matriz + R$ 5.00 de taxa fixa
    - Premium: Comissão de 16.5% + Frete de Matriz + R$ 5.00 de taxa fixa
    """
    frete_ml = get_frete_ml_matriz(peso_tarifa)
    
    if canal == 'Mercado Livre Clássico':
        comissao = 0.115
    elif canal == 'Mercado Livre Premium':
        comissao = 0.165
    else:
        raise ValueError("Canal inválido para o módulo do Mercado Livre.")
        
    # Custos operacionais e logísticos agrupados (j)
    j_despesa = -frete_ml - 5.0
    return comissao, j_despesa

def get_taxas_canal(canal, peso_tarifa, frete_g1):
    if canal in ['Mercado Livre Clássico', 'Mercado Livre Premium']:
        return calcular_taxas_mercado_livre(canal, peso_tarifa)
    elif canal == 'Shopee':
        return 0.14, -31.0
    elif canal == 'Amazon':
        return 0.12, -5.5 - frete_g1
    elif canal == 'Magalu':
        return 0.18, -5.0 - frete_g1
    return 0.0, 0.0

# --- CÁLCULO DIRETO (FOB -> PDV) ---
def calcular_pdv(fob, qtd, comp, larg, alt, peso_fisico, cambio, frete_mar, margem):
    peso_cubado = (comp * larg * alt) / 6000.0
    peso_tarifa = max(peso_fisico, peso_cubado)
    frete_g1 = get_frete_ml_g1(peso_tarifa)
    
    valor_fob_total = fob * qtd * cambio
    frete_brl = frete_mar * cambio
    valor_aduaneiro = valor_fob_total + frete_brl + 80.0
    
    ii = 0.20 * valor_aduaneiro
    ipi = 0.0325 * (valor_aduaneiro + ii)
    pis = 0.0210 * valor_aduaneiro
    cofins = 0.0965 * valor_aduaneiro
    
    thc = 998.0
    siscomex = 154.23
    afrmm = 0.08 * (frete_brl + thc) + 21.20
    despesas_log = afrmm + 1900.0 + thc + 1800.0 + 650.0 + (50.0 * cambio) + 4000.0 + siscomex
    icms_imp = (valor_aduaneiro + ii + ipi + pis + cofins + afrmm + siscomex) / (1 - 0.18) * 0.18
    
    total_importacao = valor_aduaneiro + ii + ipi + pis + cofins + icms_imp + despesas_log
    custo_base = (total_importacao - pis - cofins - ipi - icms_imp) / qtd
    fixed_base = custo_base + 2.0
    
    canais_nomes = ['Mercado Livre Clássico', 'Mercado Livre Premium', 'Shopee', 'Amazon', 'Magalu']
    resultados = []
    valores_pdv_dict = {}
    
    for canal in canais_nomes:
        tx_mkt, j = get_taxas_canal(canal, peso_tarifa, frete_g1)
        denom = (1.0 - tx_mkt - 0.0925 - 0.18 - margem)
        pdv = (fixed_base - j) / denom
        
        lucro = pdv * margem
        valores_pdv_dict[canal] = round(pdv, 2)
        resultados.append({
            "Marketplace": canal,
            "Comissão": f"{tx_mkt*100:.1f}%",
            "Frete / Taxa Fixa": f"R$ {j:.2f}",
            "PDV Recomendado": f"R$ {pdv:.2f}",
            "Lucro Unitário": f"R$ {lucro:.2f}",
            "Margem Resultante": f"{margem*100:.1f}%"
        })
    return resultados, valores_pdv_dict

# --- CÁLCULO INVERSO (PDV -> TARGET FOB) ---
def calcular_fob_inverso(pdv_alvo, canal_ref, qtd, comp, larg, alt, peso_fisico, cambio, frete_mar, margem):
    peso_cubado = (comp * larg * alt) / 6000.0
    peso_tarifa = max(peso_fisico, peso_cubado)
    frete_g1 = get_frete_ml_g1(peso_tarifa)
    
    tx_mkt, j = get_taxas_canal(canal_ref, peso_tarifa, frete_g1)
    
    denom = (1.0 - tx_mkt - 0.0925 - 0.18 - margem)
    fixed_base = (pdv_alvo * denom) + j
    custo_base = fixed_base - 2.0
    
    frete_brl = frete_mar * cambio
    thc = 998.0
    siscomex = 154.23
    afrmm = 0.08 * (frete_brl + thc) + 21.20
    despesas_log = afrmm + 1900.0 + thc + 1800.0 + 650.0 + (50.0 * cambio) + 4000.0 + siscomex
    
    custo_total_base = custo_base * qtd
    valor_aduaneiro = (custo_total_base - despesas_log) / 1.20
    fob_total_brl = valor_aduaneiro - frete_brl - 80.0
    fob_usd_max = fob_total_brl / (qtd * cambio)
    
    return max(0.0, fob_usd_max)

# --- NAVEGAÇÃO POR ABAS ---
tab1, tab2, tab3 = st.tabs(["🧮 Cálculo Direto (FOB → PDV)", "🔄 Cálculo Inverso (PDV → FOB)", "📊 Histórico Google Sheets"])

with tab1:
    st.subheader("Calcular PDV Recomendado por Marketplace")
    with st.form("form_produto_direto"):
        col1, col2, col3 = st.columns(3)
        with col1:
            fabrica_prod = st.text_input("Fábrica (Opcional)", value=None, key="fab_dir")
            nome_prod = st.text_input("Nome/Código do Produto (Opcional)", value=None, key="nome_dir")
            fob_val = st.number_input("Preço FOB (USD)", min_value=0.0, value=None, step=0.5, key="fob_dir")
        with col2:
            qtd_val = st.number_input("Quantidade no Container", min_value=0, value=None, step=50, key="qtd_dir")
            peso_val = st.number_input("Peso Físico (kg)", min_value=0.0, value=None, step=0.5, key="peso_dir")
        with col3:
            comp_val = st.number_input("Comprimento (cm)", min_value=0.0, value=None, step=1.0, key="comp_dir")
            larg_val = st.number_input("Largura (cm)", min_value=0.0, value=None, step=1.0, key="larg_dir")
            alt_val = st.number_input("Altura (cm)", min_value=0.0, value=None, step=1.0, key="alt_dir")
            
        btn_col1, btn_col2 = st.columns([3, 1])
        with btn_col1:
            submitted_direto = st.form_submit_button("Calcular e Salvar na Planilha")
        with btn_col2:
            st.form_submit_button("🧹 Limpar Campos", on_click=reset_tab1)

    if submitted_direto:
        if not fob_val or not qtd_val or not peso_val or not comp_val or not larg_val or not alt_val:
            st.error("Preencha todos os campos numéricos obrigatórios para realizar o cálculo.")
        elif fob_val <= 0 or qtd_val <= 0 or peso_val <= 0 or comp_val <= 0 or larg_val <= 0 or alt_val <= 0:
            st.error("Os valores numéricos devem ser maiores que zero.")
        else:
            fab_final = fabrica_prod.strip() if (fabrica_prod and fabrica_prod.strip()) else "Não informada"
            nome_final = nome_prod.strip() if (nome_prod and nome_prod.strip()) else "Sem nome"
            
            res_tabela, pdv_dict = calcular_pdv(fob_val, qtd_val, comp_val, larg_val, alt_val, peso_val, taxa_cambio, frete_maritimo, margem_alvo)
            ok = salvar_no_google_sheets(fab_final, nome_final, fob_val, qtd_val, peso_val, comp_val, larg_val, alt_val, pdv_dict)
            if ok:
                st.success("Cálculo realizado e salvo na planilha do Google Sheets com sucesso!")
            st.subheader(f"Tabela de PDV — Produto: {nome_final} ({fab_final})")
            st.table(res_tabela)

with tab2:
    st.subheader("Descobrir o Preço FOB Máximo a partir do PDV Desejado")
    with st.form("form_produto_inverso"):
        col1, col2, col3 = st.columns(3)
        with col1:
            fabrica_inv = st.text_input("Fábrica (Opcional)", value=None, key="fab_inv")
            nome_inv = st.text_input("Nome/Código do Produto (Opcional)", value=None, key="nome_inv")
            pdv_alvo_val = st.number_input("PDV Desejado (R$)", min_value=0.0, value=None, step=5.0, key="pdv_inv")
            canal_ref = st.selectbox("Marketplace de Referência", ['Mercado Livre Clássico', 'Mercado Livre Premium', 'Shopee', 'Amazon', 'Magalu'])
        with col2:
            qtd_inv = st.number_input("Quantidade no Container", min_value=0, value=None, step=50, key="qtd_inv")
            peso_inv = st.number_input("Peso Físico (kg)", min_value=0.0, value=None, step=0.5, key="peso_inv")
        with col3:
            comp_inv = st.number_input("Comprimento (cm)", min_value=0.0, value=None, step=1.0, key="comp_inv")
            larg_inv = st.number_input("Largura (cm)", min_value=0.0, value=None, step=1.0, key="larg_inv")
            alt_inv = st.number_input("Altura (cm)", min_value=0.0, value=None, step=1.0, key="alt_inv")
            
        btn_col1, btn_col2 = st.columns([3, 1])
        with btn_col1:
            submitted_inverso = st.form_submit_button("Calcular Preço FOB Máximo")
        with btn_col2:
            st.form_submit_button("🧹 Limpar Campos", on_click=reset_tab2)

    if submitted_inverso:
        if not pdv_alvo_val or not qtd_inv or not peso_inv or not comp_inv or not larg_inv or not alt_inv:
            st.error("Preencha todos os campos numéricos obrigatórios.")
        elif pdv_alvo_val <= 0 or qtd_inv <= 0 or peso_inv <= 0 or comp_inv <= 0 or larg_inv <= 0 or alt_inv <= 0:
            st.error("Os valores numéricos devem ser maiores que zero.")
        else:
            fab_inv_final = fabrica_inv.strip() if (fabrica_inv and fabrica_inv.strip()) else "Não informada"
            nome_inv_final = nome_inv.strip() if (nome_inv and nome_inv.strip()) else "Sem nome"
            
            fob_calculado = calcular_fob_inverso(pdv_alvo_val, canal_ref, qtd_inv, comp_inv, larg_inv, alt_inv, peso_inv, taxa_cambio, frete_maritimo, margem_alvo)
            
            if fob_calculado <= 0:
                st.warning("O PDV desejado é muito baixo para cobrir os custos logísticos (o FOB ficou negativo). Aumente o PDV alvo.")
            else:
                st.metric(label=f"💵 Preço FOB Máximo Recomendado ({fab_inv_final} - {nome_inv_final})", value=f"USD ${fob_calculado:.2f}")
                st.info(f"Para vender no **{canal_ref}** por **R$ {pdv_alvo_val:.2f}** mantendo a margem de **{margem_alvo*100:.1f}%**, o preço FOB máximo a negociar com a fábrica é **USD ${fob_calculado:.2f}**.")
                
                res_tabela, pdv_dict = calcular_pdv(fob_calculado, qtd_inv, comp_inv, larg_inv, alt_inv, peso_inv, taxa_cambio, frete_maritimo, margem_alvo)
                
                salvar_no_google_sheets(fab_inv_final, nome_inv_final, fob_calculado, qtd_inv, peso_inv, comp_inv, larg_inv, alt_inv, pdv_dict)
                
                st.subheader("Projeção de PDV para todos os Marketplaces com esse FOB:")
                st.table(res_tabela)

with tab3:
    st.subheader("📊 Registros Gravados no Google Sheets")
    df_sheets = carregar_do_google_sheets()
    
    if df_sheets.empty:
        st.info("Aguardando os primeiros registros ou verificando conexão...")
    else:
        st.dataframe(df_sheets, use_container_width=True)
        
        csv = df_sheets.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Baixar Histórico em CSV / Excel",
            data=csv,
            file_name="historico_simulacoes_pdv.csv",
            mime="text/csv"
        )
        
        st.divider()
        st.subheader("🗑️️ Gerenciar / Excluir Registros")
        
        col_del1, col_del2 = st.columns([2, 1])
        with col_del1:
            id_para_deletar = st.number_input("Digite o ID do produto que deseja excluir:", min_value=2, step=1)
        with col_del2:
            st.write("")
            st.write("")
            if st.button("Excluir Produto"):
                if deletar_do_google_sheets(id_para_deletar):
                    st.warning(f"Registro ID {id_para_deletar} removido com sucesso da planilha do Google Sheets!")
                    st.rerun()
                else:
                    st.error("Não foi possível excluir o registro. Verifique se atualizou o Apps Script para a 'Nova versão'.")
