import requests
from bs4 import BeautifulSoup
import json
import re
import os
import sys
from datetime import datetime
from io import BytesIO
from pypdf import PdfReader
import urllib3

# Desactivar alertas SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ARCHIVO_JSON = 'datos_poceada.json'
CARPETA_BACKUP = 'backups'
ID_SEGURIDAD = 870 

def obtener_ultimo_id_web_procesado():
    if os.path.exists("ultimo_id_web.txt"):
        with open("ultimo_id_web.txt", "r") as f:
            return int(f.read().strip())
    return ID_SEGURIDAD

def guardar_ultimo_id_web(id_web):
    with open("ultimo_id_web.txt", "w") as f:
        f.write(str(id_web))

def limpiar_texto(texto):
    if not texto: return ""
    return texto.replace("\n", "").strip()

# --- FUNCIÓN CORREGIDA ---
def detectar_ganadores_en_fila(textos_fila):
    # 1. Unimos todo el texto de la fila para buscar palabras clave
    texto_completo = " ".join(textos_fila).upper()
    
    # CASO A: VACANTE
    if "VACANTE" in texto_completo:
        return 0, True # (cantidad, es_vacante)

    # CASO B: BUSCAR EL NÚMERO "SUELTO"
    candidatos = [] # Lista en español
    for t in textos_fila:
        t_limpio = t.replace("$", "").strip()
        if "," in t_limpio: # Si tiene coma es plata, ignorar
            continue
        
        # Buscamos números enteros
        solo_numeros = re.findall(r'\d+', t_limpio.replace(".", ""))
        if solo_numeros:
            valor = int(solo_numeros[0])
            candidatos.append(valor)

    if candidatos:
        # --- AQUÍ ESTABA EL ERROR, AHORA DICE 'candidatos' ---
        return candidatos[0], False 
    
    return 0, False

