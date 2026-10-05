import streamlit as st
import pandas as pd
import requests
from bisect import bisect_right

# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================
st.set_page_config(
    page_title="Simulador de Importação & PDV",
    layout="wide"
)

URL_GOOGLE_SHEETS = (
    "https://script.google.com/macros/s/"
    "AKfycbxry1mS1PozdeKeYqCgfhzuCAd8H8sxiEW_vQwFtMzI4nqykh3ApJmH-DkIs2sv1suW/exec"
)

st.title("🚢 Simulador de Importação & Preço de Venda (PDV)")
st.write("Conectado ao Google Sheets para persistência permanente dos dados.")

# ============================================================
# CONSTANTES DO MODELO
# Estas constantes reproduzem a estrutura da planilha enviada.
# ============================================================
II_RATE = 0.20
IPI_RATE = 0.0325
PIS_RATE = 0.0210
COFINS_RATE = 0.0965
ICMS_RATE = 0.18
IMP_LP_RATE = 0.0925

THC = 998.0
SISCOMEX = 154.23
SEGURO = 80.0
AFRMM_ADICIONAL = 21.20

PORTO_ARMAZENAGEM = 1900.0
THC_LOCAL = 998.0
TAXAS_LOCAIS = 1800.0
HONORARIO_DESPACHANTE = 650.0
FRETE_RODOVIARIO = 4000.0
BANCO_TARIFA_FIXA_USD = 50.0

# A planilha soma LOG = R$1 e Emb = R$1 ao custo da venda.
LOG_VENDA = 1.0
EMB_VENDA = 1.0
CUSTOS_INTERNOS_VENDA = LOG_VENDA + EMB_VENDA

# A aba MP soma mais R$5 em "Frete 2" aos marketplaces.
FRETE_EXTRA_MARKETPLACE = 5.0

# ============================================================
# MATRIZ EXATA DA ABA "ML"
#
# A fórmula do Excel usa:
# INDEX(ML!C14:J42,
#       MATCH(PESO, ML!B14:B42, 1),
#       MATCH(PDV, ML!C13:J13, 1))
#
# Portanto, o frete depende de PESO E PDV.
# ============================================================
ML_PESO_FAIXAS = [
    0, 0.3, 0.5, 1, 1.5, 2, 3, 4, 5, 6, 7, 8, 9,
    11, 13, 15, 17, 20, 25, 30, 40, 50, 60, 70, 80,
    90, 100, 125, 150
]

ML_PRECO_FAIXAS = [0, 19, 49, 79, 100, 120, 150, 200]

ML_FRETE_MATRIX = [
    [5.65, 6.55, 7.75, 12.35, 14.35, 16.45, 18.45, 20.95],
    [5.95, 6.65, 7.85, 13.25, 15.45, 17.65, 19.85, 22.55],
    [6.05, 6.75, 7.95, 13.85, 16.15, 18.45, 20.75, 23.65],
    [6.15, 6.85, 8.05, 14.15, 16.45, 18.85, 21.15, 24.65],
    [6.25, 6.95, 8.15, 14.45, 16.85, 19.25, 21.65, 24.65],
    [6.35, 7.95, 8.55, 15.75, 18.35, 21.05, 23.65, 26.25],
    [6.45, 8.15, 8.95, 17.05, 19.85, 22.65, 25.55, 28.35],
    [6.55, 8.35, 9.75, 18.45, 21.55, 24.65, 27.75, 30.75],
    [6.65, 8.55, 9.95, 25.45, 28.55, 32.65, 35.75, 39.75],
    [6.75, 8.75, 10.15, 27.05, 31.05, 36.05, 40.05, 44.05],
    [6.85, 8.95, 10.35, 28.85, 33.65, 38.45, 43.25, 48.05],
    [6.95, 9.15, 10.55, 29.65, 34.55, 39.55, 44.45, 49.35],
    [7.05, 9.55, 10.95, 41.25, 48.05, 54.95, 61.75, 68.65],
    [7.15, 9.95, 11.35, 42.15, 49.25, 56.25, 63.25, 70.25],
    [7.25, 10.15, 11.55, 45.05, 52.45, 59.95, 67.45, 74.95],
    [7.35, 10.35, 11.75, 48.55, 56.05, 63.55, 70.75, 78.65],
    [7.45, 10.55, 11.95, 54.75, 63.85, 72.95, 82.05, 91.15],
    [7.65, 10.95, 12.15, 64.05, 75.05, 84.75, 95.35, 105.95],
    [7.75, 11.15, 12.35, 65.95, 75.45, 85.55, 96.25, 106.95],
    [7.85, 11.35, 12.55, 67.75, 78.95, 88.95, 99.15, 107.05],
    [7.95, 11.55, 12.75, 70.25, 81.05, 92.05, 102.55, 110.75],
    [8.05, 11.75, 12.95, 74.95, 86.45, 98.15, 109.35, 118.15],
    [8.15, 11.95, 13.15, 80.25, 92.95, 105.05, 117.15, 126.55],
    [8.25, 12.15, 13.35, 83.95, 97.05, 109.85, 122.45, 132.25],
    [8.35, 12.35, 13.55, 93.25, 107.45, 122.05, 136.05, 146.95],
    [8.45, 12.55, 13.75, 106.55, 123.95, 139.55, 155.55, 167.95],
    [8.55, 12.75, 13.95, 119.25, 138.05, 156.05, 173.95, 187.95],
    [8.65, 12.75, 14.15, 126.55, 146.15, 165.65, 184.65, 199.45],
    [8.75, 12.95, 14.35, 166.15, 192.45, 217.55, 242.55, 261.95],
]

