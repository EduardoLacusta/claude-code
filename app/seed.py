"""
Script para popular o banco com os dados que estavam hardcoded no HTML original.
Execute uma vez para ter dados iniciais sem precisar dos xlsx.
"""
import json
import os
import sys

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import init_db, get_db
from app.importer import seed_comunidades


def seed_from_json(json_path):
    """Importa dados de um arquivo JSON com formato {criminais:[], celulares:[], veiculos:[]}."""
    init_db()
    seed_comunidades()

    with open(json_path) as f:
        data = json.load(f)

    conn = get_db()
    count = 0

    # Criminais: [lat, lon, rubrica, natureza, data, hora, bairro, logradouro, municipio, tipo_local]
    for d in data.get("criminais", []):
        conn.execute(
            "INSERT INTO ocorrencias (tipo,lat,lon,rubrica,natureza,data,hora,bairro,logradouro,municipio,tipo_local,ano_origem) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ("criminais", d[0], d[1], d[2], d[3], d[4], d[5] if d[5] != "NULL" else None,
             d[6], d[7], d[8], d[9], int(d[4][:4]) if d[4] else 2025))
        count += 1

    # Celulares: [lat, lon, rubrica, data, hora, bairro, logradouro, municipio, tipo_local]
    for d in data.get("celulares", []):
        conn.execute(
            "INSERT INTO ocorrencias (tipo,lat,lon,rubrica,natureza,data,hora,bairro,logradouro,municipio,tipo_local,ano_origem) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ("celulares", d[0], d[1], d[2], d[2], d[3], d[4] if d[4] != "NULL" else None,
             d[5], d[6], d[7], d[8] if len(d) > 8 else None, int(d[3][:4]) if d[3] else 2025))
        count += 1

    # Veiculos: [lat, lon, rubrica, data, hora, bairro, logradouro, municipio, tipo_local, tipo_veiculo]
    for d in data.get("veiculos", []):
        conn.execute(
            "INSERT INTO ocorrencias (tipo,lat,lon,rubrica,natureza,data,hora,bairro,logradouro,municipio,tipo_local,tipo_veiculo,ano_origem) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("veiculos", d[0], d[1], d[2], d[2], d[3], d[4] if d[4] != "NULL" else None,
             d[5], d[6], d[7], d[8] if len(d) > 8 else None, d[9] if len(d) > 9 else None,
             int(d[3][:4]) if d[3] else 2025))
        count += 1

    conn.commit()
    conn.close()
    print(f"Seed completo: {count} registros inseridos")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        seed_from_json(sys.argv[1])
    else:
        print("Uso: python -m app.seed <caminho_para_seed_data.json>")
        print("  ou coloque os xlsx em data/xlsx/ e use a interface web para importar")
