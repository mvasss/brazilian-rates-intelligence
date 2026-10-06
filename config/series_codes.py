"""
Brazilian Rates Intelligence — Series Codes Catalog

Centralized registry of all data series used in the project.
Each entry documents source, code, description, and frequency.
"""

# =============================================================================
# BCB SGS — Sistema Gerenciador de Séries Temporais
# Portal: https://www3.bcb.gov.br/sgspub/
# =============================================================================
SGS_SERIES = {
    # Monetary policy
    "selic_meta": {"code": 432, "desc": "Taxa Selic Meta (% a.a.)", "freq": "D"},
    "selic_efetiva": {"code": 11, "desc": "Taxa Selic Efetiva (% a.a.)", "freq": "D"},
    # Inflation
    "ipca_mensal": {"code": 433, "desc": "IPCA variação mensal (%)", "freq": "M"},
    "ipca_12m": {"code": 13522, "desc": "IPCA acumulado 12 meses (%)", "freq": "M"},
    "igpm_mensal": {"code": 189, "desc": "IGP-M variação mensal (%)", "freq": "M"},
    # Exchange rate
    "usd_brl_ptax": {"code": 1, "desc": "Dólar PTAX venda (R$/US$)", "freq": "D"},
    # Activity
    "pib_mensal": {"code": 4380, "desc": "PIB mensal (índice)", "freq": "M"},
    "desemprego_pnad": {"code": 24369, "desc": "Taxa de desemprego PNAD (%)", "freq": "M"},
    # Fiscal
    "divida_bruta_pib": {"code": 13762, "desc": "Dívida bruta / PIB (%)", "freq": "M"},
    "resultado_primario": {"code": 5793, "desc": "Resultado primário (R$ mi)", "freq": "M"},
}

# =============================================================================
# BCB Focus — Expectativas de Mercado
# API OData: https://olinda.bcb.gov.br/olinda/servico/Expectativas/
# =============================================================================
FOCUS_INDICATORS = {
    "ipca": {"indicator": "IPCA", "desc": "Expectativa IPCA (%)"},
    "selic": {"indicator": "Selic", "desc": "Expectativa Selic (% a.a.)"},
    "pib": {"indicator": "PIB Total", "desc": "Expectativa PIB (%)"},
    "cambio": {"indicator": "Câmbio", "desc": "Expectativa câmbio (R$/US$)"},
}

# =============================================================================
# yfinance — Market Data
# =============================================================================
YFINANCE_TICKERS = {
    "ibovespa": {"ticker": "^BVSP", "desc": "Índice Ibovespa"},
    "ifix": {"ticker": "XFIX11.SA", "desc": "Índice IFIX (FIIs - ETF Proxy)"},
    "usd_brl": {"ticker": "USDBRL=X", "desc": "Câmbio USD/BRL"},
    "imab11": {"ticker": "IMAB11.SA", "desc": "ETF IMA-B (proxy)"},
    "bova11": {"ticker": "BOVA11.SA", "desc": "ETF Ibovespa"},
}

# Sector tickers for deeper asset impact analysis
SECTOR_TICKERS = {
    "banks": {"ticker": "IFNC.SA", "desc": "Índice Financeiro"},
    "small_caps": {"ticker": "SMLL.SA", "desc": "Índice Small Cap"},
}

# =============================================================================
# pyettj — Estrutura a Termo da Taxa de Juros
# =============================================================================
ETTJ_CURVES = {
    "pre": {"curve": "PRE", "desc": "ETTJ Prefixada (DI)"},
    "ipca": {"curve": "DIC", "desc": "ETTJ IPCA (NTN-B)"},
}

# =============================================================================
# Event catalogs
# =============================================================================
# COPOM decisions are fetched dynamically; this maps decision types
COPOM_DECISION_TYPES = {
    "hike": "Alta",
    "cut": "Corte",
    "hold": "Manutenção",
}

# FOMC meeting dates (manually curated, key ones only)
# Format: (date, decision_bps, description)
FOMC_KEY_DECISIONS = [
    ("2020-03-03", -50, "Emergency cut (COVID)"),
    ("2020-03-15", -100, "Emergency cut to 0-0.25%"),
    ("2022-03-16", 25, "First hike post-COVID"),
    ("2022-05-04", 50, "50bps hike"),
    ("2022-06-15", 75, "75bps hike"),
    ("2022-07-27", 75, "75bps hike"),
    ("2022-09-21", 75, "75bps hike"),
    ("2022-11-02", 75, "75bps hike"),
    ("2022-12-14", 50, "50bps hike"),
    ("2023-02-01", 25, "25bps hike"),
    ("2023-03-22", 25, "25bps hike to 5%"),
    ("2023-05-03", 25, "Hold at 5-5.25%"),
    ("2023-07-26", 25, "25bps hike to 5.25-5.5%"),
    ("2024-09-18", -50, "First cut"),
    ("2024-11-07", -25, "25bps cut"),
    ("2024-12-18", -25, "25bps cut"),
    ("2025-01-29", 0, "Hold"),
    ("2025-03-19", 0, "Hold"),
    ("2025-05-07", 0, "Hold"),
    ("2025-06-18", -25, "25bps cut"),
]

# Key fiscal events (manually curated)
FISCAL_EVENTS = [
    ("2020-03-20", "negative", "Calamidade pública COVID"),
    ("2021-03-15", "negative", "Fura-teto: PEC Emergencial"),
    ("2021-10-20", "negative", "Precatórios PEC — fura-teto"),
    ("2022-06-23", "negative", "PEC Kamikaze (benefícios eleitorais)"),
    ("2023-01-12", "positive", "Novo arcabouço fiscal (proposta)"),
    ("2023-03-30", "positive", "Arcabouço fiscal aprovado"),
    ("2023-08-24", "negative", "Meta fiscal flexibilizada"),
    ("2024-04-15", "negative", "Revisão meta fiscal 2025"),
    ("2024-11-28", "positive", "Pacote corte gastos anunciado"),
    ("2025-03-31", "negative", "Revisão meta primária"),
]