# ============================================================
# FRETE "G1" DA ABA "Fretes ML"
# Usado pelo modelo atual para Amazon e Magalu.
# ============================================================
FRETE_G1_FAIXAS = [
    (0.3, 19.95),
    (0.5, 20.45),
    (1.0, 21.45),
    (2.0, 22.95),
    (3.0, 23.95),
    (4.0, 24.95),
    (5.0, 25.95),
    (9.0, 41.95),
    (13.0, 65.95),
    (17.0, 73.45),
    (23.0, 85.95),
    (30.0, 98.95),
    (40.0, 109.45),
    (50.0, 116.95),
]

# ============================================================
# SHOPEE: faixas da aba "Shopee"
# O cálculo antigo aplicava 14% + R$26 + R$5 para qualquer preço.
# Isso só é correto para a faixa >= R$200.
# ============================================================
SHOPEE_FAIXAS = [
    (0.00, 79.99, 0.20, 4.00),
    (80.00, 99.99, 0.14, 16.00),
    (100.00, 199.99, 0.14, 20.00),
    (200.00, 499.99, 0.14, 26.00),
    (500.00, float("inf"), 0.14, 26.00),
]

CANAIS_DISPONIVEIS = [
    "Mercado Livre Clássico",
    "Mercado Livre Premium",
    "Shopee",
    "Amazon",
    "Magalu",
]

MAPA_COLUNAS_SALVAMENTO = {
    "Mercado Livre Clássico": "ml_classico_pdv",
    "Mercado Livre Premium": "ml_premium_pdv",
    "Shopee": "shopee_pdv",
    "Amazon": "amazon_pdv",
    "Magalu": "magalu_pdv",
}

# ============================================================
# FUNÇÕES DE FORMULÁRIO / RESET
# ============================================================
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

# ============================================================
# GOOGLE SHEETS
# ============================================================
def salvar_no_google_sheets(
    fabrica, nome, fob, qtd, peso, comp, larg, alt, resultados_dict, canais_salvar=None
):
    if canais_salvar is None:
        canais_salvar = list(CANAIS_DISPONIVEIS)
    canais_salvar = set(canais_salvar)

    payload = {
        "fabrica": fabrica,
        "nome_produto": nome,
        "fob_usd": round(float(fob), 2),
        "qtd": int(qtd),
        "peso_kg": float(peso),
        "comprimento_cm": float(comp),
        "largura_cm": float(larg),
        "altura_cm": float(alt),
        "ml_classico_pdv": resultados_dict.get("Mercado Livre Clássico") if "Mercado Livre Clássico" in canais_salvar else None,
        "ml_premium_pdv": resultados_dict.get("Mercado Livre Premium") if "Mercado Livre Premium" in canais_salvar else None,
        "shopee_pdv": resultados_dict.get("Shopee") if "Shopee" in canais_salvar else None,
        "amazon_pdv": resultados_dict.get("Amazon") if "Amazon" in canais_salvar else None,
        "magalu_pdv": resultados_dict.get("Magalu") if "Magalu" in canais_salvar else None,
    }

    try:
        res = requests.post(
            URL_GOOGLE_SHEETS,
            json=payload,
            allow_redirects=True,
            timeout=20,
        )
        return res.status_code == 200
    except requests.RequestException as e:
        st.error(f"Erro ao salvar no Google Sheets: {e}")
        return False


def deletar_do_google_sheets(row_index):
    payload = {
        "action": "delete",
        "row_index": int(row_index),
    }

    try:
        res = requests.post(
            URL_GOOGLE_SHEETS,
            json=payload,
            allow_redirects=True,
            timeout=20,
        )
        return res.status_code == 200
    except requests.RequestException as e:
        st.error(f"Erro ao deletar no Google Sheets: {e}")
        return False


def deletar_varios_do_google_sheets(row_indices):
    """Exclui vários registros em uma única ação do usuário.

    As linhas são processadas da maior para a menor para que a exclusão
    de uma linha não altere o índice das linhas ainda pendentes.
    """
    sucesso = True
    erros = []

    for row_index in sorted({int(i) for i in row_indices}, reverse=True):
        if not deletar_do_google_sheets(row_index):
            sucesso = False
            erros.append(row_index)

    return sucesso, erros


def carregar_do_google_sheets():
    try:
        res = requests.get(
            URL_GOOGLE_SHEETS,
            allow_redirects=True,
            timeout=20,
        )

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

            except (ValueError, TypeError, KeyError):
                st.warning(
                    "Verifique se o Google Apps Script está configurado "
                    "com permissão de acesso para 'Qualquer pessoa'."
                )

        return pd.DataFrame()

    except requests.RequestException as e:
        st.error(f"Erro ao carregar do Google Sheets: {e}")
        return pd.DataFrame()

