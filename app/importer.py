"""
Importador de dados SSP-SP para o banco SQLite.

Lida com:
- Múltiplas abas por planilha (ignora metodologia, dicionário, etc.)
- Nomes de colunas diferentes entre planilhas
- Detecção automática da aba de dados principal
- Filtragem por municípios da Baixada Santista
"""
import os
import re
import logging
from datetime import datetime

import openpyxl
import requests

from app.config import SSP_SOURCES, XLSX_DIR, MUNICIPIOS_BAIXADA
from app.models import get_db, init_db

logger = logging.getLogger(__name__)

# Abas que devem ser ignoradas
SKIP_SHEETS = {"metodologia", "dicionario", "dicionário", "dicionario de dados",
               "dicionário de dados", "metadados", "leia-me", "leiame", "about", "info"}

# Mapeamento flexível de colunas — cada tipo de planilha pode ter nomes diferentes
COLUMN_MAPS = {
    "criminais": {
        "lat": ["latitude"],
        "lon": ["longitude"],
        "rubrica": ["rubrica", "especie"],
        "natureza": ["natureza_apurada", "natureza", "descr_tipolocal", "descricao"],
        "data": ["data_ocorrencia_bo", "data_ocorrencia", "dataocorrencia", "data_fato"],
        "hora": ["hora_ocorrencia_bo", "hora_ocorrencia", "horaocorrencia", "hora_fato"],
        "bairro": ["bairro", "nome_bairro"],
        "logradouro": ["logradouro", "nome_logradouro", "endereco", "logradouro_fato"],
        "municipio": ["municipio_circunscricao", "municipio", "cidade", "nome_municipio",
                       "municipio_fato"],
        "tipo_local": ["descr_tipolocal", "tipo_local", "tipolocal", "local"],
    },
    "celulares": {
        "lat": ["latitude"],
        "lon": ["longitude"],
        "rubrica": ["rubrica", "natureza", "especie"],
        "data": ["data_ocorrencia_bo", "data_ocorrencia", "dataocorrencia"],
        "hora": ["hora_ocorrencia_bo", "hora_ocorrencia", "horaocorrencia"],
        "bairro": ["bairro", "nome_bairro"],
        "logradouro": ["logradouro", "nome_logradouro"],
        "municipio": ["municipio_circunscricao", "municipio", "cidade"],
        "tipo_local": ["descr_tipolocal", "tipo_local", "tipolocal"],
    },
    "veiculos": {
        "lat": ["latitude"],
        "lon": ["longitude"],
        "rubrica": ["rubrica", "natureza", "especie"],
        "data": ["data_ocorrencia_bo", "data_ocorrencia", "dataocorrencia"],
        "hora": ["hora_ocorrencia_bo", "hora_ocorrencia", "horaocorrencia"],
        "bairro": ["bairro", "nome_bairro"],
        "logradouro": ["logradouro", "nome_logradouro"],
        "municipio": ["municipio_circunscricao", "municipio", "cidade"],
        "tipo_local": ["descr_tipolocal", "tipo_local", "tipolocal"],
        "tipo_veiculo": ["descr_marca_veiculo", "tipo_veiculo", "marca_veiculo",
                          "descr_tipo_veiculo", "veiculo"],
    },
}


def normalize_col(name):
    """Normaliza nome de coluna para comparação."""
    if not name:
        return ""
    return re.sub(r'[^a-z0-9]', '', str(name).lower().strip())


def _sheet_looks_like_data(ws):
    """Verifica se uma aba parece conter dados reais (tem coluna 'latitude' ou muitas colunas)."""
    for row in ws.iter_rows(min_row=1, max_row=5, values_only=True):
        cells = [str(c).strip().lower() for c in row if c is not None]
        if not cells:
            continue
        # Se tem "latitude" ou muitas colunas (>5), provavelmente é dados
        for c in cells:
            if "latitude" in c or "longitude" in c:
                return True
        if len(cells) >= 5:
            # Checa se NÃO é texto descritivo longo (típico de aba metodologia)
            if all(len(c) < 80 for c in cells):
                return True
    return False


