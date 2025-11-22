import requests
from bs4 import BeautifulSoup
import json
import re
import os

# Nombre del archivo JSON
ARCHIVO_JSON = 'datos_poceada.json'

def actualizar_diario():
    print("--- INICIANDO ROBOT DIARIO ---")
    
    # 1. LEER EL ÚLTIMO SORTEO GUARDADO
    try:
        if os.path.exists(ARCHIVO_JSON):
            with open(ARCHIVO_JSON, 'r', encoding='utf-8') as f:
                historial = json.load(f)
        else:
            historial = []
    except Exception:
        historial = []
        
    # Buscamos el ID más alto que tengamos guardado
    ultimo_id = 451 # Base por defecto
    if historial:
        # Asumimos que el primero es el más nuevo
        ultimo_id = historial[0].get('numeroSorteo', 451)
    
    siguiente_id = ultimo_id + 1
    print(f"Último sorteo guardado: {ultimo_id}. Buscando el siguiente: {siguiente_id}...")

    # 2. INTENTAR DESCARGAR EL SIGUIENTE
    url = f"https://loteria.chaco.gov.ar/detalle_poceada/{siguiente_id}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers)
        
        # Si la web da error 404 o 500, es que todavía no se sorteó
        if response.status_code != 200:
            print(f"⚠️ El sorteo {siguiente_id} aún no está disponible (Código {response.status_code}).")
            return # Terminamos por hoy

        soup = BeautifulSoup(response.content, 'html.parser')

        # --- LÓGICA DE EXTRACCIÓN (LA MISMA QUE PROBAMOS Y FUNCIONA) ---
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
            print("⚠️ La página existe pero no tiene números cargados aún.")
            return

        # EXTRAER PREMIOS
        datos_premios = { "pozo5": "$0", "gan5": 0, "vacante5": False, "pozo4": "$0", "gan4": 0, "pozo3": "$0", "gan3": 0, "pozo2": "$0", "gan2": 0 }
        
        header_premios = soup.find("h4", string=re.compile("Pozos Quiniela Poceada"))
        if header_premios:
            card_body = header_premios.find_parent("div", class_="card").find("article", class_="card-body")
            filas_premios = card_body.find_all("li", class_="results-list__item")
            
            def limpiar(txt): return txt.replace("\n", "").strip()

            if len(filas_premios) > 1:
                col = filas_premios[1].find_all("p", class_="results-number")
                if len(col) >= 4:
                    datos_premios["pozo5"] = limpiar(col[1].text)
                    cant = limpiar(col[2].text)
                    datos_premios["vacante5"] = (cant == "VACANTE" or cant == "0")
                    datos_premios["gan5"] = 0 if datos_premios["vacante5"] else int(cant.replace(".", ""))

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

        # ARMAR OBJETO
        nuevo_sorteo = {
            "numeroSorteo": siguiente_id,
            "fecha": "Fecha Actual", # Podríamos usar datetime.now() aquí
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

        # 3. GUARDAR EL NUEVO SORTEO AL PRINCIPIO
        historial.insert(0, nuevo_sorteo)
        
        # Guardamos en disco
        with open(ARCHIVO_JSON, 'w', encoding='utf-8') as f:
            json.dump(historial, f, indent=4, ensure_ascii=False)
            
        print(f"✅ ¡ÉXITO! Sorteo {siguiente_id} agregado correctamente.")

    except Exception as e:
        print(f"❌ Error en robot diario: {e}")

if __name__ == "__main__":
    actualizar_diario()