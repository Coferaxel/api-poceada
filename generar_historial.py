import requests
from bs4 import BeautifulSoup
import json
import re
import time
from io import BytesIO
from pypdf import PdfReader
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- RANGO CORREGIDO (IDs de URL) ---
# Buscamos alrededor del 868 para asegurar que agarre el último
RANGO_INICIO = 860 
RANGO_FIN = 875 

lista_sorteos = []
print(f"--- REPARANDO ULTIMOS POZOS (IDs Web {RANGO_INICIO}-{RANGO_FIN}) ---")

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

# Cargamos el historial existente para no perder lo viejo
try:
    with open('datos_poceada.json', 'r', encoding='utf-8') as f:
        historial_existente = json.load(f)
except:
    historial_existente = []

for id_url in range(RANGO_INICIO, RANGO_FIN):
    url = f"https://loteria.chaco.gov.ar/detalle_poceada/{id_url}"
    
    try:
        print(f"ID Web {id_url}...", end=" ")
        response = requests.get(url, headers=headers, timeout=10, verify=False)
        
        if response.status_code != 200:
            print(f"❌ (Vacío)")
            continue

        soup = BeautifulSoup(response.content, 'html.parser')

        # 1. NÚMERO REAL
        numero_real_sorteo = 0
        for t in soup.find_all('h5'):
            if "Sorteo" in t.text:
                nums = re.findall(r'\d+', t.text)
                if nums: numero_real_sorteo = int(nums[0])
        
        if numero_real_sorteo == 0: 
            print("(No es sorteo)")
            continue

        # 2. BOLILLAS
        numeros = []
        for item in soup.find_all("li", class_="results-list__item"):
            p = item.find_all("p", class_="results-number")
            if len(p) == 2:
                txt = p[1].text.strip()
                if txt.isdigit(): numeros.append(int(txt))
        numeros = sorted(list(set(numeros[:10])))
        if len(numeros) < 5: 
            print("⚠️")
            continue

        # 3. PDF (FECHA Y POZO)
        fecha_sorteo = "Fecha Pendiente"
        pozo_proximo = "0"
        
        link_pdf = soup.find('a', href=re.compile(r'POCEADA.*\.pdf', re.IGNORECASE))
        
        if link_pdf:
            try:
                raw_href = requests.utils.unquote(link_pdf.get('href'))
                
                # FECHA
                match_fecha = re.search(r'(\d{2})[-/](\d{2})[-/](\d{2,4})', raw_href)
                if match_fecha:
                    d, m, y = match_fecha.groups()
                    if len(y) == 2: y = "20" + y
                    fecha_sorteo = f"{y}-{m}-{d} 21:00:00"

                # DESCARGAR
                pdf_url = "https://loteria.chaco.gov.ar" + raw_href if raw_href.startswith('/') else raw_href
                resp_pdf = requests.get(pdf_url, headers=headers, verify=False)
                
                if resp_pdf.status_code == 200:
                    reader = PdfReader(BytesIO(resp_pdf.content))
                    texto_pdf = ""
                    for page in reader.pages: texto_pdf += page.extract_text() + " "
                    
                    # LIMPIEZA
                    texto_limpio = " ".join(texto_pdf.split())
                    
                    # FECHA EN PDF (Si falló el nombre)
                    if fecha_sorteo == "Fecha Pendiente":
                         match_f = re.search(r'(\d{2})[-/](\d{2})[-/](\d{2,4})', texto_limpio)
                         if match_f:
                            d, m, y = match_f.groups()
                            if len(y) == 2: y = "20" + y
                            fecha_sorteo = f"{y}-{m}-{d} 21:00:00"

                    # POZO
                    if "ESTIMADO" in texto_limpio.upper():
                        parte = texto_limpio.upper().split("ESTIMADO")[1]
                        # Busca: Digitos, puntos opcionales, coma, 2 digitos
                        match_dinero = re.search(r'(\d{1,3}(?:\.\d{3})*,\d{2})', parte)
                        if match_dinero:
                            pozo_proximo = match_dinero.group(1)

            except Exception as e: pass

        # 4. PREMIOS
        dp = { "pozo5": "0", "gan5": 0, "vacante5": False, "pozo4": "0", "gan4": 0, "pozo3": "0", "gan3": 0, "pozo2": "0", "gan2": 0 }
        header = soup.find("h4", string=re.compile("Pozos Quiniela Poceada"))
        if header:
            filas = header.find_parent("div", class_="card").find_all("li", class_="results-list__item")
            def cln(t): return t.replace("\n", "").strip()
            if len(filas) > 1:
                dp["pozo5"] = cln(filas[1].find_all("p")[1].text)
                g = cln(filas[1].find_all("p")[2].text)
                dp["vacante5"] = (g.upper() == "VACANTE" or g == "0")
                dp["gan5"] = 0 if dp["vacante5"] else int(g.replace(".",""))
            if len(filas) > 2:
                dp["gan4"] = int(cln(filas[2].find_all("p")[2].text).replace(".",""))
                dp["pozo4"] = cln(filas[2].find_all("p")[3].text)
            if len(filas) > 3:
                dp["gan3"] = int(cln(filas[3].find_all("p")[2].text).replace(".",""))
                dp["pozo3"] = cln(filas[3].find_all("p")[3].text)
            if len(filas) > 4:
                dp["gan2"] = int(cln(filas[4].find_all("p")[2].text).replace(".",""))
                dp["pozo2"] = cln(filas[4].find_all("p")[3].text)

        # 5. ACTUALIZAR O AGREGAR
        obj = {
            "numeroSorteo": numero_real_sorteo, "id_web": id_url, "fecha": fecha_sorteo,
            "numerosGanadores": numeros,
            "pozo5aciertos": dp["pozo5"], "vacante5aciertos": dp["vacante5"],
            "ganadores4aciertos": dp["gan4"], "premio4aciertos": dp["pozo4"],
            "ganadores3aciertos": dp["gan3"], "premio3aciertos": dp["pozo3"],
            "ganadores2aciertos": dp["gan2"], "premio2aciertos": dp["pozo2"],
            "pozoEstimadoProximo": pozo_proximo, "fechaProximo": "" 
        }
        
        # Reemplazar si existe, sino agregar
        encontrado = False
        for i, s in enumerate(historial_existente):
            if s['numeroSorteo'] == numero_real_sorteo:
                historial_existente[i] = obj
                encontrado = True
                break
        if not encontrado:
            historial_existente.insert(0, obj)

        print(f"✅ Sorteo {numero_real_sorteo} (ID {id_url}) - Pozo: ${pozo_proximo}")

    except Exception as e:
        print(f"❌ {e}")

# Ordenar historial por numeroSorteo descendente
historial_existente.sort(key=lambda x: x['numeroSorteo'], reverse=True)

with open('datos_poceada.json', 'w', encoding='utf-8') as f:
    json.dump(historial_existente, f, indent=4, ensure_ascii=False)

print(f"\n✨ FINALIZADO.")