def procesar_sorteo(id_url):
    url = f"https://loteria.chaco.gov.ar/detalle_poceada/{id_url}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        print(f"🔍 Escaneando ID {id_url}...", end=" ")
        response = requests.get(url, headers=headers, timeout=15, verify=False)
        
        if response.status_code != 200:
            print("❌ (Web Off)")
            return None

        soup = BeautifulSoup(response.content, 'html.parser')
        todo_el_texto = soup.get_text(" ", strip=True)

        # 1. FECHA REAL
        fecha_sorteo = "Fecha Pendiente"
        match_fecha = re.search(r'FECHA:?\s*(\d{2}/\d{2}/\d{4})', todo_el_texto, re.IGNORECASE)
        if match_fecha:
            d, m, y = match_fecha.group(1).split('/')
            fecha_sorteo = f"{y}-{m}-{d} 21:00:00"
        else:
             match_f2 = re.search(r'(\d{2}/\d{2}/\d{4})', todo_el_texto)
             if match_f2:
                d, m, y = match_f2.group(1).split('/')
                fecha_sorteo = f"{y}-{m}-{d} 21:00:00"

        # 2. NÚMERO SORTEO
        numero_real_sorteo = 0
        match_sorteo = re.search(r'N° Sorteo:?\s*(\d+)', todo_el_texto, re.IGNORECASE)
        if match_sorteo: numero_real_sorteo = int(match_sorteo.group(1))
        
        if numero_real_sorteo == 0: return None

        # 3. NÚMEROS GANADORES
        numeros = []
        items = soup.find_all("li", class_="results-list__item")
        for item in items:
            cols = item.find_all("p", class_="results-number")
            if len(cols) >= 2:
                posible_numero = cols[1].text.strip()
                if posible_numero.isdigit(): numeros.append(int(posible_numero))
        numeros = sorted(list(set(numeros[:10])))
        if len(numeros) < 10: return None

        # --- 4. PREMIOS (Con función corregida) ---
        dp = { "pozo5": "$0", "gan5": 0, "vacante5": False, "pozo4": "$0", "gan4": 0, "pozo3": "$0", "gan3": 0, "pozo2": "$0", "gan2": 0 }
        
        header_premios = soup.find("h4", string=re.compile("Pozos Quiniela Poceada"))
        if header_premios:
            card = header_premios.find_parent("div", class_="card")
            filas = card.find_all("li", class_="results-list__item")
            
            # Función auxiliar interna para extraer datos de una fila
            def analizar_fila(indice_fila):
                if len(filas) > indice_fila:
                    p_tags = filas[indice_fila].find_all("p")
                    textos = [p.text.strip() for p in p_tags]
                    
                    # Dinero (Pozo o Premio) es el que tiene signo $ o coma
                    dinero = "$0"
                    for t in textos:
                        if "," in t or "$" in t: dinero = t
                    
                    # Cantidad de ganadores
                    cant, es_vacante = detectar_ganadores_en_fila(textos)
                    return cant, es_vacante, textos
                return 0, False, []

            # Fila 5 Aciertos
            cant, vac, txts = analizar_fila(1)
            dp["gan5"] = cant
            dp["vacante5"] = vac
            if len(txts) > 1: dp["pozo5"] = txts[1]

            # Fila 4 Aciertos
            cant, _, txts = analizar_fila(2)
            dp["gan4"] = cant
            if len(txts) > 3: dp["pozo4"] = txts[3]

            # Fila 3 Aciertos
            cant, _, txts = analizar_fila(3)
            dp["gan3"] = cant
            if len(txts) > 3: dp["pozo3"] = txts[3]

            # Fila 2 Aciertos
            cant, _, txts = analizar_fila(4)
            dp["gan2"] = cant
            if len(txts) > 3: dp["pozo2"] = txts[3]

        # 5. POZO PRÓXIMO
        pozo_proximo = "Ver próximo sorteo"
        match_pozo_prox = re.search(r'POZO ESTIMADO.*?\$?\s*([\d\.,]+)', todo_el_texto, re.IGNORECASE)
        if match_pozo_prox: pozo_proximo = match_pozo_prox.group(1)

        print(f"✅ OK: Sorteo {numero_real_sorteo} (Ganadores 5: {dp['gan5']})")
        
        return {
            "numeroSorteo": numero_real_sorteo, "id_web": id_url, "fecha": fecha_sorteo, "numerosGanadores": numeros,
            "pozo5aciertos": dp["pozo5"], "vacante5aciertos": dp["vacante5"],
            "ganadores4aciertos": dp["gan4"], "premio4aciertos": dp["pozo4"],
            "ganadores3aciertos": dp["gan3"], "premio3aciertos": dp["pozo3"],
            "ganadores2aciertos": dp["gan2"], "premio2aciertos": dp["pozo2"],
            "pozoEstimadoProximo": pozo_proximo, "fechaProximo": "" 
        }

    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def actualizar_diario():
    historial = []
    if os.path.exists(ARCHIVO_JSON):
        with open(ARCHIVO_JSON, 'r', encoding='utf-8') as f:
            historial = json.load(f)

    ultimo_id_web = obtener_ultimo_id_web_procesado()
    
    # Revisar último ID
    dato_actualizado = procesar_sorteo(ultimo_id_web)
    if dato_actualizado:
        for i, s in enumerate(historial):
            if s['numeroSorteo'] == dato_actualizado['numeroSorteo']:
                historial[i] = dato_actualizado
                break
        else: historial.insert(0, dato_actualizado)

    # Buscar siguiente
    siguiente = ultimo_id_web + 1
    dato_nuevo = procesar_sorteo(siguiente)
    if dato_nuevo:
        historial.insert(0, dato_nuevo)
        guardar_ultimo_id_web(siguiente)

    with open(ARCHIVO_JSON, 'w', encoding='utf-8') as f:
        json.dump(historial, f, indent=4, ensure_ascii=False)
        
    if not os.path.exists(CARPETA_BACKUP): os.makedirs(CARPETA_BACKUP)
    bkp = f"{CARPETA_BACKUP}/backup_{datetime.now().strftime('%Y-%m-%d')}.json"
    with open(bkp, 'w', encoding='utf-8') as f:
        json.dump(historial, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    actualizar_diario()