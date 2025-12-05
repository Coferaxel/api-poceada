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

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ARCHIVO_JSON = 'datos_poceada.json'
CARPETA_BACKUP = 'backups'
URL_LISTA = "https://loteria.chaco.gov.ar/juego/quiniela_poceada/4"
BASE_URL = "https://loteria.chaco.gov.ar"

def limpiar_texto(texto):
    if not texto: return ""
    return texto.replace("\n", "").strip()

def detectar_ganadores_en_fila(textos_fila):
    # Unimos todo para ver si es vacante
    texto_completo = " ".join(textos_fila).upper()
    if "VACANTE" in texto_completo: return 0, True
    
    candidatos = []
    
    # --- CORRECCIÓN CLAVE ---
    # Saltamos el primer elemento (índice 0) porque es el título ("Pozo 5 Aciertos")
    # Procesamos solo desde el índice 1 en adelante
    for t in textos_fila[1:]: 
        t_limpio = t.replace("$", "").strip()
        if "," in t_limpio: continue # Es dinero, ignorar
        
        # Buscamos números enteros puros
        solo_numeros = re.findall(r'\d+', t_limpio.replace(".", ""))
        
        # Filtro extra: Si el texto tiene palabras, probablemente no sea la cantidad
        # (A menos que sea solo el número). 
        # La cantidad suele venir sola "7" o "319".
        if solo_numeros and len(t_limpio) < 10: 
            candidatos.append(int(solo_numeros[0]))
            
    # Devolvemos el primer candidato válido encontrado
    return candidatos[0] if candidatos else 0, False