# ============================================================
# FUNÇÕES DE FRETE / FAIXAS
# ============================================================
def _indice_match_aproximado(valor, faixas):
    """
    Reproduz o comportamento do Excel:
        MATCH(valor, faixa, 1)

    Retorna a última faixa <= valor.
    """
    idx = bisect_right(faixas, valor) - 1
    return max(0, min(idx, len(faixas) - 1))


def get_frete_ml_matriz(peso_tarifa, pdv):
    """
    Frete exato da matriz ML, considerando PESO + PDV.

    Equivale a:
        INDEX(ML!C14:J42,
              MATCH(PESO,ML!B14:B42,1),
              MATCH(PDV,ML!C13:J13,1))
    """
    peso_idx = _indice_match_aproximado(float(peso_tarifa), ML_PESO_FAIXAS)
    preco_idx = _indice_match_aproximado(float(pdv), ML_PRECO_FAIXAS)

    return ML_FRETE_MATRIX[peso_idx][preco_idx]


def get_frete_ml_g1(peso):
    """Frete da tabela Fretes ML por faixa de peso."""
    peso = float(peso)

    for limite_superior, valor in FRETE_G1_FAIXAS:
        if peso <= limite_superior:
            return valor

    # A planilha termina em 50 kg; para pesos maiores,
    # mantemos o último valor disponível, como um lookup aproximado.
    return FRETE_G1_FAIXAS[-1][1]


def get_taxas_ml_por_preco(peso_tarifa, pdv):
    """Taxa do ML + custo fixo da matriz + R$5 de Frete 2."""
    comissao = 0.115
    frete_matriz = get_frete_ml_matriz(peso_tarifa, pdv)
    custo_fixo = frete_matriz + FRETE_EXTRA_MARKETPLACE
    return comissao, custo_fixo, frete_matriz


def get_taxas_shopee_por_preco(pdv):
    """Taxa e custo fixo da Shopee conforme a aba Shopee."""
    pdv = float(pdv)

    for minimo, maximo, comissao, taxa_fixa in SHOPEE_FAIXAS:
        if minimo <= pdv <= maximo:
            custo_fixo = taxa_fixa + FRETE_EXTRA_MARKETPLACE
            return comissao, custo_fixo, taxa_fixa

    raise ValueError("PDV inválido para cálculo das taxas da Shopee.")


def get_taxas_outros_canais(canal, frete_g1, pdv=None):
    if canal == "Shopee":
        if pdv is None:
            raise ValueError("PDV é obrigatório para calcular as taxas da Shopee.")
        tx, custo_fixo, taxa_fixa_original = get_taxas_shopee_por_preco(pdv)
        return tx, custo_fixo, taxa_fixa_original

    if canal == "Amazon":
        return 0.12, 5.5 + frete_g1, 5.5 + frete_g1

    if canal == "Magalu":
        return 0.18, 5.0 + frete_g1, 5.0 + frete_g1

    raise ValueError(f"Canal não suportado: {canal}")

# ============================================================
# CUSTO DE IMPORTAÇÃO
# ============================================================
def calcular_custo_importacao(
    fob, qtd, cambio, frete_mar
):
    """
    Reproduz a lógica da aba Import.

    Retorna:
        custo_unitario_bruto -> valor unitário com impostos
        custo_unitario_liquido -> valor usado no marketplace
        detalhes -> valores intermediários úteis para auditoria
    """
    if qtd <= 0 or cambio <= 0:
        raise ValueError("Quantidade e câmbio precisam ser maiores que zero.")

    valor_fob_total = float(fob) * float(qtd) * float(cambio)
    frete_brl = float(frete_mar) * float(cambio)
    valor_aduaneiro = valor_fob_total + frete_brl + SEGURO

    ii = II_RATE * valor_aduaneiro
    ipi = IPI_RATE * (valor_aduaneiro + ii)
    pis = PIS_RATE * valor_aduaneiro
    cofins = COFINS_RATE * valor_aduaneiro

    afrmm = AFRMM_ADICIONAL + 0.08 * (frete_brl + THC)

    despesas_log = (
        afrmm
        + PORTO_ARMAZENAGEM
        + THC_LOCAL
        + TAXAS_LOCAIS
        + HONORARIO_DESPACHANTE
        + (BANCO_TARIFA_FIXA_USD * cambio)
        + FRETE_RODOVIARIO
        + SISCOMEX
    )

    # ICMS "por dentro", como na aba Import.
    icms_imp = (
        valor_aduaneiro
        + ii
        + ipi
        + pis
        + cofins
        + afrmm
        + SISCOMEX
    ) / (1.0 - ICMS_RATE) * ICMS_RATE

    total_importacao = (
        valor_aduaneiro
        + ii
        + ipi
        + pis
        + cofins
        + icms_imp
        + despesas_log
    )

    custo_unitario_bruto = total_importacao / qtd

    # A planilha remove PIS, COFINS, IPI e ICMS do custo
    # para obter o "VALOR UNITÁRIO LÍQUIDO" usado na venda.
    custo_unitario_liquido = (
        total_importacao
        - pis
        - cofins
        - ipi
        - icms_imp
    ) / qtd

    detalhes = {
        "valor_fob_total": valor_fob_total,
        "frete_brl": frete_brl,
        "valor_aduaneiro": valor_aduaneiro,
        "ii": ii,
        "ipi": ipi,
        "pis": pis,
        "cofins": cofins,
        "afrmm": afrmm,
        "despesas_log": despesas_log,
        "icms_imp": icms_imp,
        "total_importacao": total_importacao,
        "custo_unitario_bruto": custo_unitario_bruto,
        "custo_unitario_liquido": custo_unitario_liquido,
    }

    return custo_unitario_bruto, custo_unitario_liquido, detalhes

