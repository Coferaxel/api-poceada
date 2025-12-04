import json
import requests
from bs4 import BeautifulSoup
import re
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# EL SORTEO QUE QUEREMOS ARREGLAR
ID_WEB_A_REPARAR = 872 # Corresponde al Sorteo 2240

def reparar():
    print("--- REPARANDO SORTEO 2240 ---")
    
    # 1. Cargar el archivo actual
    try:
        with open('datos_poceada.json', 'r', encoding='utf-8') as f:
            historial = json.load(f)
    except:
        print("❌ No encontré el archivo datos_poceada.json")
        return

    # 2. Borrar el sorteo defectuoso de la lista (si existe)
    historial_filtrado = [s for s in historial if s['numeroSorteo'] != 2240]
    print(f"Sorteos antes: {len(historial)} -> Ahora: {len(historial_filtrado)}")

    # 3. Descargar el dato correcto de la web
    url = f"https://loteria.chaco.gov.ar/detalle_poceada/{ID_WEB_A_REPARAR}"
    print(f"Descargando datos reales de {url}...")
    
    response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, verify=False)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Extracción de datos (Simplificada para este arreglo)
    dp = { "pozo5": "$0", "gan5": 0, "vacante5": False, "pozo4": "$0", "gan4": 0, "pozo3": "$0", "gan3": 0, "pozo2": "$0", "gan2": 0 }
    
    header = soup.find("h4", string=re.compile("Pozos Quiniela Poceada"))
    if header:
        filas = header.find_parent("div", class_="card").find_all("li", class_="results-list__item")
        def cln(t): return t.replace("\n", "").strip()
        
        # Fila 5 Aciertos
        if len(filas) > 1:
            dp["pozo5"] = cln(filas[1].find_all("p")[1].text)
            texto_gan = cln(filas[1].find_all("p")[2].text)
            
            if "VACANTE" in texto_gan.upper():
                dp["vacante5"] = True
                dp["gan5"] = 0
            else:
                dp["vacante5"] = False
                # Extraer el número "7"
                nums = re.findall(r'\d+', texto_gan.replace(".", ""))
                dp["gan5"] = int(nums[0]) if nums else 0

        # (El resto de premios los copiamos igual que antes)
        if len(filas) > 2:
             dp["gan4"] = int(cln(filas[2].find_all("p")[2].text).replace(".",""))
             dp["pozo4"] = cln(filas[2].find_all("p")[3].text)
        if len(filas) > 3:
             dp["gan3"] = int(cln(filas[3].find_all("p")[2].text).replace(".",""))
             dp["pozo3"] = cln(filas[3].find_all("p")[3].text)
        if len(filas) > 4:
             dp["gan2"] = int(cln(filas[4].find_all("p")[2].text).replace(".",""))
             dp["pozo2"] = cln(filas[4].find_all("p")[3].text)

    # Números (re-escaneo rápido)
    numeros = []
    for item in soup.find_all("li", class_="results-list__item"):
        p = item.find_all("p", class_="results-number")
        if len(p) >= 2 and p[1].text.strip().isdigit():
            numeros.append(int(p[1].text.strip()))
    numeros = sorted(list(set(numeros[:10])))

    # Objeto Nuevo Correcto
    # (Usamos los datos que ya teníamos para lo que no cambia, como la fecha o el pozo proximo si quieres, o lo dejamos limpio)
    nuevo_dato = {
        "numeroSorteo": 2240,
        "id_web": ID_WEB_A_REPARAR,
        "fecha": "2025-12-02 21:00:00", # Fecha hardcodeada correcta para este fix
        "numerosGanadores": numeros,
        "pozo5aciertos": dp["pozo5"],
        "vacante5aciertos": dp["vacante5"],
        "ganadores5aciertos": dp["gan5"], # ¡AQUÍ ESTÁ EL 7!
        "ganadores4aciertos": dp["gan4"], "premio4aciertos": dp["pozo4"],
        "ganadores3aciertos": dp["gan3"], "premio3aciertos": dp["pozo3"],
        "ganadores2aciertos": dp["gan2"], "premio2aciertos": dp["pozo2"],
        "pozoEstimadoProximo": "83.833.472,20", # Valor del PDF que ya tenías o lo pones manual
        "fechaProximo": ""
    }
    
    print(f"✅ CORREGIDO: Ganadores con 5 aciertos: {nuevo_dato['ganadores5aciertos']}")

    # 4. Insertar el corregido
    historial_filtrado.insert(0, nuevo_dato)

    # 5. Guardar
    with open('datos_poceada.json', 'w', encoding='utf-8') as f:
        json.dump(historial_filtrado, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    reparar()