from datetime import datetime
import json
import re
import subprocess
import time
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

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

COOKIE_JAR = "/tmp/futgal_cookies.txt"


def limpiar_texto(texto: str) -> str:
    return re.sub(r"\s+", " ", texto or "").strip()


def es_numero_decimal(texto: str) -> bool:
    return bool(re.fullmatch(r"\d+[,\.]\d+", texto.strip()))


def preparar_sesion_cookies() -> None:
    subprocess.run(
        [
            "curl",
            "-sL",
            "--compressed",
            "--max-time",
            "15",
            "-c",
            COOKIE_JAR,
            "-b",
            COOKIE_JAR,
            "-A",
            USER_AGENT,
            "-H",
            "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "-H",
            "Accept-Language: es-ES,es;q=0.9,gl;q=0.8",
            "https://www.futgal.es/",
        ],
        capture_output=True,
        check=False,
    )


def descargar_html(url: str) -> tuple[str, str]:
    proc = subprocess.run(
        [
            "curl",
            "-sL",
            "--compressed",
            "--max-time",
            "15",
            "-c",
            COOKIE_JAR,
            "-b",
            COOKIE_JAR,
            "-A",
            USER_AGENT,
            "-e",
            "https://www.futgal.es/",
            "-H",
            "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "-H",
            "Accept-Language: es-ES,es;q=0.9,gl;q=0.8",
            "-w",
            "\n__HTTP_CODE__:%{http_code}",
            url,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    salida = proc.stdout or ""
    if "\n__HTTP_CODE__:" in salida:
        cuerpo, codigo = salida.rsplit("\n__HTTP_CODE__:", 1)
        code = codigo.strip()
        if cuerpo.strip():
            return cuerpo, f"curl_cookie:{code}"
        return "", f"curl_cookie:{code}_vacio"
    return "", "curl_cookie:sin_codigo"


def extraer_de_html(html: str) -> tuple[list[dict], str]:
    soup = BeautifulSoup(html, "html.parser")
    top3 = []

    for fila in soup.select("table tr"):
        celdas = [limpiar_texto(td.get_text()) for td in fila.find_all(["td", "th"])]
        celdas_no_vacias = [c for c in celdas if c != ""]
        if len(celdas_no_vacias) < 3:
            continue

        posicion = None
        idx_pos = -1
        for i in range(min(2, len(celdas_no_vacias))):
            m = re.fullmatch(r"([1-3])[º\.]?", celdas_no_vacias[i])
            if m:
                posicion = int(m.group(1))
                idx_pos = i
                break

        if posicion is None:
            continue

        equipo = ""
        for c in celdas_no_vacias[idx_pos + 1 :]:
            if re.fullmatch(r"[\d,\.\-\s]+", c):
                continue
            if len(c) >= 2:
                equipo = c
                break

        if not equipo:
            continue

        enteros = []
        for c in celdas_no_vacias[idx_pos + 1 :]:
            if c == equipo or es_numero_decimal(c):
                continue
            for num_str in re.findall(r"\b\d+\b", c):
                enteros.append(int(num_str))

        if len(enteros) < 2:
            continue

        if any(item["pos"] == posicion for item in top3):
            continue

        top3.append({
            "pos": posicion,
            "equipo": equipo,
            "pts": enteros[0],
            "pj": enteros[1],
        })

        if len(top3) == 3:
            break

    top3 = sorted(top3, key=lambda x: x["pos"])
    titulo = limpiar_texto(soup.title.get_text()) if soup.title else "sin titulo"
    num_tablas = len(soup.select("table"))
    num_filas = len(soup.select("table tr"))
    info = f"title='{titulo[:45]}' tablas={num_tablas} filas={num_filas} len_html={len(html)}"
    return top3, info


def obtener_top3_grupo(cod_grupo: str) -> tuple[list[dict], str]:
    urls = [
        (
            f"https://www.futgal.es/pnfg/NPcd/NFG_VisClasificacion"
            f"?cod_primaria={COD_PRIMARIA}"
            f"&codcompeticion={COD_COMPETICION}"
            f"&codgrupo={cod_grupo}"
            f"&codtemporada={COD_TEMPORADA}"
        ),
        (
            f"https://www.futgal.es/pnfg/NPcd/NFG_CmpClasificacion"
            f"?cod_primaria={COD_PRIMARIA}"
            f"&CodCompeticion={COD_COMPETICION}"
            f"&CodGrupo={cod_grupo}"
            f"&CodTemporada={COD_TEMPORADA}"
        ),
    ]

    ultimo_info = ""
    for url in urls:
        html, via = descargar_html(url)
        top3, info = extraer_de_html(html)
        ultimo_info = f"{info} via={via} url={url.split('?')[0].split('/')[-1]}"
        if len(top3) >= 1:
            return top3, ultimo_info

    return [], ultimo_info


def main():
    preparar_sesion_cookies()
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
        url_web = (
            f"https://www.futgal.es/pnfg/NPcd/NFG_VisClasificacion"
            f"?cod_primaria={COD_PRIMARIA}&codcompeticion={COD_COMPETICION}"
            f"&codgrupo={cod}&codtemporada={COD_TEMPORADA}"
        )
        try:
            top3, info = obtener_top3_grupo(cod)
            resultado["grupos"].append({
                "grupo": num,
                "cod_grupo": cod,
                "url_jornada": url_web,
                "top3": top3,
                "estado": "ok" if top3 else "sin_datos",
            })
            if top3:
                print(f"Grupo {num:02d} ({cod}): {len(top3)} equipos extraídos")
            else:
                print(f"Grupo {num:02d} ({cod}): 0 equipos extraídos [{info}]")
        except Exception as exc:
            resultado["grupos"].append({
                "grupo": num,
                "cod_grupo": cod,
                "url_jornada": url_web,
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
