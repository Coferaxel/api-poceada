import requests
from bs4 import BeautifulSoup
import json
import time
import re

# Rango de sorteos a escanear
RANGO_INICIO = 452
RANGO_FIN = 900 

lista_sorteos = []

print(f"--- INICIANDO ROBOT DE HISTORIAL ({RANGO_INICIO} a {RANGO_FIN}) ---")

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

for id_sorteo in range(RANGO_INICIO, RANGO_FIN):
    url = f"https://loteria.chaco.gov.ar/detalle_poceada/{id_sorteo}"
    
    try:
        print(f"Procesando Sorteo {id_sorteo}...", end="")
        
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"❌ Error {response.status_code}")
            continue

        soup = BeautifulSoup(response.content, 'html.parser')

        # --- 1. EXTRAER NÚMEROS GANADORES ---
        numeros = []
        items_lista = soup.find_all("li", class_="results-list__item")
        
        for item in items_lista:
            parrafos = item.find_all("p", class_="results-number")
            if len(parrafos) == 2:
                texto_numero = parrafos[1].text.strip()
                if texto_numero.isdigit():
                    numeros.append(int(texto_numero))
        
        numeros = sorted(list(set(numeros[:10])))

        if len(numeros) < 5:
            print("⚠️ Sin datos, saltando...")
            continue

        # --- 2. EXTRAER PREMIOS ---
        datos_premios = {
            "pozo5": "$0", "gan5": 0, "vacante5": False,
            "pozo4": "$0", "gan4": 0,
            "pozo3": "$0", "gan3": 0,
            "pozo2": "$0", "gan2": 0
        }

        header_premios = soup.find("h4", string=re.compile("Pozos Quiniela Poceada"))
        
        if header_premios:
            card_body = header_premios.find_parent("div", class_="card").find("article", class_="card-body")
            filas_premios = card_body.find_all("li", class_="results-list__item")

            def limpiar(txt):
                return txt.replace("\n", "").strip()

            if len(filas_premios) > 1:
                col = filas_premios[1].find_all("p", class_="results-number")
                if len(col) >= 4:
                    datos_premios["pozo5"] = limpiar(col[1].text)
                    cant = limpiar(col[2].text)
                    if cant == "VACANTE" or cant == "0":
                        datos_premios["vacante5"] = True
                        datos_premios["gan5"] = 0
                    else:
                        datos_premios["gan5"] = int(cant.replace(".", ""))

            if len(filas_premios) > 2:
                col = filas_premios[2].find_all("p", class_="results-number")
                if len(col) >= 4:
                    datos_premios["gan4"] = int(limpiar(col[2].text).replace(".", ""))
                    datos_premios["pozo4"] = limpiar(col[3].text)

            if len(filas_premios) > 3:
                col = filas_premios[3].find_all("p", class_="results-number")
                if len(col) >= 4:
                    datos_premios["gan3"] = int(limpiar(col[2].text).replace(".", ""))
                    datos_premios["pozo3"] = limpiar(col[3].text)

            if len(filas_premios) > 4:
                col = filas_premios[4].find_all("p", class_="results-number")
                if len(col) >= 4:
                    datos_premios["gan2"] = int(limpiar(col[2].text).replace(".", ""))
                    datos_premios["pozo2"] = limpiar(col[3].text)

        # --- 3. ARMAR OBJETO ---
        objeto_sorteo = {
            "numeroSorteo": id_sorteo,
            "fecha": "2024-01-01", 
            "numerosGanadores": numeros,
            "pozo5aciertos": datos_premios["pozo5"],
            "vacante5aciertos": datos_premios["vacante5"],
            "ganadores4aciertos": datos_premios["gan4"],
            "premio4aciertos": datos_premios["pozo4"],
            "ganadores3aciertos": datos_premios["gan3"],
            "premio3aciertos": datos_premios["pozo3"],
            "ganadores2aciertos": datos_premios["gan2"],
            "premio2aciertos": datos_premios["pozo2"],
            "pozoEstimadoProximo": "Ver próximo sorteo", 
            "fechaProximo": ""
        }
        
        lista_sorteos.insert(0, objeto_sorteo)
        print(f"✅ OK ({len(numeros)} nums)")
        time.sleep(0.1)

    except Exception as e:
        print(f"❌ Error procesando: {e}")

# GUARDAR JSON
with open('datos_poceada.json', 'w', encoding='utf-8') as f:
    json.dump(lista_sorteos, f, indent=4, ensure_ascii=False)

print(f"\n✨ FINALIZADO: {len(lista_sorteos)} sorteos guardados en 'datos_poceada.json'")