def find_data_sheet(wb):
    """Encontra a aba principal de dados, ignorando abas de metodologia/dicionário."""
    sheets = wb.sheetnames
    if len(sheets) == 1:
        return sheets[0]

    skip_normalized = {normalize_col(s) for s in SKIP_SHEETS}

    # Primeira passada: procura aba com coluna latitude/longitude
    for name in sheets:
        if normalize_col(name) in skip_normalized:
            continue
        ws = wb[name]
        if _sheet_looks_like_data(ws):
            return name

    # Segunda passada: pega a aba com mais linhas (provavelmente é a de dados)
    best = None
    best_rows = 0
    for name in sheets:
        if normalize_col(name) in skip_normalized:
            continue
        ws = wb[name]
        rows = ws.max_row or 0
        if rows > best_rows:
            best_rows = rows
            best = name

    if best:
        return best

    return sheets[0]


def map_columns(headers, tipo):
    """Mapeia colunas do xlsx para nossos campos, por correspondência flexível."""
    col_map = COLUMN_MAPS.get(tipo, COLUMN_MAPS["criminais"])
    normalized = {normalize_col(h): i for i, h in enumerate(headers) if h}
    result = {}

    for field, candidates in col_map.items():
        for candidate in candidates:
            norm_cand = normalize_col(candidate)
            if norm_cand in normalized:
                result[field] = normalized[norm_cand]
                break

    return result


def parse_date(val):
    """Converte valor de data para YYYY-MM-DD."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    s = str(val).strip()
    if not s or s == "NULL":
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(s[:19], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def parse_hora(val):
    """Extrai hora como string HH:MM."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.strftime("%H:%M")
    s = str(val).strip()
    if not s or s == "NULL":
        return None
    m = re.match(r'(\d{1,2}:\d{2})', s)
    return m.group(1) if m else None


def is_baixada(municipio):
    """Verifica se o município pertence à Baixada Santista."""
    if not municipio:
        return False
    mun_upper = str(municipio).upper().strip()
    return any(mun_upper == m or mun_upper.startswith(m.split()[0])
               for m in MUNICIPIOS_BAIXADA)


