import os
import psycopg2
from flask import Flask, render_template, request
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", "")),
    "dbname": os.environ.get("DB_NAME", "cc3201"),
    "user": os.environ.get("DB_USER", "webuser"),
    "password": os.environ.get("DB_PASSWORD", ""),
}

def query_db(sql, params=()):
    """Abre conexión, ejecuta la consulta y devuelve las filas."""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/consulta1", methods=["GET"])
def consulta1():
    q = request.args.get("q", "").strip()
    gen = request.args.get("genero", "").strip()
    plat = request.args.get("plataforma", "").strip()

    generos = []
    plataformas = []
    resultados = []
    error = None

    try:
        generos = query_db("SELECT generoid, genero FROM public.generos ORDER BY genero;")
        plataformas = query_db("SELECT plataformaid, plataforma FROM public.plataformas ORDER BY plataforma;")
        resultados = query_db("""
            SELECT DISTINCT j.gameid, j.nombre, j.fechalanzamiento, j.precio,
                            j.cantidadresenhaspositivas, j.cantidadresenhasnegativas
            FROM public.juego j
            LEFT JOIN public.clasificadoen cl ON j.gameid = cl.gameid
            LEFT JOIN public.disponibleen di ON j.gameid = di.gameid
            WHERE (%s = '' OR j.nombre ILIKE %s)
              AND (%s = '' OR cl.generoid::text = %s)
              AND (%s = '' OR di.plataformaid::text = %s)
            ORDER BY j.cantidadresenhaspositivas DESC
            LIMIT 50;
        """, (q, f"%{q}%", gen, gen, plat, plat))
    except Exception as e:
        error = str(e)

    return render_template(
        "consulta1.html",
        generos=generos,
        plataformas=plataformas,
        q=q,
        genero_sel=gen,
        plataforma_sel=plat,
        resultados=resultados,
        error=error,
    )


@app.route("/consulta2", methods=["GET"])
def consulta2():
    cat = request.args.get("categoria", "").strip()
    min_j = int(request.args.get("min_juegos") or 3)

    categorias = []
    resultados = []
    error = None

    try:
        categorias = query_db("SELECT categoriaid, categoria FROM public.categorias ORDER BY categoria;")

        resultados = query_db("""
            SELECT d.nombredesarrollador, COUNT(DISTINCT j.gameid),
                   SUM(j.cantidadresenhaspositivas), SUM(j.cantidadresenhasnegativas),
                   ROUND(SUM(j.cantidadresenhaspositivas) * 100.0 /
                         NULLIF(SUM(j.cantidadresenhaspositivas + j.cantidadresenhasnegativas), 0), 1) || '%'
            FROM public.desarrolladores d
            JOIN public.creadopor cp ON d.desarrolladorid = cp.desarrolladorid
            JOIN public.juego j ON cp.gameid = j.gameid
            LEFT JOIN public.posee po ON j.gameid = po.gameid
            WHERE (%s = '' OR po.categoriaid::text = %s)
            GROUP BY d.desarrolladorid, d.nombredesarrollador
            HAVING COUNT(DISTINCT j.gameid) >= %s
            ORDER BY SUM(j.cantidadresenhaspositivas) DESC
            LIMIT 50;
        """, (cat, cat, min_j))
    except Exception as e:
        error = str(e)

    return render_template(
        "consulta2.html",
        categorias=categorias,
        categoria_sel=cat,
        min_juegos=min_j,
        resultados=resultados,
        error=error,
    )

@app.route("/consulta3", methods=["GET"])
def consulta3():
    idioma = request.args.get("idioma", "").strip()

    resultados = []
    error = None

    try:
        resultados = query_db("""
            SELECT g.genero, COUNT(DISTINCT j.gameid),
                   ROUND(AVG(j.averageplaytime), 1), ROUND(AVG(j.medianplaytime), 1),
                   SUM(j.cantidadresenhaspositivas)
            FROM public.generos g
            JOIN public.clasificadoen cl ON g.generoid = cl.generoid
            JOIN public.juego j ON cl.gameid = j.gameid
            WHERE (%s = '' OR j.english::text = %s)
            GROUP BY g.generoid, g.genero
            ORDER BY COUNT(DISTINCT j.gameid) DESC;
        """, (idioma, idioma))
    except Exception as e:
        error = str(e)

    return render_template(
        "consulta3.html",
        idioma_sel=idioma,
        resultados=resultados,
        error=error,
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
