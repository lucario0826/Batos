import os
from flask import Flask, render_template, request

import queries


app = Flask(__name__)

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", 5432)),
    "dbname": os.environ.get("DB_NAME", "cc3201"),
    "user": os.environ.get("DB_USER", "webuser"),
    "password": os.environ.get("DB_PASSWORD", ""),
}

# Mientras no esté la base real, el buscador usa juegos inventados.
DB_DEMO = os.environ.get("DB_DEMO", "true").lower() == "true"


@app.route("/", methods=["GET"])
def index():
    q = request.args.get("q", "").strip()
    titulo, sql, columnas, resultados, error = None, None, [], [], None

    if q:
        try:
            titulo, sql = queries.resolve(q)
            columnas, resultados = queries.run(sql, DB_CONFIG, DB_DEMO)
        except Exception as e:
            error = str(e)

    return render_template("index.html", q=q, titulo=titulo, sql=sql, columnas=columnas,
                           resultados=resultados, error=error, ejemplos=queries.EXAMPLES)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)