import streamlit as st

# Configuração da página
st.set_page_config(page_title="Simulador de Importação & PDV", layout="wide")

st.title("🚢 Simulador de Importação & Preço de Venda (PDV)")
st.write("Preencha os dados abaixo para calcular os preços recomendados por marketplace.")

# Sidebar com premissas globais
st.sidebar.header("⚙️ Configurações Globais")
taxa_cambio = st.sidebar.number_input("Taxa de Câmbio (USD/BRL)", value=5.30, step=0.05)
frete_maritimo = st.sidebar.number_input("Frete Marítimo Total (USD)", value=5000.0, step=100.0)
margem_alvo = st.sidebar.number_input("Margem Alvo (%)", value=21.9, step=0.1) / 100.0

# Faixas de peso oficiais do Mercado Livre (Matriz Excel)
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

# Tabela G1 (Mercado Livre Coluna I/H - Usada para Amazon e Magalu)
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
        resultados.append({
            "Marketplace": canal,
            "Comissão": f"{tx_mkt*100:.1f}%",
            "Frete / Taxa Fixa": f"R$ {j:.2f}",
            "PDV Recomendado": f"R$ {pdv:.2f}",
            "Lucro Unitário": f"R$ {lucro:.2f}",
            "Margem Resultante": f"{margem_alvo*100:.1f}%"
        })
    return resultados

# Formulário para entrada dos dados
with st.form("form_produto"):
    col1, col2, col3 = st.columns(3)
    with col1:
        nome_prod = st.text_input("Nome/Código do Produto")
        fob_val = st.number_input("Preço FOB (USD)", min_value=0.0, value=0.0, step=0.5)
    with col2:
        qtd_val = st.number_input("Quantidade no Container", min_value=0, value=0, step=50)
        peso_val = st.number_input("Peso Físico (kg)", min_value=0.0, value=0.0, step=0.5)
    with col3:
        comp_val = st.number_input("Comprimento (cm)", min_value=0.0, value=0.0, step=1.0)
        larg_val = st.number_input("Largura (cm)", min_value=0.0, value=0.0, step=1.0)
        alt_val = st.number_input("Altura (cm)", min_value=0.0, value=0.0, step=1.0)
        
    submitted = st.form_submit_button("Calcular PDV")

if submitted:
    if not nome_prod or fob_val <= 0 or qtd_val <= 0 or peso_val <= 0 or comp_val <= 0 or larg_val <= 0 or alt_val <= 0:
        st.error("erro no calculo")
    else:
        res = calcular_pdv(fob_val, qtd_val, comp_val, larg_val, alt_val, peso_val)
        st.subheader(f"Tabela de PDV — Produto: {nome_prod}")
        st.table(res)