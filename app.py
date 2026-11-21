import os
from flask import Flask, render_template


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
    return render_template("index.html")


@app.route("/consulta1", methods=["GET"])
def consulta1():
    # TODO: Conectar Consulta 1 
    return render_template("consulta1.html")


@app.route("/consulta2", methods=["GET"])
def consulta2():
    # TODO: Conectar Consulta 2 
    return render_template("consulta2.html")


@app.route("/consulta3", methods=["GET"])
def consulta3():
    # TODO: Conectar Consulta 3 
    return render_template("consulta3.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)