from datetime import datetime
import json
import re
import time
import urllib.request
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

COD_COMPETICION = "26991813"
COD_TEMPORADA = "22"
COD_PRIMARIA = "1000120"

GRUPOS = [
    {"grupo": 1, "cod_grupo": "28767141"},
    {"grupo": 2, "cod_grupo": "28767176"},
    {"grupo": 3, "cod_grupo": "28767199"},
    {"grupo": 4, "cod_grupo": "28767203"},
    {"grupo": 5, "cod_grupo": "28767240"},
    {"grupo": 6, "cod_grupo": "28767243"},
    {"grupo": 7, "cod_grupo": "28767271"},
    {"grupo": 8, "cod_grupo": "28767276"},
    {"grupo": 9, "cod_grupo": "28767279"},
    {"grupo": 10, "cod_grupo": "28767351"},
    {"grupo": 11, "cod_grupo": "28767370"},
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
    )
}


def limpiar_texto(texto: str) -> str:
    return re.sub(r"\s+", " ", texto or "").strip()


def es_numero_decimal(texto: str) -> bool:
    return bool(re.fullmatch(r"\d+[,\.]\d+", texto.strip()))


def obtener_top3_grupo(cod_grupo: str) -> list[dict]:
    url = (
        f"https://www.futgal.es/pnfg/NPcd/NFG_VisClasificacion"
        f"?cod_primaria={COD_PRIMARIA}"
        f"&codcompeticion={COD_COMPETICION}"
        f"&codgrupo={cod_grupo}"
        f"&codtemporada={COD_TEMPORADA}"
    )

    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    soup = BeautifulSoup(html, "html.parser")
    top3 = []

    for fila in soup.select("table tr"):
        celdas = [limpiar_texto(td.get_text()) for td in fila.find_all(["td", "th"])]
        celdas = [c for c in celdas if c != ""]
        if len(celdas) < 4:
            continue

        pos_match = re.fullmatch(r"([1-3])[º\.]?", celdas[0])
        if not pos_match:
            continue

        posicion = int(pos_match.group(1))
        equipo = celdas[1]

        enteros = []
        for celda in celdas[2:]:
            if es_numero_decimal(celda):
                continue
            for m in re.findall(r"\b\d+\b", celda):
                enteros.append(int(m))

        if not equipo or len(enteros) < 2:
            continue

        top3.append({
            "pos": posicion,
            "equipo": equipo,
            "pts": enteros[0],
            "pj": enteros[1],
        })

        if len(top3) == 3:
            break

    return sorted(top3, key=lambda x: x["pos"])


def main():
    ahora_es = datetime.now(ZoneInfo("Europe/Madrid")).strftime("%d/%m %H:%M")

    resultado = {
        "competicion": "BENJAMIN F-8 - SEGUNDA FUTGAL",
        "zona": "Vigo · 1ª Fase",
        "cod_competicion": COD_COMPETICION,
        "cod_temporada": COD_TEMPORADA,
        "actualizado_en": ahora_es,
        "grupos": [],
    }

    for idx, item in enumerate(GRUPOS):
        cod = item["cod_grupo"]
        num = item["grupo"]
        try:
            top3 = obtener_top3_grupo(cod)
            resultado["grupos"].append({
                "grupo": num,
                "cod_grupo": cod,
                "url_jornada": (
                    f"https://www.futgal.es/pnfg/NPcd/NFG_VisClasificacion"
                    f"?cod_primaria={COD_PRIMARIA}&codcompeticion={COD_COMPETICION}"
                    f"&codgrupo={cod}&codtemporada={COD_TEMPORADA}"
                ),
                "top3": top3,
                "estado": "ok" if top3 else "sin_datos",
            })
            print(f"Grupo {num:02d} ({cod}): {len(top3)} equipos extraídos")
        except Exception as exc:
            resultado["grupos"].append({
                "grupo": num,
                "cod_grupo": cod,
                "url_jornada": (
                    f"https://www.futgal.es/pnfg/NPcd/NFG_VisClasificacion"
                    f"?cod_primaria={COD_PRIMARIA}&codcompeticion={COD_COMPETICION}"
                    f"&codgrupo={cod}&codtemporada={COD_TEMPORADA}"
                ),
                "top3": [],
                "estado": f"error: {exc}",
            })
            print(f"Grupo {num:02d} ({cod}): error -> {exc}")

        if idx < len(GRUPOS) - 1:
            time.sleep(0.6)

    with open("datos.json", "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(f"Archivo datos.json generado ({ahora_es}).")


if __name__ == "__main__":
    main()
