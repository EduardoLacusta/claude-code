import os
import logging
import threading
from flask import Flask, render_template, jsonify, request

from app.models import init_db, query_ocorrencias, get_stats, get_comunidades, get_date_range, get_import_log
from app.importer import import_xlsx, import_all, seed_comunidades, download_xlsx
from app.config import SSP_SOURCES, XLSX_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__,
            template_folder=os.path.join(os.path.dirname(__file__), "templates"),
            static_folder=os.path.join(os.path.dirname(__file__), "static"))

# Inicializa banco e dados fixos na primeira execução
with app.app_context():
    init_db()
    seed_comunidades()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/ocorrencias")
def api_ocorrencias():
    """Retorna ocorrências filtradas como JSON otimizado para o mapa."""
    tipo = request.args.get("tipo")
    municipio = request.args.get("municipio")
    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")
    natureza = request.args.get("natureza")

    rows = query_ocorrencias(
        tipo=tipo,
        municipio=municipio,
        data_inicio=data_inicio,
        data_fim=data_fim,
        natureza=natureza,
    )

    # Formato compacto: arrays ao invés de objetos para reduzir tamanho
    result = {
        "criminais": [],
        "celulares": [],
        "veiculos": [],
    }

    for r in rows:
        t = r["tipo"]
        if t == "criminais":
            result["criminais"].append([
                r["lat"], r["lon"], r["rubrica"], r["natureza"],
                r["data"], r["hora"], r["bairro"], r["logradouro"],
                r["municipio"], r["tipo_local"]
            ])
        elif t == "celulares":
            result["celulares"].append([
                r["lat"], r["lon"], r["rubrica"],
                r["data"], r["hora"], r["bairro"], r["logradouro"],
                r["municipio"], r["tipo_local"]
            ])
        elif t == "veiculos":
            result["veiculos"].append([
                r["lat"], r["lon"], r["rubrica"],
                r["data"], r["hora"], r["bairro"], r["logradouro"],
                r["municipio"], r["tipo_local"], r["tipo_veiculo"]
            ])

    return jsonify(result)


@app.route("/api/stats")
def api_stats():
    municipio = request.args.get("municipio")
    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")
    stats = get_stats(municipio=municipio, data_inicio=data_inicio, data_fim=data_fim)
    return jsonify(stats)


@app.route("/api/comunidades")
def api_comunidades():
    return jsonify(get_comunidades())


@app.route("/api/date-range")
def api_date_range():
    return jsonify(get_date_range())


@app.route("/api/import-log")
def api_import_log():
    return jsonify(get_import_log())


# Estado da importação em background
_import_status = {"running": False, "result": None, "progress": ""}


@app.route("/api/import", methods=["POST"])
def api_import():
    """Dispara importação de dados. Aceita JSON com tipo e ano."""
    global _import_status

    if _import_status["running"]:
        return jsonify({"ok": False, "error": "Importação já em andamento", "progress": _import_status["progress"]}), 409

    data = request.get_json() or {}
    tipo = data.get("tipo")
    year = data.get("ano", 2026)

    if tipo and tipo not in SSP_SOURCES:
        return jsonify({"ok": False, "error": f"Tipo inválido. Use: {list(SSP_SOURCES.keys())}"}), 400

    def run_import():
        global _import_status
        _import_status = {"running": True, "result": None, "progress": "Iniciando..."}
        try:
            if tipo:
                _import_status["progress"] = f"Importando {tipo} {year}..."
                result = import_xlsx(tipo, year)
                _import_status["result"] = {f"{tipo}_{year}": result}
            else:
                results = {}
                for t in SSP_SOURCES:
                    _import_status["progress"] = f"Importando {t} {year}..."
                    results[f"{t}_{year}"] = import_xlsx(t, year)
                _import_status["result"] = results
            _import_status["progress"] = "Concluído"
        except Exception as e:
            logger.exception("Erro na importação")
            _import_status["result"] = {"ok": False, "error": str(e)}
            _import_status["progress"] = f"Erro: {e}"
        finally:
            _import_status["running"] = False

    thread = threading.Thread(target=run_import, daemon=True)
    thread.start()

    return jsonify({"ok": True, "message": "Importação iniciada em background"})


@app.route("/api/import-status")
def api_import_status():
    return jsonify(_import_status)


@app.route("/api/available-files")
def api_available_files():
    """Lista arquivos xlsx disponíveis em data/xlsx/."""
    os.makedirs(XLSX_DIR, exist_ok=True)
    files = []
    for f in sorted(os.listdir(XLSX_DIR)):
        if f.endswith(".xlsx"):
            path = os.path.join(XLSX_DIR, f)
            files.append({
                "name": f,
                "size_mb": round(os.path.getsize(path) / 1024 / 1024, 1),
            })
    return jsonify(files)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
