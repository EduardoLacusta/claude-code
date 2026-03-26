import sqlite3
import os
from app.config import DB_PATH, DATA_DIR


def get_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ocorrencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,          -- 'criminais', 'celulares', 'veiculos'
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            rubrica TEXT,
            natureza TEXT,
            data TEXT,                   -- YYYY-MM-DD
            hora TEXT,
            bairro TEXT,
            logradouro TEXT,
            municipio TEXT,
            tipo_local TEXT,
            tipo_veiculo TEXT,
            ano_origem INTEGER,
            fonte TEXT DEFAULT 'ssp'
        );

        CREATE INDEX IF NOT EXISTS idx_ocorrencias_tipo ON ocorrencias(tipo);
        CREATE INDEX IF NOT EXISTS idx_ocorrencias_data ON ocorrencias(data);
        CREATE INDEX IF NOT EXISTS idx_ocorrencias_municipio ON ocorrencias(municipio);
        CREATE INDEX IF NOT EXISTS idx_ocorrencias_lat_lon ON ocorrencias(lat, lon);
        CREATE INDEX IF NOT EXISTS idx_ocorrencias_tipo_data ON ocorrencias(tipo, data);

        CREATE TABLE IF NOT EXISTS comunidades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            municipio TEXT,
            descricao TEXT
        );

        CREATE TABLE IF NOT EXISTS import_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            ano INTEGER NOT NULL,
            arquivo TEXT,
            registros INTEGER,
            importado_em TEXT DEFAULT (datetime('now')),
            UNIQUE(tipo, ano)
        );
    """)
    conn.commit()
    conn.close()


def query_ocorrencias(tipo=None, municipio=None, data_inicio=None, data_fim=None,
                      natureza=None, limit=50000):
    conn = get_db()
    sql = "SELECT lat, lon, tipo, rubrica, natureza, data, hora, bairro, logradouro, municipio, tipo_local, tipo_veiculo FROM ocorrencias WHERE 1=1"
    params = []

    if tipo:
        sql += " AND tipo = ?"
        params.append(tipo)
    if municipio:
        sql += " AND municipio = ?"
        params.append(municipio)
    if data_inicio:
        sql += " AND data >= ?"
        params.append(data_inicio)
    if data_fim:
        sql += " AND data <= ?"
        params.append(data_fim)
    if natureza:
        sql += " AND natureza LIKE ?"
        params.append(f"%{natureza}%")

    sql += " LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats(municipio=None, data_inicio=None, data_fim=None):
    conn = get_db()
    where = "WHERE 1=1"
    params = []
    if municipio:
        where += " AND municipio = ?"
        params.append(municipio)
    if data_inicio:
        where += " AND data >= ?"
        params.append(data_inicio)
    if data_fim:
        where += " AND data <= ?"
        params.append(data_fim)

    stats = {}
    for key, cond in [("total", ""), ("roubos", " AND natureza LIKE '%ROUBO%'"),
                       ("furtos", " AND natureza LIKE '%FURTO%'"),
                       ("homicidios", " AND (natureza LIKE '%HOMICÍDIO DOLOSO%' OR natureza LIKE '%LATROCÍNIO%')")]:
        row = conn.execute(f"SELECT COUNT(*) as n FROM ocorrencias {where}{cond}", params).fetchone()
        stats[key] = row["n"]

    for tipo in ["criminais", "celulares", "veiculos"]:
        row = conn.execute(f"SELECT COUNT(*) as n FROM ocorrencias {where} AND tipo = ?", params + [tipo]).fetchone()
        stats[f"cnt_{tipo}"] = row["n"]

    conn.close()
    return stats


def get_comunidades():
    conn = get_db()
    rows = conn.execute("SELECT nome, lat, lon, municipio, descricao FROM comunidades").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_date_range():
    conn = get_db()
    row = conn.execute("SELECT MIN(data) as min_data, MAX(data) as max_data FROM ocorrencias WHERE data IS NOT NULL AND data != ''").fetchone()
    conn.close()
    if row and row["min_data"]:
        return {"min": row["min_data"], "max": row["max_data"]}
    return {"min": "2025-01-01", "max": "2026-12-31"}


def get_import_log():
    conn = get_db()
    rows = conn.execute("SELECT tipo, ano, registros, importado_em FROM import_log ORDER BY importado_em DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]
