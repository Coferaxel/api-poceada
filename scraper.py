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

# --- CORRECCIÓN CLAVE: ID ACTUALIZADO A DICIEMBRE 2025 ---
# El ID 872 corresponde al Sorteo 2240 (02/12/2025)
ID_BASE_WEB = 870 

def obtener_ultimo_id_web_procesado():
    # Intentamos leer la memoria del robot
    if os.path.exists("ultimo_id_web.txt"):
        try:
            with open("ultimo_id_web.txt", "r") as f:
                guardado = int(f.read().strip())
                # Si el guardado es muy viejo (menor a la base actual), usamos la base nueva
                if guardado < ID_BASE_WEB:
                    return ID_BASE_WEB
                return guardado
        except:
            pass
    return ID_BASE_WEB

def guardar_ultimo_id_web(id_web):
    with open("ultimo_id_web.txt", "w") as f:
        f.write(str(id_web))

def procesar_sorteo(id_url):
    url = f"https://loteria.chaco.gov.ar/detalle_poceada/{id_url}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        print(f"🔍 Buscando ID {id_url}...", end=" ")
        response = requests.get(url, headers=headers, timeout=15, verify=False)
        
        if response.status_code != 200:
            print("❌ No disponible.")
            return None

        soup = BeautifulSoup(response.content, 'html.parser')
        todo_texto = soup.get_text(" ", strip=True)

        # 1. NÚMERO REAL
        numero_real_sorteo = 0
        match_sorteo = re.search(r'N° Sorteo:?\s*(\d+)', todo_texto, re.IGNORECASE)
        if match_sorteo:
            numero_real_sorteo = int(match_sorteo.group(1))
        
        if numero_real_sorteo == 0:
            # Intento secundario en títulos h5
            for t in soup.find_all('h5'):
                if "Sorteo" in t.text:
                    nums = re.findall(r'\d+', t.text)
                    if nums: numero_real_sorteo = int(nums[0])
            if numero_real_sorteo == 0:
                numero_real_sorteo = id_url # Fallback

        # 2. NÚMEROS
        numeros = []
        for item in soup.find_all("li", class_="results-list__item"):
            p = item.find_all("p", class_="results-number")
            if len(p) >= 2:
                t = p[1].text.strip()
                if t.isdigit(): numeros.append(int(t))
        numeros = sorted(list(set(numeros[:10])))
        if len(numeros) < 5: 
            print("⚠️ (Sin bolillas)")
            return None

        # 3. PDF (FECHA Y POZO)
        fecha_sorteo = datetime.now().strftime("%Y-%m-%d 21:00:00")
        pozo_proximo = "Ver próximo sorteo"
        
        # Intentar sacar fecha del HTML primero (más seguro)
        match_fecha_html = re.search(r'FECHA:?\s*(\d{2}/\d{2}/\d{4})', todo_texto, re.IGNORECASE)
        if match_fecha_html:
            d, m, y = match_fecha_html.group(1).split('/')
            fecha_sorteo = f"{y}-{m}-{d} 21:00:00"
        
        # PDF para el pozo
        link_pdf = soup.find('a', href=re.compile(r'POCEADA.*\.pdf', re.IGNORECASE))
        if link_pdf:
            try:
                raw = requests.utils.unquote(link_pdf.get('href'))
                p_url = "https://loteria.chaco.gov.ar" + raw if raw.startswith('/') else raw
                resp = requests.get(p_url, headers=headers, verify=False)
                if resp.status_code == 200:
                    reader = PdfReader(BytesIO(resp.content))
                    txt_pdf = ""
                    for p in reader.pages: txt_pdf += p.extract_text() + " "
                    txt_pdf = " ".join(txt_pdf.split())

                    # Pozo
                    match_pozo = re.search(r'POZO.*?ESTIMADO.*?\$?\s*([\d\.,]+)', txt_pdf, re.IGNORECASE)
                    if match_pozo: pozo_proximo = match_pozo.group(1).strip()
            except: pass

        # 4. PREMIOS
        dp = { "pozo5": "0", "gan5": 0, "vacante5": False, "pozo4": "0", "gan4": 0, "pozo3": "0", "gan3": 0, "pozo2": "0", "gan2": 0 }
        # ... (Lógica de premios igual)
        h = soup.find("h4", string=re.compile("Pozos Quiniela Poceada"))
        if h:
            filas = h.find_parent("div", class_="card").find_all("li", class_="results-list__item")
            def cln(t): return t.replace("\n", "").strip()
            if len(filas) > 1:
                dp["pozo5"] = cln(filas[1].find_all("p")[1].text)
                g = cln(filas[1].find_all("p")[2].text)
                dp["vacante5"] = "VACANTE" in g.upper()
                dp["gan5"] = 0 if dp["vacante5"] else int(re.findall(r'\d+', g.replace(".",""))[0] if re.findall(r'\d+', g) else 0)
            if len(filas) > 2:
                dp["gan4"] = int(cln(filas[2].find_all("p")[2].text).replace(".",""))
                dp["pozo4"] = cln(filas[2].find_all("p")[3].text)
            if len(filas) > 3:
                dp["gan3"] = int(cln(filas[3].find_all("p")[2].text).replace(".",""))
                dp["pozo3"] = cln(filas[3].find_all("p")[3].text)
            if len(filas) > 4:
                dp["gan2"] = int(cln(filas[4].find_all("p")[2].text).replace(".",""))
                dp["pozo2"] = cln(filas[4].find_all("p")[3].text)

        print(f"✅ OK Sorteo {numero_real_sorteo} ({fecha_sorteo})")
        
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
    print("--- ROBOT CORRIGIENDO POSICIÓN ---")
    historial = []
    if os.path.exists(ARCHIVO_JSON):
        try:
            with open(ARCHIVO_JSON, 'r', encoding='utf-8') as f:
                historial = json.load(f)
        except: sys.exit(1) # Abortar si no se lee

    # Empezamos desde el ID actualizado
    id_actual = obtener_ultimo_id_web_procesado()
    
    # Buscamos hacia adelante (max 5 intentos)
    encontro_algo = False
    for i in range(1, 6):
        proximo = id_actual + i
        dato = procesar_sorteo(proximo)
        if dato:
            # Insertar arriba
            historial.insert(0, dato)
            # Actualizar puntero
            guardar_ultimo_id_web(proximo)
            print(f"🎉 ¡Nuevo sorteo {dato['numeroSorteo']} agregado!")
            encontro_algo = True
            # No rompemos el loop para que siga buscando si hay más atrasados

    if encontro_algo:
        with open(ARCHIVO_JSON, 'w', encoding='utf-8') as f:
            json.dump(historial, f, indent=4, ensure_ascii=False)
        
        # Backup
        if not os.path.exists(CARPETA_BACKUP): os.makedirs(CARPETA_BACKUP)
        bkp = f"{CARPETA_BACKUP}/backup_{datetime.now().strftime('%Y-%m-%d')}.json"
        with open(bkp, 'w', encoding='utf-8') as f:
            json.dump(historial, f, indent=4, ensure_ascii=False)
    else:
        print("💤 Todo al día (Último ID Web revisado: " + str(id_actual) + ")")

if __name__ == "__main__":
    actualizar_diario()