# ============================================================
# SOLUÇÃO INVERSA DO PDV POR FAIXA
# ============================================================
def _validar_denominador(denom, canal):
    if denom <= 0:
        raise ValueError(
            f"A combinação de margem, impostos e taxa do {canal} "
            "não permite um preço de venda matematicamente válido."
        )


def _resolver_pdv_ml(custo_unitario, peso_tarifa, margem, canal):
    """
    Resolve o PDV do Mercado Livre respeitando a matriz de frete
    dependente de PESO e PREÇO.

    Como o frete muda quando o PDV cruza 19/49/79/100/120/150/200,
    calculamos uma hipótese para cada faixa e aceitamos somente a
    hipótese que cai dentro da própria faixa.
    """
    if canal == "Mercado Livre Clássico":
        comissao = 0.115
    elif canal == "Mercado Livre Premium":
        comissao = 0.165
    else:
        raise ValueError("Canal inválido para Mercado Livre.")

    for i, limite_inferior in enumerate(ML_PRECO_FAIXAS):
        limite_superior = (
            ML_PRECO_FAIXAS[i + 1]
            if i + 1 < len(ML_PRECO_FAIXAS)
            else float("inf")
        )

        frete_matriz = get_frete_ml_matriz(peso_tarifa, limite_inferior)
        custo_fixo_marketplace = frete_matriz + FRETE_EXTRA_MARKETPLACE

        denom = (
            1.0
            - comissao
            - IMP_LP_RATE
            - ICMS_RATE
            - margem
        )
        _validar_denominador(denom, canal)

        pdv = (
            custo_unitario
            + CUSTOS_INTERNOS_VENDA
            + custo_fixo_marketplace
        ) / denom

        # Excel MATCH usa a faixa cuja origem é <= PDV.
        # Logo a faixa é [limite_inferior, limite_superior).
        if pdv >= limite_inferior and pdv < limite_superior:
            return pdv, comissao, custo_fixo_marketplace, frete_matriz

    # Caso extremo de arredondamento numérico:
    ultimo_frete = get_frete_ml_matriz(peso_tarifa, ML_PRECO_FAIXAS[-1])
    denom = 1.0 - comissao - IMP_LP_RATE - ICMS_RATE - margem
    _validar_denominador(denom, canal)
    pdv = (
        custo_unitario
        + CUSTOS_INTERNOS_VENDA
        + ultimo_frete
        + FRETE_EXTRA_MARKETPLACE
    ) / denom
    return pdv, comissao, ultimo_frete + FRETE_EXTRA_MARKETPLACE, ultimo_frete


def _resolver_pdv_shopee(custo_unitario, margem):
    """Resolve o PDV da Shopee respeitando suas faixas de preço."""
    for i, (minimo, maximo, comissao, taxa_fixa) in enumerate(SHOPEE_FAIXAS):
        denom = 1.0 - comissao - IMP_LP_RATE - ICMS_RATE - margem
        _validar_denominador(denom, "Shopee")

        custo_fixo_marketplace = taxa_fixa + FRETE_EXTRA_MARKETPLACE
        pdv = (
            custo_unitario
            + CUSTOS_INTERNOS_VENDA
            + custo_fixo_marketplace
        ) / denom

        if pdv >= minimo and pdv <= maximo:
            return pdv, comissao, custo_fixo_marketplace, taxa_fixa

    # Última faixa é aberta.
    _, _, comissao, taxa_fixa = SHOPEE_FAIXAS[-1]
    denom = 1.0 - comissao - IMP_LP_RATE - ICMS_RATE - margem
    _validar_denominador(denom, "Shopee")
    custo_fixo_marketplace = taxa_fixa + FRETE_EXTRA_MARKETPLACE
    pdv = (
        custo_unitario
        + CUSTOS_INTERNOS_VENDA
        + custo_fixo_marketplace
    ) / denom
    return pdv, comissao, custo_fixo_marketplace, taxa_fixa

