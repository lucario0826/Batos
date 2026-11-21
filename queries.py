"""Consultas sobre videojuegos (estilo SteamDB) para el buscador de la página de inicio.

Mientras DB_DEMO=true (por defecto) se usa una base SQLite en memoria con juegos
inventados. Con DB_DEMO=false se consulta PostgreSQL con DB_CONFIG.

Esquema esperado (placeholder, ajustar a la base real):
  CREATE TABLE games (
    appid INT PRIMARY KEY, name TEXT,
    positive INT, negative INT,                 -- reseñas positivas / negativas
    windows BOOLEAN, linux BOOLEAN, mac BOOLEAN,
    average_playtime INT                        -- media jugada en total, en minutos
  );
"""
import random
import re
import sqlite3
import unicodedata

import psycopg2

RATIO = "ROUND(CAST(100.0 * positive / NULLIF(positive + negative, 0) AS NUMERIC), 1)"

# (palabras clave, título, SQL)
PRESETS = [
    (["jugad", "played", "horas", "tiempo"], "Más jugados (media de tiempo jugado)",
     "SELECT name, ROUND(CAST(average_playtime / 60.0 AS NUMERIC), 1) AS horas_media, positive + negative AS reseñas\n"
     "FROM games ORDER BY average_playtime DESC LIMIT 20"),
    (["mejor", "valorad", "top", "rated"], "Mejor valorados (≥1000 reseñas)",
     f"SELECT name, {RATIO} AS pct_positivo, positive + negative AS reseñas\n"
     "FROM games WHERE positive + negative >= 1000 ORDER BY pct_positivo DESC LIMIT 20"),
    (["peor", "odiad", "negativ", "worst"], "Peor valorados (≥1000 reseñas)",
     f"SELECT name, {RATIO} AS pct_positivo, negative\n"
     "FROM games WHERE positive + negative >= 1000 ORDER BY pct_positivo ASC LIMIT 20"),
    (["popular", "reseña", "review"], "Más populares (volumen de reseñas)",
     f"SELECT name, positive + negative AS reseñas, {RATIO} AS pct_positivo\n"
     "FROM games ORDER BY reseñas DESC LIMIT 20"),
    (["polemic", "divis", "controvers"], "Más polémicos (cerca de 50/50)",
     f"SELECT name, {RATIO} AS pct_positivo, positive + negative AS reseñas\n"
     "FROM games WHERE positive + negative >= 1000\n"
     "ORDER BY ABS(100.0 * positive / (positive + negative) - 50) ASC LIMIT 20"),
    (["joya", "ocult", "gem", "infravalor"], "Joyas ocultas (muy buenos, poco conocidos)",
     f"SELECT name, {RATIO} AS pct_positivo, positive + negative AS reseñas\n"
     "FROM games WHERE positive + negative BETWEEN 50 AND 2000\n"
     "ORDER BY pct_positivo DESC, reseñas DESC LIMIT 20"),
    (["linux"], "Mejores juegos con soporte Linux",
     f"SELECT name, {RATIO} AS pct_positivo, positive + negative AS reseñas\n"
     "FROM games WHERE linux = TRUE AND positive + negative >= 500 ORDER BY pct_positivo DESC LIMIT 20"),
    (["mac"], "Mejores juegos con soporte Mac",
     f"SELECT name, {RATIO} AS pct_positivo, positive + negative AS reseñas\n"
     "FROM games WHERE mac = TRUE AND positive + negative >= 500 ORDER BY pct_positivo DESC LIMIT 20"),
    (["solo windows", "exclusiv"], "Exclusivos de Windows más populares",
     "SELECT name, positive + negative AS reseñas\n"
     "FROM games WHERE windows = TRUE AND linux = FALSE AND mac = FALSE ORDER BY reseñas DESC LIMIT 20"),
    (["plataforma", "compar", "multiplat"], "Comparativa por plataforma",
     "SELECT 'windows' AS plataforma, COUNT(*) AS juegos, ROUND(CAST(AVG(average_playtime)/60.0 AS NUMERIC),1) AS horas_media,\n"
     "  ROUND(CAST(100.0*SUM(positive)/NULLIF(SUM(positive+negative),0) AS NUMERIC),1) AS pct_positivo FROM games WHERE windows = TRUE\n"
     "UNION ALL SELECT 'linux', COUNT(*), ROUND(CAST(AVG(average_playtime)/60.0 AS NUMERIC),1),\n"
     "  ROUND(CAST(100.0*SUM(positive)/NULLIF(SUM(positive+negative),0) AS NUMERIC),1) FROM games WHERE linux = TRUE\n"
     "UNION ALL SELECT 'mac', COUNT(*), ROUND(CAST(AVG(average_playtime)/60.0 AS NUMERIC),1),\n"
     "  ROUND(CAST(100.0*SUM(positive)/NULLIF(SUM(positive+negative),0) AS NUMERIC),1) FROM games WHERE mac = TRUE"),
    (["engancha", "adict", "retencion"], "Más adictivos (horas por reseña)",
     "SELECT name, ROUND(CAST(average_playtime / 60.0 AS NUMERIC), 1) AS horas_media,\n"
     "  ROUND(CAST(average_playtime * 1.0 / NULLIF(positive + negative, 0) AS NUMERIC), 3) AS min_por_reseña\n"
     "FROM games WHERE positive + negative >= 1000 ORDER BY min_por_reseña DESC LIMIT 20"),
    (["abandon", "rapido", "corto"], "Populares pero poco jugados (¿abandonados?)",
     "SELECT name, positive + negative AS reseñas, ROUND(CAST(average_playtime / 60.0 AS NUMERIC), 1) AS horas_media\n"
     "FROM games WHERE positive + negative >= 5000 ORDER BY average_playtime ASC LIMIT 20"),
]

