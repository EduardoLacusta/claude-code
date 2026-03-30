import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, "data")
XLSX_DIR = os.path.join(DATA_DIR, "xlsx")
DB_PATH = os.path.join(DATA_DIR, "risco.db")

SSP_BASE = "https://www.ssp.sp.gov.br/assets/estatistica/transparencia/baseDados"

SSP_SOURCES = {
    "criminais": {
        "url_tpl": f"{SSP_BASE}/spDados/SPDadosCriminais_{{year}}.xlsx",
        "file_tpl": "SPDadosCriminais_{year}.xlsx",
    },
    "celulares": {
        "url_tpl": f"{SSP_BASE}/celularesSub/CelularesSubtraidos_{{year}}.xlsx",
        "file_tpl": "CelularesSubtraidos_{year}.xlsx",
    },
    "veiculos": {
        "url_tpl": f"{SSP_BASE}/veiculosSub/VeiculosSubtraidos_{{year}}.xlsx",
        "file_tpl": "VeiculosSubtraidos_{year}.xlsx",
    },
}

# Municípios da Baixada Santista (nomes como aparecem nos dados SSP)
MUNICIPIOS_BAIXADA = [
    "SANTOS", "S.VICENTE", "SAO VICENTE", "GUARUJA", "GUARUJÁ",
    "PRAIA GRANDE", "CUBATAO", "CUBATÃO", "ITANHAEM", "ITANHAÉM",
    "MONGAGUA", "MONGAGUÁ", "PERUIBE", "PERUÍBE", "BERTIOGA",
]