# ============================================================
# CÁLCULO DIRETO (FOB -> PDV)
# ============================================================
def calcular_pdv(
    fob,
    qtd,
    comp,
    larg,
    alt,
    peso_fisico,
    cambio,
    frete_mar,
    margem,
):
    peso_cubado = (comp * larg * alt) / 6000.0
    peso_tarifa = max(peso_fisico, peso_cubado)
    frete_g1 = get_frete_ml_g1(peso_tarifa)

    _, custo_unitario, detalhes_import = calcular_custo_importacao(
        fob=fob,
        qtd=qtd,
        cambio=cambio,
        frete_mar=frete_mar,
    )

    canais_nomes = [
        "Mercado Livre Clássico",
        "Mercado Livre Premium",
        "Shopee",
        "Amazon",
        "Magalu",
    ]

    resultados = []
    valores_pdv_dict = {}

    for canal in canais_nomes:
        if canal in [
            "Mercado Livre Clássico",
            "Mercado Livre Premium",
        ]:
            pdv, tx_mkt, custo_fixo_marketplace, frete_matriz = _resolver_pdv_ml(
                custo_unitario=custo_unitario,
                peso_tarifa=peso_tarifa,
                margem=margem,
                canal=canal,
            )
            detalhe_taxa = f"Frete R$ {frete_matriz:.2f} + R$ {FRETE_EXTRA_MARKETPLACE:.2f}"

        elif canal == "Shopee":
            pdv, tx_mkt, custo_fixo_marketplace, taxa_fixa = _resolver_pdv_shopee(
                custo_unitario=custo_unitario,
                margem=margem,
            )
            detalhe_taxa = (
                f"Taxa fixa R$ {taxa_fixa:.2f}"
                f" + R$ {FRETE_EXTRA_MARKETPLACE:.2f}"
            )

        else:
            if canal == "Amazon":
                tx_mkt, custo_fixo_marketplace, _ = get_taxas_outros_canais(
                    canal, frete_g1
                )
                detalhe_taxa = f"R$ 5,50 + frete G1 R$ {frete_g1:.2f}"
            else:
                tx_mkt, custo_fixo_marketplace, _ = get_taxas_outros_canais(
                    canal, frete_g1
                )
                detalhe_taxa = f"R$ 5,00 + frete G1 R$ {frete_g1:.2f}"

            denom = 1.0 - tx_mkt - IMP_LP_RATE - ICMS_RATE - margem
            _validar_denominador(denom, canal)

            pdv = (
                custo_unitario
                + CUSTOS_INTERNOS_VENDA
                + custo_fixo_marketplace
            ) / denom

        # Recalcula a margem pela própria equação da venda.
        lucro = pdv * margem

        valores_pdv_dict[canal] = round(pdv, 2)
        resultados.append(
            {
                "Marketplace": canal,
                "Comissão": f"{tx_mkt * 100:.1f}%",
                "Frete / Taxas Fixas": f"R$ {custo_fixo_marketplace:.2f}",
                "PDV Recomendado": f"R$ {pdv:.2f}",
                "Lucro Unitário": f"R$ {lucro:.2f}",
                "Margem Resultante": f"{margem * 100:.1f}%",
            }
        )

    return resultados, valores_pdv_dict

# ============================================================
# CÁLCULO INVERSO (PDV -> FOB)
# ============================================================
def calcular_fob_inverso(
    pdv_alvo,
    canal_ref,
    qtd,
    comp,
    larg,
    alt,
    peso_fisico,
    cambio,
    frete_mar,
    margem,
):
    peso_cubado = (comp * larg * alt) / 6000.0
    peso_tarifa = max(peso_fisico, peso_cubado)
    frete_g1 = get_frete_ml_g1(peso_tarifa)

    # ========================================================
    # 1. Determina EXATAMENTE a taxa/frete do canal para o
    #    PDV informado.
    # ========================================================
    if canal_ref == "Mercado Livre Clássico":
        tx_mkt, custo_fixo_marketplace, frete_matriz = get_taxas_ml_por_preco(
            peso_tarifa, pdv_alvo
        )
        detalhe = f"Frete matriz R$ {frete_matriz:.2f} + R$ {FRETE_EXTRA_MARKETPLACE:.2f}"

    elif canal_ref == "Mercado Livre Premium":
        tx_mkt = 0.165
        frete_matriz = get_frete_ml_matriz(peso_tarifa, pdv_alvo)
        custo_fixo_marketplace = frete_matriz + FRETE_EXTRA_MARKETPLACE
        detalhe = f"Frete matriz R$ {frete_matriz:.2f} + R$ {FRETE_EXTRA_MARKETPLACE:.2f}"

    elif canal_ref == "Shopee":
        tx_mkt, custo_fixo_marketplace, taxa_fixa = get_taxas_shopee_por_preco(
            pdv_alvo
        )
        detalhe = f"Taxa fixa R$ {taxa_fixa:.2f} + R$ {FRETE_EXTRA_MARKETPLACE:.2f}"

    elif canal_ref == "Amazon":
        tx_mkt, custo_fixo_marketplace, _ = get_taxas_outros_canais(
            "Amazon", frete_g1
        )
        detalhe = f"R$ 5,50 + frete G1 R$ {frete_g1:.2f}"

    elif canal_ref == "Magalu":
        tx_mkt, custo_fixo_marketplace, _ = get_taxas_outros_canais(
            "Magalu", frete_g1
        )
        detalhe = f"R$ 5,00 + frete G1 R$ {frete_g1:.2f}"

    else:
        raise ValueError("Marketplace inválido.")

    # ========================================================
    # 2. Isola o custo unitário máximo permitido.
    #
    # pdv = (custo_unitario + log + emb + custos_marketplace)
    #       / (1 - comissão - IMP_LP - ICMS - margem)
    #
    # Logo:
    # custo_unitario = pdv * denominador
    #                 - log - emb - custos_marketplace
    # ========================================================
    denom = 1.0 - tx_mkt - IMP_LP_RATE - ICMS_RATE - margem
    _validar_denominador(denom, canal_ref)

    custo_unitario_max = (
        pdv_alvo * denom
        - CUSTOS_INTERNOS_VENDA
        - custo_fixo_marketplace
    )

    if custo_unitario_max <= 0:
        return 0.0, detalhe, peso_tarifa, frete_g1, custo_unitario_max

    # ========================================================
    # 3. Reverte o custo de importação para achar o FOB.
    # ========================================================
    frete_brl = frete_mar * cambio

    afrmm = AFRMM_ADICIONAL + 0.08 * (frete_brl + THC)

    despesas_log = (
        afrmm
        + PORTO_ARMAZENAGEM
        + THC_LOCAL
        + TAXAS_LOCAIS
        + HONORARIO_DESPACHANTE
        + (BANCO_TARIFA_FIXA_USD * cambio)
        + FRETE_RODOVIARIO
        + SISCOMEX
    )

    # A aba Import usa:
    # Custo líquido total = 1,20 * Valor Aduaneiro + despesas logísticas
    custo_total_base = custo_unitario_max * qtd
    valor_aduaneiro = (custo_total_base - despesas_log) / (1.0 + II_RATE)

    fob_total_brl = valor_aduaneiro - frete_brl - SEGURO
    fob_usd_max = fob_total_brl / (qtd * cambio)

    return (
        max(0.0, fob_usd_max),
        detalhe,
        peso_tarifa,
        frete_g1,
        custo_unitario_max,
    )