EXAMPLES = ["más jugados", "mejor valorados", "peor valorados", "más populares", "polémicos",
            "joyas ocultas", "mejores en linux", "mejores en mac", "exclusivos windows",
            "comparar plataformas", "más adictivos", "abandonados"]


def _norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def resolve(q):
    """Devuelve (titulo, sql). Se permite un SELECT/WITH directo; si no, se busca un preset."""
    if re.match(r"^\s*(select|with)\b", q, re.I):
        if ";" in q.strip().rstrip(";"):
            raise ValueError("Solo una sentencia.")
        return "Query manual", q.strip().rstrip(";")
    nq = _norm(q)
    for keys, title, sql in PRESETS:
        if any(k in nq for k in keys):
            return title, sql
    raise ValueError("No entendí la pregunta. Prueba con uno de los ejemplos o escribe un SELECT.")


def _demo_db():
    """Juegos inventados para tener datos mientras no está la base real."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE games (appid INT, name TEXT, positive INT, negative INT, "
                 "windows BOOLEAN, linux BOOLEAN, mac BOOLEAN, average_playtime INT)")
    rng = random.Random(7)
    words = ["Iron", "Pixel", "Void", "Neon", "Crypt", "Star", "Hollow", "Rogue", "Dust", "Echo",
             "Frost", "Orbit", "Ember", "Quartz", "Shadow", "Delta"]
    tails = ["Protocol", "Legends", "Tactics", "Odyssey", "Drift", "Saga", "Frontier", "Keeper", "Run", "Forge"]
    rows = []
    for i in range(400):
        tot = int(rng.paretovariate(1.1) * 40)
        pos = int(tot * rng.betavariate(5, 1.5))
        rows.append((1000 + i, f"{rng.choice(words)} {rng.choice(tails)} {i}", pos, tot - pos,
                     True, rng.random() < .35, rng.random() < .3, int(rng.expovariate(1 / 600))))
    conn.executemany("INSERT INTO games VALUES (?,?,?,?,?,?,?,?)", rows)
    return conn


def run(sql, db_config, demo):
    """Ejecuta la consulta en modo solo lectura y devuelve (columnas, filas)."""
    if demo:
        conn = _demo_db()
    else:
        conn = psycopg2.connect(**db_config)
        conn.set_session(readonly=True, autocommit=True)
    try:
        cur = conn.cursor()
        cur.execute(sql)
        return [d[0] for d in cur.description], cur.fetchmany(200)
    finally:
        conn.close()
