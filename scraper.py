import requests
from bs4 import BeautifulSoup
import json
import time
import re

# Ajusta el rango según lo que necesites
RANGO_INICIO = 452
RANGO_FIN = 900 

lista_sorteos = []
print(f"--- ROBOT DE HISTORIAL MEJORADO ({RANGO_INICIO}-{RANGO_FIN}) ---")

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

for id_sorteo in range(RANGO_INICIO, RANGO_FIN):
    url = f"https://loteria.chaco.gov.ar/detalle_poceada/{id_sorteo}"
    
    try:
        print(f"Sorteo {id_sorteo}...", end="")
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print("❌ Error web")
            continue

        soup = BeautifulSoup(response.content, 'html.parser')

        # 1. EXTRAER FECHA (Del link al PDF)
        # Buscamos un enlace que contenga "POCEADA" y termine en ".pdf"
        fecha_sorteo = "Fecha no encontrada"
        link_pdf = soup.find('a', href=re.compile(r'POCEADA.*\d{2}-\d{2}-\d{4}.*\.pdf', re.IGNORECASE))
        
        if link_pdf:
            href = link_pdf['href']
            # Usamos expresión regular para sacar la fecha DD-MM-YYYY
            match = re.search(r'(\d{2}-\d{2}-\d{4})', href)
            if match:
                fecha_str = match.group(1)
                # Convertimos de 18-11-2025 a formato ISO 2025-11-18 para que Flutter lo entienda fácil
                dia, mes, anio = fecha_str.split('-')
                fecha_sorteo = f"{anio}-{mes}-{dia} 21:00:00"

        # 2. EXTRAER NÚMEROS
        numeros = []
        items_lista = soup.find_all("li", class_="results-list__item")
        for item in items_lista:
            parrafos = item.find_all("p", class_="results-number")
            if len(parrafos) == 2:
                txt = parrafos[1].text.strip()
                if txt.isdigit(): numeros.append(int(txt))
        
        numeros = sorted(list(set(numeros[:10])))
        if len(numeros) < 5:
            print("⚠️ Sin números")
            continue

        # 3. EXTRAER PREMIOS (Lógica robusta)
        datos_premios = {
            "pozo5": "$0", "gan5": 0, "vacante5": False,
            "pozo4": "$0", "gan4": 0,
            "pozo3": "$0", "gan3": 0,
            "pozo2": "$0", "gan2": 0
        }
        
        # Buscamos la tabla de premios
        header_premios = soup.find("h4", string=re.compile("Pozos Quiniela Poceada"))
        if header_premios:
            card_body = header_premios.find_parent("div", class_="card").find("article", class_="card-body")
            filas = card_body.find_all("li", class_="results-list__item")
            
            def limpio(t): return t.replace("\n", "").strip()

            # Mapeamos las filas sabiendo el orden fijo del HTML
            if len(filas) > 1: # 5 Aciertos
                cols = filas[1].find_all("p", class_="results-number")
                if len(cols) >= 4:
                    datos_premios["pozo5"] = limpio(cols[1].text)
                    gan = limpio(cols[2].text)
                    datos_premios["vacante5"] = (gan == "VACANTE" or gan == "0")
                    datos_premios["gan5"] = 0 if datos_premios["vacante5"] else int(gan.replace(".",""))

            if len(filas) > 2: # 4 Aciertos
                cols = filas[2].find_all("p", class_="results-number")
                if len(cols) >= 4:
                    datos_premios["gan4"] = int(limpio(cols[2].text).replace(".",""))
                    datos_premios["pozo4"] = limpio(cols[3].text)

            if len(filas) > 3: # 3 Aciertos
                cols = filas[3].find_all("p", class_="results-number")
                if len(cols) >= 4:
                    datos_premios["gan3"] = int(limpio(cols[2].text).replace(".",""))
                    datos_premios["pozo3"] = limpio(cols[3].text)

            if len(filas) > 4: # 2 Aciertos
                cols = filas[4].find_all("p", class_="results-number")
                if len(cols) >= 4:
                    datos_premios["gan2"] = int(limpio(cols[2].text).replace(".",""))
                    datos_premios["pozo2"] = limpio(cols[3].text)

        # 4. ARMAR OBJETO
        obj = {
            "numeroSorteo": id_sorteo,
            "fecha": fecha_sorteo, # ¡Ahora sí tiene la fecha real!
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
        
        lista_sorteos.insert(0, obj)
        print(f"✅ OK ({fecha_sorteo})")
        time.sleep(0.1)

    except Exception as e:
        print(f"❌ Error: {e}")

with open('datos_poceada.json', 'w', encoding='utf-8') as f:
    json.dump(lista_sorteos, f, indent=4, ensure_ascii=False)

print(f"\n✨ FINALIZADO: {len(lista_sorteos)} sorteos.")