# ============================================================
# CONFIGURAÇÕES GLOBAIS DA BARRA LATERAL
# ============================================================
st.sidebar.header("⚙️ Configurações Globais")

taxa_cambio = st.sidebar.number_input(
    "Taxa de Câmbio (USD/BRL)",
    min_value=0.01,
    value=5.30,
    step=0.05,
)

frete_maritimo = st.sidebar.number_input(
    "Frete Marítimo Total (USD)",
    min_value=0.0,
    value=5000.0,
    step=100.0,
)

margem_alvo = (
    st.sidebar.number_input(
        "Margem Alvo (%)",
        min_value=0.0,
        max_value=99.0,
        value=21.9,
        step=0.1,
    )
    / 100.0
)

st.sidebar.caption(
    "O cálculo do Mercado Livre usa a matriz de frete da planilha, "
    "considerando simultaneamente peso e faixa de PDV."
)

# ============================================================
# ABAS
# ============================================================
tab1, tab2, tab3 = st.tabs(
    [
        "🧮 Cálculo Direto (FOB → PDV)",
        "🔄 Cálculo Inverso (PDV → FOB)",
        "📊 Histórico Google Sheets",
    ]
)

# ============================================================
# ABA 1 — FOB -> PDV
# ============================================================
with tab1:
    st.subheader("Calcular PDV Recomendado por Marketplace")

    with st.form("form_produto_direto"):
        col1, col2, col3 = st.columns(3)

        with col1:
            fabrica_prod = st.text_input(
                "Fábrica (Opcional)",
                value=None,
                key="fab_dir",
            )
            nome_prod = st.text_input(
                "Nome/Código do Produto (Opcional)",
                value=None,
                key="nome_dir",
            )
            fob_val = st.number_input(
                "Preço FOB (USD)",
                min_value=0.0,
                value=None,
                step=0.5,
                key="fob_dir",
            )

        with col2:
            qtd_val = st.number_input(
                "Quantidade no Container",
                min_value=0,
                value=None,
                step=50,
                key="qtd_dir",
            )
            peso_val = st.number_input(
                "Peso Físico (kg)",
                min_value=0.0,
                value=None,
                step=0.5,
                key="peso_dir",
            )

        with col3:
            comp_val = st.number_input(
                "Comprimento (cm)",
                min_value=0.0,
                value=None,
                step=1.0,
                key="comp_dir",
            )
            larg_val = st.number_input(
                "Largura (cm)",
                min_value=0.0,
                value=None,
                step=1.0,
                key="larg_dir",
            )
            alt_val = st.number_input(
                "Altura (cm)",
                min_value=0.0,
                value=None,
                step=1.0,
                key="alt_dir",
            )

        canais_salvar_direto = st.multiselect(
            "💾 Quais cálculos deseja salvar no histórico?",
            options=CANAIS_DISPONIVEIS,
            default=CANAIS_DISPONIVEIS,
            key="canais_salvar_direto",
            help="Todos os marketplaces continuam sendo calculados e mostrados. Esta opção define apenas quais resultados serão gravados no Google Sheets.",
        )

        btn_col1, btn_col2 = st.columns([3, 1])

        with btn_col1:
            submitted_direto = st.form_submit_button(
                "Calcular e Salvar na Planilha"
            )

        with btn_col2:
            st.form_submit_button(
                "🧹 Limpar Campos",
                on_click=reset_tab1,
            )

    if submitted_direto:
        campos = [
            fob_val,
            qtd_val,
            peso_val,
            comp_val,
            larg_val,
            alt_val,
        ]

        if any(v is None for v in campos):
            st.error(
                "Preencha todos os campos numéricos obrigatórios para realizar o cálculo."
            )

        elif not canais_salvar_direto:
            st.error("Selecione pelo menos um cálculo para salvar no histórico.")

        elif any(float(v) <= 0 for v in campos):
            st.error("Os valores numéricos devem ser maiores que zero.")

        else:
            fab_final = (
                fabrica_prod.strip()
                if fabrica_prod and fabrica_prod.strip()
                else "Não informada"
            )
            nome_final = (
                nome_prod.strip()
                if nome_prod and nome_prod.strip()
                else "Sem nome"
            )

            try:
                res_tabela, pdv_dict = calcular_pdv(
                    fob=fob_val,
                    qtd=qtd_val,
                    comp=comp_val,
                    larg=larg_val,
                    alt=alt_val,
                    peso_fisico=peso_val,
                    cambio=taxa_cambio,
                    frete_mar=frete_maritimo,
                    margem=margem_alvo,
                )

                ok = salvar_no_google_sheets(
                    fab_final,
                    nome_final,
                    fob_val,
                    qtd_val,
                    peso_val,
                    comp_val,
                    larg_val,
                    alt_val,
                    pdv_dict,
                    canais_salvar=canais_salvar_direto,
                )

                if ok:
                    st.success(
                        "Cálculo realizado e salvo na planilha do Google Sheets com sucesso!"
                    )
                else:
                    st.warning(
                        "Cálculo realizado, mas não foi possível confirmar o salvamento no Google Sheets."
                    )

                st.subheader(
                    f"Tabela de PDV — Produto: {nome_final} ({fab_final})"
                )
                st.table(res_tabela)

            except ValueError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Erro inesperado no cálculo: {e}")