def obtener_links_de_la_lista():
    print(f"🔍 Leyendo Lista Oficial: {URL_LISTA}...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    links_a_procesar = []
    try:
        response = requests.get(URL_LISTA, headers=headers, timeout=15, verify=False)
        soup = BeautifulSoup(response.content, 'html.parser')
        enlaces = soup.find_all('a', href=re.compile(r'detalle_poceada/\d+'))
        for a in enlaces[:5]: # Los primeros 5
            href = a['href']
            if not href.startswith("http"): href = BASE_URL + href
            if href not in links_a_procesar: links_a_procesar.append(href)
        return links_a_procesar
    except Exception as e:
        print(f"❌ Error lista: {e}")
        return []

def procesar_url(url_detalle):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        id_web = url_detalle.split('/')[-1]
        print(f"   >> Procesando ID {id_web}...", end=" ")
        response = requests.get(url_detalle, headers=headers, timeout=15, verify=False)
        if response.status_code != 200: 
            print("Off")
            return None

        soup = BeautifulSoup(response.content, 'html.parser')
        todo_texto = soup.get_text(" ", strip=True)

        # 1. NÚMERO
        numero_real_sorteo = 0
        match_sorteo = re.search(r'N° Sorteo:?\s*(\d+)', todo_texto, re.IGNORECASE)
        if match_sorteo: numero_real_sorteo = int(match_sorteo.group(1))
        if numero_real_sorteo == 0: return None

        # 2. FECHA
        fecha_sorteo = datetime.now().strftime("%Y-%m-%d 21:00:00")
        match_fecha = re.search(r'FECHA:?\s*(\d{2}/\d{2}/\d{4})', todo_texto, re.IGNORECASE)
        if match_fecha:
            d, m, y = match_fecha.group(1).split('/')
            fecha_sorteo = f"{y}-{m}-{d} 21:00:00"
        else:
            match_f2 = re.search(r'(\d{2}/\d{2}/\d{4})', todo_texto)
            if match_f2:
                d, m, y = match_f2.group(1).split('/')
                fecha_sorteo = f"{y}-{m}-{d} 21:00:00"

        # 3. NÚMEROS
        numeros = []
        for item in soup.find_all("li", class_="results-list__item"):
            p = item.find_all("p", class_="results-number")
            if len(p) >= 2:
                t = p[1].text.strip()
                if t.isdigit(): numeros.append(int(t))
        numeros = sorted(list(set(numeros[:10])))
        if len(numeros) < 10: return None

        # 4. PDF (POZO)
        pozo_proximo = "Ver próximo sorteo"
        link_pdf = soup.find('a', href=re.compile(r'POCEADA.*\.pdf', re.IGNORECASE))
        if link_pdf:
            try:
                raw = requests.utils.unquote(link_pdf.get('href'))
                p_url = BASE_URL + raw if raw.startswith('/') else raw
                r_pdf = requests.get(p_url, headers=headers, verify=False)
                if r_pdf.status_code == 200:
                    reader = PdfReader(BytesIO(r_pdf.content))
                    txt_pdf = ""
                    for p in reader.pages: txt_pdf += p.extract_text() + " "
                    txt_pdf = " ".join(txt_pdf.split())
                    if "ESTIMADO" in txt_pdf.upper():
                        parte = txt_pdf.upper().split("ESTIMADO")[1]
                        m = re.search(r'(\d{1,3}(?:\.\d{3})*,\d{2})', parte)
                        if m: pozo_proximo = m.group(1)
            except: pass

        # 5. PREMIOS
        dp = { "pozo5": "$0", "gan5": 0, "vacante5": False, "pozo4": "$0", "gan4": 0, "pozo3": "$0", "gan3": 0, "pozo2": "$0", "gan2": 0 }
        header = soup.find("h4", string=re.compile("Pozos Quiniela Poceada"))
        if header:
            filas = header.find_parent("div", class_="card").find_all("li", class_="results-list__item")
            
            def analizar_fila(indice_fila):
                if len(filas) > indice_fila:
                    p_tags = filas[indice_fila].find_all("p")
                    textos = [p.text.strip() for p in p_tags]
                    cant, vac = detectar_ganadores_en_fila(textos)
                    return cant, vac, textos
                return 0, False, []

            # Fila 5
            cant, vac, txts = analizar_fila(1)
            dp["gan5"] = cant
            dp["vacante5"] = vac
            for t in txts: 
                if "," in t and "VACANTE" not in t: dp["pozo5"] = t; break
            
            # Resto
            dp["gan4"], _, txts4 = analizar_fila(2)
            if len(txts4) > 0: dp["pozo4"] = txts4[-1]
            
            dp["gan3"], _, txts3 = analizar_fila(3)
            if len(txts3) > 0: dp["pozo3"] = txts3[-1]
            
            dp["gan2"], _, txts2 = analizar_fila(4)
            if len(txts2) > 0: dp["pozo2"] = txts2[-1]

        print(f"✅ OK Sorteo {numero_real_sorteo} (G5:{dp['gan5']} G4:{dp['gan4']})")
        
        return {
            "numeroSorteo": numero_real_sorteo, "id_web": 0, "fecha": fecha_sorteo,
            "numerosGanadores": numeros,
            "pozo5aciertos": dp["pozo5"], "vacante5aciertos": dp["vacante5"], "ganadores5aciertos": dp["gan5"],
            "ganadores4aciertos": dp["gan4"], "premio4aciertos": dp["pozo4"],
            "ganadores3aciertos": dp["gan3"], "premio3aciertos": dp["pozo3"],
            "ganadores2aciertos": dp["gan2"], "premio2aciertos": dp["pozo2"],
            "pozoEstimadoProximo": pozo_proximo, "fechaProximo": "" 
        }

    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def actualizar_diario():
    print("--- ROBOT FINAL CORREGIDO ---")
    historial = []
    if os.path.exists(ARCHIVO_JSON):
        try:
            with open(ARCHIVO_JSON, 'r', encoding='utf-8') as f:
                historial = json.load(f)
        except: pass
    
    links = obtener_links_de_la_lista()
    
    for link in links:
        dato = procesar_url(link)
        if dato:
            ya_esta = False
            for i, s in enumerate(historial):
                if s['numeroSorteo'] == dato['numeroSorteo']:
                    historial[i] = dato 
                    ya_esta = True
                    print("   (Actualizado)")
                    break
            if not ya_esta:
                historial.insert(0, dato)

    historial.sort(key=lambda x: x['numeroSorteo'], reverse=True)

    with open(ARCHIVO_JSON, 'w', encoding='utf-8') as f:
        json.dump(historial, f, indent=4, ensure_ascii=False)
        
    if not os.path.exists(CARPETA_BACKUP): os.makedirs(CARPETA_BACKUP)
    bkp = f"{CARPETA_BACKUP}/backup_{datetime.now().strftime('%Y-%m-%d')}.json"
    with open(bkp, 'w', encoding='utf-8') as f:
        json.dump(historial, f, indent=4, ensure_ascii=False)
    
    print("✨ Guardado.")

if __name__ == "__main__":
    actualizar_diario()