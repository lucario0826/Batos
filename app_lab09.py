import os
from flask import Flask, render_template, request
import psycopg2

app = Flask(__name__)


DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", 5432)),
    "dbname": os.environ.get("DB_NAME", "cc3201"),
    "user": os.environ.get("DB_USER", "webuser"),
    "password": os.environ.get("DB_PASSWORD", ""),
}


@app.route("/", methods=["GET"])
def index():
    ap = request.args.get("ap")
    resultados = []
    error = None

    if ap is not None:
        try:
            with psycopg2.connect(**DB_CONFIG) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT nombres, apellido_p, apellido_m, mes, anho, total
                        FROM uchile.transparencia
                        WHERE apellido_p = %s
                        ORDER BY total DESC
                        LIMIT 250
                        """,
                        (ap,),
                    )
                    resultados = cur.fetchall()
        except Exception as e:
            error = str(e)

    return render_template("index.html", ap=ap, resultados=resultados, error=error)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