# ============================================================
# ABA 2 — PDV -> FOB
# ============================================================
with tab2:
    st.subheader("Descobrir o Preço FOB Máximo a partir do PDV Desejado")

    with st.form("form_produto_inverso"):
        col1, col2, col3 = st.columns(3)

        with col1:
            fabrica_inv = st.text_input(
                "Fábrica (Opcional)",
                value=None,
                key="fab_inv",
            )
            nome_inv = st.text_input(
                "Nome/Código do Produto (Opcional)",
                value=None,
                key="nome_inv",
            )
            pdv_alvo_val = st.number_input(
                "PDV Desejado (R$)",
                min_value=0.0,
                value=None,
                step=5.0,
                key="pdv_inv",
            )
            canal_ref = st.selectbox(
                "Marketplace de Referência",
                [
                    "Mercado Livre Clássico",
                    "Mercado Livre Premium",
                    "Shopee",
                    "Amazon",
                    "Magalu",
                ],
            )

        with col2:
            qtd_inv = st.number_input(
                "Quantidade no Container",
                min_value=0,
                value=None,
                step=50,
                key="qtd_inv",
            )
            peso_inv = st.number_input(
                "Peso Físico (kg)",
                min_value=0.0,
                value=None,
                step=0.5,
                key="peso_inv",
            )

        with col3:
            comp_inv = st.number_input(
                "Comprimento (cm)",
                min_value=0.0,
                value=None,
                step=1.0,
                key="comp_inv",
            )
            larg_inv = st.number_input(
                "Largura (cm)",
                min_value=0.0,
                value=None,
                step=1.0,
                key="larg_inv",
            )
            alt_inv = st.number_input(
                "Altura (cm)",
                min_value=0.0,
                value=None,
                step=1.0,
                key="alt_inv",
            )

        canais_salvar_inverso = st.multiselect(
            "💾 Quais cálculos deseja salvar no histórico?",
            options=CANAIS_DISPONIVEIS,
            default=CANAIS_DISPONIVEIS,
            key="canais_salvar_inverso",
            help="A projeção de todos os marketplaces continua sendo exibida. Esta opção define apenas quais resultados serão gravados no Google Sheets.",
        )

        btn_col1, btn_col2 = st.columns([3, 1])

        with btn_col1:
            submitted_inverso = st.form_submit_button(
                "Calcular Preço FOB Máximo"
            )

        with btn_col2:
            st.form_submit_button(
                "🧹 Limpar Campos",
                on_click=reset_tab2,
            )

    if submitted_inverso:
        campos = [
            pdv_alvo_val,
            qtd_inv,
            peso_inv,
            comp_inv,
            larg_inv,
            alt_inv,
        ]

        if any(v is None for v in campos):
            st.error("Preencha todos os campos numéricos obrigatórios.")

        elif not canais_salvar_inverso:
            st.error("Selecione pelo menos um cálculo para salvar no histórico.")

        elif any(float(v) <= 0 for v in campos):
            st.error("Os valores numéricos devem ser maiores que zero.")

        else:
            fab_inv_final = (
                fabrica_inv.strip()
                if fabrica_inv and fabrica_inv.strip()
                else "Não informada"
            )
            nome_inv_final = (
                nome_inv.strip()
                if nome_inv and nome_inv.strip()
                else "Sem nome"
            )

            try:
                (
                    fob_calculado,
                    detalhe_frete,
                    peso_tarifa,
                    frete_g1,
                    custo_unitario_max,
                ) = calcular_fob_inverso(
                    pdv_alvo=pdv_alvo_val,
                    canal_ref=canal_ref,
                    qtd=qtd_inv,
                    comp=comp_inv,
                    larg=larg_inv,
                    alt=alt_inv,
                    peso_fisico=peso_inv,
                    cambio=taxa_cambio,
                    frete_mar=frete_maritimo,
                    margem=margem_alvo,
                )

                if fob_calculado <= 0:
                    st.warning(
                        "O PDV desejado é muito baixo para cobrir os custos logísticos "
                        "(o FOB ficou negativo). Aumente o PDV alvo."
                    )
                else:
                    st.metric(
                        label=(
                            f"💵 Preço FOB Máximo Recomendado "
                            f"({fab_inv_final} - {nome_inv_final})"
                        ),
                        value=f"USD ${fob_calculado:.2f}",
                    )

                    st.info(
                        f"Para vender no **{canal_ref}** por **R$ {pdv_alvo_val:.2f}** "
                        f"mantendo a margem de **{margem_alvo * 100:.1f}%**, "
                        f"o preço FOB máximo é **USD ${fob_calculado:.2f}**."
                    )

                    st.caption(
                        f"Peso tarifário: {peso_tarifa:.2f} kg · "
                        f"Frete G1: R$ {frete_g1:.2f} · "
                        f"{detalhe_frete} · "
                        f"Custo unitário líquido máximo: R$ {custo_unitario_max:.2f}"
                    )

                    res_tabela, pdv_dict = calcular_pdv(
                        fob=fob_calculado,
                        qtd=qtd_inv,
                        comp=comp_inv,
                        larg=larg_inv,
                        alt=alt_inv,
                        peso_fisico=peso_inv,
                        cambio=taxa_cambio,
                        frete_mar=frete_maritimo,
                        margem=margem_alvo,
                    )

                    ok = salvar_no_google_sheets(
                        fab_inv_final,
                        nome_inv_final,
                        fob_calculado,
                        qtd_inv,
                        peso_inv,
                        comp_inv,
                        larg_inv,
                        alt_inv,
                        pdv_dict,
                        canais_salvar=canais_salvar_inverso,
                    )

                    if not ok:
                        st.warning(
                            "O cálculo foi concluído, mas o salvamento no Google Sheets "
                            "não pôde ser confirmado."
                        )

                    st.subheader(
                        "Projeção de PDV para todos os Marketplaces com esse FOB:"
                    )
                    st.table(res_tabela)

            except ValueError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Erro inesperado no cálculo inverso: {e}")

