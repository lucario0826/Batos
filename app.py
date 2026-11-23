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
    joyas_ocultas = []
    top_windows = []
    top_mac = []
    top_linux = []
    error = None

    sql_plataforma = """
        SELECT j.nombre,
               ROUND(j.cantidadresenhaspositivas * 100.0 /
                     (j.cantidadresenhaspositivas + j.cantidadresenhasnegativas), 1) || '%',
               j.cantidadresenhaspositivas,
               j.cantidadresenhasnegativas
        FROM juego j
        JOIN disponibleen di ON j.gameid = di.gameid
        JOIN plataformas p ON di.plataformaid = p.plataformaid
        WHERE LOWER(p.plataforma) = %s
          AND (j.cantidadresenhaspositivas + j.cantidadresenhasnegativas) >= 1000
        ORDER BY j.cantidadresenhaspositivas * 100.0 /
                 (j.cantidadresenhaspositivas + j.cantidadresenhasnegativas) DESC,
                 j.cantidadresenhaspositivas DESC
        LIMIT 5;
    """

    try:
        joyas_ocultas = query_db("""
            SELECT j.nombre,
                   ROUND(j.cantidadresenhaspositivas * 100.0 /
                         (j.cantidadresenhaspositivas + j.cantidadresenhasnegativas), 1) || '%',
                   j.cantidadresenhaspositivas,
                   j.cantidadresenhasnegativas
            FROM juego j
            WHERE (j.cantidadresenhaspositivas + j.cantidadresenhasnegativas) BETWEEN 50 AND 2000
              AND j.cantidadresenhaspositivas * 100.0 /
                  (j.cantidadresenhaspositivas + j.cantidadresenhasnegativas) >= 85
            ORDER BY j.cantidadresenhaspositivas * 100.0 /
                     (j.cantidadresenhaspositivas + j.cantidadresenhasnegativas) DESC,
                     j.cantidadresenhaspositivas DESC
            LIMIT 20;
        """)
        top_windows = query_db(sql_plataforma, ("windows",))
        top_mac = query_db(sql_plataforma, ("mac",))
        top_linux = query_db(sql_plataforma, ("linux",))
    except Exception as e:
        error = str(e)

    return render_template(
        "index.html",
        joyas_ocultas=joyas_ocultas,
        top_windows=top_windows,
        top_mac=top_mac,
        top_linux=top_linux,
        error=error,
    )


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
        generos = query_db("SELECT generoid, genero FROM generos ORDER BY genero;")
        plataformas = query_db("SELECT plataformaid, plataforma FROM plataformas ORDER BY plataforma;")

        joins = []
        conds = []
        params = []

        if q:
            conds.append("j.nombre ILIKE %s")
            params.append(f"%{q}%")
        if gen:
            joins.append("JOIN clasificadoen cl ON j.gameid = cl.gameid")
            conds.append("cl.generoid = %s")
            params.append(gen)
        if plat:
            joins.append("JOIN disponibleen di ON j.gameid = di.gameid")
            conds.append("di.plataformaid = %s")
            params.append(plat)

        where = f"WHERE {' AND '.join(conds)}" if conds else ""

        sql = f"""
            SELECT j.gameid, j.nombre, j.fechalanzamiento, j.precio,
                   j.cantidadresenhaspositivas, j.cantidadresenhasnegativas
            FROM juego j
            {' '.join(joins)}
            {where}
            ORDER BY j.cantidadresenhaspositivas DESC NULLS LAST
            LIMIT 50;
        """
        resultados = query_db(sql, tuple(params))
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
    min_j_raw = request.args.get("min_juegos", "").strip()

    categorias = []
    resultados = []
    error = None
    min_j = 3

    try:
        min_j = max(1, int(min_j_raw)) if min_j_raw else 3
        categorias = query_db("SELECT categoriaid, categoria FROM categorias ORDER BY categoria;")

        if cat:
            resultados = query_db("""
                SELECT d.nombredesarrollador,
                       COUNT(j.gameid),
                       SUM(j.cantidadresenhaspositivas),
                       SUM(j.cantidadresenhasnegativas),
                       ROUND(SUM(j.cantidadresenhaspositivas) * 100.0 /
                             NULLIF(SUM(j.cantidadresenhaspositivas + j.cantidadresenhasnegativas), 0), 1) || '%'
                FROM desarrolladores d
                JOIN creadopor cp ON d.desarrolladorid = cp.desarrolladorid
                JOIN juego j ON cp.gameid = j.gameid
                JOIN posee po ON j.gameid = po.gameid
                WHERE po.categoriaid = %s
                GROUP BY d.desarrolladorid, d.nombredesarrollador
                HAVING COUNT(j.gameid) >= %s
                ORDER BY SUM(j.cantidadresenhaspositivas) DESC NULLS LAST
                LIMIT 50;
            """, (cat, min_j))
        else:
            resultados = query_db("""
                SELECT d.nombredesarrollador,
                       COUNT(j.gameid),
                       SUM(j.cantidadresenhaspositivas),
                       SUM(j.cantidadresenhasnegativas),
                       ROUND(SUM(j.cantidadresenhaspositivas) * 100.0 /
                             NULLIF(SUM(j.cantidadresenhaspositivas + j.cantidadresenhasnegativas), 0), 1) || '%'
                FROM desarrolladores d
                JOIN creadopor cp ON d.desarrolladorid = cp.desarrolladorid
                JOIN juego j ON cp.gameid = j.gameid
                GROUP BY d.desarrolladorid, d.nombredesarrollador
                HAVING COUNT(j.gameid) >= %s
                ORDER BY SUM(j.cantidadresenhaspositivas) DESC NULLS LAST
                LIMIT 50;
            """, (min_j,))
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
            FROM generos g
            JOIN clasificadoen cl ON g.generoid = cl.generoid
            JOIN juego j ON cl.gameid = j.gameid
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