def download_xlsx(tipo, year):
    """Tenta baixar o xlsx da SSP. Retorna caminho do arquivo ou None."""
    os.makedirs(XLSX_DIR, exist_ok=True)
    src = SSP_SOURCES[tipo]
    url = src["url_tpl"].format(year=year)
    filepath = os.path.join(XLSX_DIR, src["file_tpl"].format(year=year))

    if os.path.exists(filepath):
        logger.info(f"Arquivo já existe: {filepath}")
        return filepath

    logger.info(f"Baixando {url}...")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "Referer": "https://www.ssp.sp.gov.br/",
        }
        resp = requests.get(url, headers=headers, timeout=120, stream=True)
        resp.raise_for_status()

        with open(filepath, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info(f"Baixado: {filepath} ({os.path.getsize(filepath)} bytes)")
        return filepath
    except Exception as e:
        logger.warning(f"Falha no download de {url}: {e}")
        # Verifica se já foi colocado manualmente
        if os.path.exists(filepath):
            return filepath
        return None


def import_xlsx(tipo, year, filepath=None):
    """
    Importa um arquivo xlsx para o banco de dados.
    Retorna dict com resultado da importação.
    """
    init_db()

    if filepath is None:
        src = SSP_SOURCES[tipo]
        filepath = os.path.join(XLSX_DIR, src["file_tpl"].format(year=year))

    if not os.path.exists(filepath):
        filepath = download_xlsx(tipo, year)
        if not filepath:
            return {"ok": False, "error": f"Arquivo não encontrado. Coloque em: data/xlsx/{SSP_SOURCES[tipo]['file_tpl'].format(year=year)}"}

    logger.info(f"Importando {filepath} (tipo={tipo}, ano={year})...")

    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    sheet_name = find_data_sheet(wb)
    ws = wb[sheet_name]
    logger.info(f"Usando aba: {sheet_name}")

    # Ler cabeçalhos — pode precisar pular linhas de "apresentação" no topo
    rows_iter = ws.iter_rows(values_only=True)
    headers = None
    col_idx = {}
    skipped_header_rows = 0

    for row in rows_iter:
        candidate = [str(h).strip() if h else "" for h in row]
        # Tenta mapear esta linha como cabeçalho
        test_idx = map_columns(candidate, tipo)
        if "lat" in test_idx and "lon" in test_idx:
            headers = candidate
            col_idx = test_idx
            break
        skipped_header_rows += 1
        if skipped_header_rows > 20:
            break

    if not headers or "lat" not in col_idx or "lon" not in col_idx:
        wb.close()
        # Mostra as primeiras linhas para debug
        return {"ok": False, "error": f"Colunas lat/lon não encontradas após {skipped_header_rows} linhas. Verifique a estrutura do arquivo."}

    logger.info(f"Colunas mapeadas (após pular {skipped_header_rows} linhas): {col_idx}")

    conn = get_db()
    # Remove dados anteriores deste tipo/ano para reimportação
    conn.execute("DELETE FROM ocorrencias WHERE tipo = ? AND ano_origem = ?", (tipo, year))

    batch = []
    count = 0
    skipped = 0

    for row in rows_iter:
        try:
            lat = row[col_idx["lat"]]
            lon = row[col_idx["lon"]]
            if lat is None or lon is None:
                skipped += 1
                continue

            lat = float(lat)
            lon = float(lon)
            if lat == 0 or lon == 0 or abs(lat) < 1 or abs(lon) < 1:
                skipped += 1
                continue

            municipio = str(row[col_idx["municipio"]]).strip() if "municipio" in col_idx and row[col_idx["municipio"]] else None

            # Filtrar apenas Baixada Santista
            if not is_baixada(municipio):
                skipped += 1
                continue

            # Normalizar nome do município
            if municipio:
                municipio = municipio.upper().strip()

            record = (
                tipo,
                lat,
                lon,
                str(row[col_idx["rubrica"]]).strip() if "rubrica" in col_idx and row[col_idx["rubrica"]] else None,
                str(row[col_idx["natureza"]]).strip() if "natureza" in col_idx and row[col_idx["natureza"]] else (str(row[col_idx["rubrica"]]).strip() if "rubrica" in col_idx and row[col_idx["rubrica"]] else None),
                parse_date(row[col_idx["data"]]) if "data" in col_idx else None,
                parse_hora(row[col_idx["hora"]]) if "hora" in col_idx else None,
                str(row[col_idx["bairro"]]).strip() if "bairro" in col_idx and row[col_idx["bairro"]] else None,
                str(row[col_idx["logradouro"]]).strip() if "logradouro" in col_idx and row[col_idx["logradouro"]] else None,
                municipio,
                str(row[col_idx["tipo_local"]]).strip() if "tipo_local" in col_idx and row[col_idx["tipo_local"]] else None,
                str(row[col_idx["tipo_veiculo"]]).strip() if "tipo_veiculo" in col_idx and row[col_idx["tipo_veiculo"]] else None,
                year,
            )
            batch.append(record)
            count += 1

            if len(batch) >= 5000:
                conn.executemany(
                    "INSERT INTO ocorrencias (tipo,lat,lon,rubrica,natureza,data,hora,bairro,logradouro,municipio,tipo_local,tipo_veiculo,ano_origem) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    batch)
                batch = []

        except (ValueError, TypeError, IndexError) as e:
            skipped += 1
            continue

    if batch:
        conn.executemany(
            "INSERT INTO ocorrencias (tipo,lat,lon,rubrica,natureza,data,hora,bairro,logradouro,municipio,tipo_local,tipo_veiculo,ano_origem) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            batch)

    # Registrar importação
    conn.execute(
        "INSERT OR REPLACE INTO import_log (tipo, ano, arquivo, registros) VALUES (?, ?, ?, ?)",
        (tipo, year, os.path.basename(filepath), count))

    conn.commit()
    conn.close()
    wb.close()

    logger.info(f"Importados {count} registros, {skipped} ignorados")
    return {"ok": True, "registros": count, "ignorados": skipped, "arquivo": os.path.basename(filepath)}


def import_all(years=None):
    """Importa todos os tipos para os anos especificados."""
    if years is None:
        years = [2025, 2026]

    results = {}
    for tipo in SSP_SOURCES:
        for year in years:
            key = f"{tipo}_{year}"
            results[key] = import_xlsx(tipo, year)
            logger.info(f"{key}: {results[key]}")

    return results


def seed_comunidades():
    """Insere os dados fixos de comunidades/áreas de risco."""
    init_db()
    conn = get_db()

    existing = conn.execute("SELECT COUNT(*) as n FROM comunidades").fetchone()["n"]
    if existing > 0:
        conn.close()
        return

    comunidades = [
        ("Vila Gilda", -23.9685, -46.3923, "SANTOS", "Maior palafita da América Latina"),
        ("Dique da Vila Gilda", -23.9710, -46.3940, "SANTOS", "Extensão das palafitas sobre mangue"),
        ("Jardim Piratininga", -23.9620, -46.3870, "SANTOS", "Área de risco em Santos"),
        ("Rádio Clube", -23.9750, -46.3560, "SANTOS", "Região vulnerável"),
        ("Vila Pantanal", -23.9640, -46.3710, "SANTOS", "Área de ocupação irregular"),
        ("Morro da Nova Cintra", -23.9590, -46.3340, "SANTOS", "Encosta com risco de deslizamento"),
        ("Morro do Marapé", -23.9560, -46.3460, "SANTOS", "Comunidade em encosta"),
        ("Morro Santa Maria", -23.9510, -46.3380, "SANTOS", "Área de risco geológico"),
        ("Morro do São Bento", -23.9545, -46.3290, "SANTOS", "Ocupação em encosta"),
        ("Vila Esperança", -23.9680, -46.3850, "SANTOS", "Comunidade na zona noroeste"),
        ("Dique do Sambaiatuba", -23.9578, -46.3980, "S.VICENTE", "Palafitas e ocupação irregular"),
        ("México 70", -23.9650, -46.4056, "S.VICENTE", "Comunidade"),
        ("Vila Margarida", -23.9530, -46.3990, "S.VICENTE", "Área de risco"),
        ("Jardim Rio Branco", -23.9460, -46.4100, "S.VICENTE", "Comunidade"),
        ("Vila Baiana", -23.9894, -46.2667, "GUARUJA", "Comunidade Vicente de Carvalho"),
        ("Favela do Morrinhos", -23.9940, -46.2590, "GUARUJA", "Área de ocupação"),
        ("Vila Zilda", -23.9970, -46.2530, "GUARUJA", "Comunidade no Guarujá"),
        ("Jardim Progresso", -24.0050, -46.2620, "GUARUJA", "Área de ocupação"),
        ("Sítio do Campo", -24.0152, -46.4350, "PRAIA GRANDE", "Região com alto índice criminal"),
        ("Nova Mirim", -24.0290, -46.4480, "PRAIA GRANDE", "Região periférica"),
        ("Quietude", -24.0220, -46.4250, "PRAIA GRANDE", "Área com ocupações irregulares"),
        ("Vila Esperança (Cubatão)", -23.8870, -46.4180, "CUBATAO", "Comunidade em Cubatão"),
        ("Cota 200", -23.8750, -46.4050, "CUBATAO", "Ocupação em área de serra"),
        ("Pilões", -23.8920, -46.3950, "CUBATAO", "Área de risco geológico"),
    ]

    conn.executemany(
        "INSERT INTO comunidades (nome, lat, lon, municipio, descricao) VALUES (?,?,?,?,?)",
        comunidades)
    conn.commit()
    conn.close()