# ============================================================
# ABA 3 — HISTÓRICO
# ============================================================
with tab3:
    st.subheader("📊 Registros Gravados no Google Sheets")
    df_sheets = carregar_do_google_sheets()

    if df_sheets.empty:
        st.info("Aguardando os primeiros registros ou verificando conexão...")

    else:
        st.dataframe(df_sheets, use_container_width=True)

        csv = df_sheets.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Baixar Histórico em CSV",
            data=csv,
            file_name="historico_simulacoes_pdv.csv",
            mime="text/csv",
        )

        st.divider()
        st.subheader("🗑 Gerenciar / Excluir Registros")
        st.caption(
            "Selecione um ou vários registros abaixo e clique uma única vez em "
            '"Excluir selecionados". Os registros são removidos em ordem segura para preservar os IDs.'
        )

        ids_disponiveis = df_sheets["ID"].astype(int).tolist() if "ID" in df_sheets.columns else []

        ids_selecionados = st.multiselect(
            "Registros que deseja excluir:",
            options=ids_disponiveis,
            format_func=lambda x: (
                f"ID {x} — "
                f"{df_sheets.loc[df_sheets['ID'] == x, 'nome_produto'].iloc[0]}"
                if "nome_produto" in df_sheets.columns and not df_sheets.loc[df_sheets['ID'] == x].empty
                else f"ID {x}"
            ),
            key="ids_para_deletar",
        )

        col_del1, col_del2 = st.columns([2, 1])
        with col_del1:
            st.write(
                f"**{len(ids_selecionados)} registro(s) selecionado(s).**"
            )
        with col_del2:
            if st.button(
                "🗑️ Excluir selecionados",
                type="primary",
                disabled=not ids_selecionados,
                use_container_width=True,
            ):
                sucesso, erros = deletar_varios_do_google_sheets(ids_selecionados)

                if sucesso:
                    st.success(
                        f"{len(ids_selecionados)} registro(s) removido(s) com sucesso!"
                    )
                    st.rerun()
                else:
                    st.error(
                        "Não foi possível remover todos os registros. "
                        f"IDs com erro: {', '.join(map(str, erros))}."
                    )
