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

def query_db(sql, params=None):
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
                     (j.cantidadresenhaspositivas + j.cantidadresenhasnegativas), 1) || '%%',
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
                   j.cantidadduenhos,
                   ROUND(j.cantidadresenhaspositivas * 100.0 /
                         (j.cantidadresenhaspositivas + j.cantidadresenhasnegativas), 1) || '%',
                   j.cantidadresenhaspositivas,
                   j.cantidadresenhasnegativas
            FROM juego j
            WHERE j.cantidadduenhos = '0-20000'
              AND (j.cantidadresenhaspositivas + j.cantidadresenhasnegativas) >= 20
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
            try:
                gen_id = int(gen)
            except ValueError:
                gen_id = None
            if gen_id is not None:
                joins.append("JOIN clasificadoen cl ON j.gameid = cl.gameid")
                conds.append("cl.generoid = %s")
                params.append(gen_id)
        if plat:
            try:
                plat_id = int(plat)
            except ValueError:
                plat_id = None
            if plat_id is not None:
                joins.append("JOIN disponibleen di ON j.gameid = di.gameid")
                conds.append("di.plataformaid = %s")
                params.append(plat_id)

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
    try:
        min_j = max(1, int(min_j_raw)) if min_j_raw else 3
    except ValueError:
        min_j = 3

    try:
        categorias = query_db("SELECT categoriaid, categoria FROM categorias ORDER BY categoria;")

        cat_id = None
        if cat:
            try:
                cat_id = int(cat)
            except ValueError:
                cat_id = None

        if cat_id is not None:
            resultados = query_db("""
                SELECT d.nombredesarrollador,
                       COUNT(j.gameid),
                       SUM(j.cantidadresenhaspositivas),
                       SUM(j.cantidadresenhasnegativas),
                       COALESCE(ROUND(SUM(j.cantidadresenhaspositivas) * 100.0 /
                             NULLIF(SUM(j.cantidadresenhaspositivas + j.cantidadresenhasnegativas), 0), 1) || '%%', 'N/A')
                FROM desarrolladores d
                JOIN creadopor cp ON d.desarrolladorid = cp.desarrolladorid
                JOIN juego j ON cp.gameid = j.gameid
                JOIN posee po ON j.gameid = po.gameid
                WHERE po.categoriaid = %s
                GROUP BY d.desarrolladorid, d.nombredesarrollador
                HAVING COUNT(j.gameid) >= %s
                ORDER BY SUM(j.cantidadresenhaspositivas) DESC NULLS LAST
                LIMIT 50;
            """, (cat_id, min_j))
        else:
            resultados = query_db("""
                SELECT d.nombredesarrollador,
                       COUNT(j.gameid),
                       SUM(j.cantidadresenhaspositivas),
                       SUM(j.cantidadresenhasnegativas),
                       COALESCE(ROUND(SUM(j.cantidadresenhaspositivas) * 100.0 /
                             NULLIF(SUM(j.cantidadresenhaspositivas + j.cantidadresenhasnegativas), 0), 1) || '%%', 'N/A')
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
    gameid = request.args.get("gameid", "").strip()

    operador_fecha = request.args.get("operador_fecha", "").strip()
    operador_anio = request.args.get("operador_anio", "").strip()
    operador_tiempo = request.args.get("operador_tiempo", "").strip()
    operador_positivas = request.args.get("operador_positivas", "").strip()
    operador_negativas = request.args.get("operador_negativas", "").strip()

    resultados = []
    juegos = []
    referencia = None
    error = None

    operadores = {
        "mayor": ">",
        "menor": "<",
    }

    try:
        juegos = query_db("""
            SELECT gameid, nombre
            FROM juego
            ORDER BY nombre;
        """)

        if gameid:
            referencia = query_db("""
                SELECT gameid, nombre, fechalanzamiento,
                       EXTRACT(YEAR FROM fechalanzamiento),
                       averageplaytime,
                       cantidadresenhaspositivas,
                       cantidadresenhasnegativas
                FROM juego
                WHERE gameid = %s;
            """, (gameid,))

            if not referencia:
                raise ValueError("El juego seleccionado no existe.")

            conds = ["j.gameid <> %s"]
            params = [gameid]

            comparaciones = [
                ("operador_fecha", operador_fecha,
                 "j.fechalanzamiento", "r.fechalanzamiento"),
                ("operador_anio", operador_anio,
                 "EXTRACT(YEAR FROM j.fechalanzamiento)",
                 "EXTRACT(YEAR FROM r.fechalanzamiento)"),
                ("operador_tiempo", operador_tiempo,
                 "j.averageplaytime", "r.averageplaytime"),
                ("operador_positivas", operador_positivas,
                 "j.cantidadresenhaspositivas",
                 "r.cantidadresenhaspositivas"),
                ("operador_negativas", operador_negativas,
                 "j.cantidadresenhasnegativas",
                 "r.cantidadresenhasnegativas")
            ]

            for nombre_filtro, operador, columna_j, columna_r in comparaciones:
                if operador:
                    if operador not in operadores:
                        raise ValueError("Operador de comparación inválido.")

                    conds.append(
                        f"{columna_j} {operadores[operador]} ({columna_r})"
                    )


        resultados = query_db("""
                SELECT
                    j.gameid,
                    j.nombre,
                    j.fechalanzamiento,
                    EXTRACT(YEAR FROM j.fechalanzamiento) AS anio,
                    j.averageplaytime,
                    j.cantidadresenhaspositivas,
                    j.cantidadresenhasnegativas
                FROM juego j
                CROSS JOIN juego r
                WHERE r.gameid = %s
                  AND {" AND ".join(conds)}
                ORDER BY j.cantidadresenhaspositivas DESC NULLS LAST
                LIMIT 50;
        """, (gameid, *params))

    except Exception as e:
        error = str(e)

    return render_template(
        "consulta3.html",
        juegos=juegos,
        gameid=gameid,
        referencia=referencia,
        operador_fecha=operador_fecha,
        operador_anio=operador_anio,
        operador_tiempo=operador_tiempo,
        operador_positivas=operador_positivas,
        operador_negativas=operador_negativas,
        resultados=resultados,
        error=error
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
