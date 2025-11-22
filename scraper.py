import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

# URL de donde sacamos los datos (Página oficial o un portal de noticias confiable)
# Usamos un portal de noticias de Chaco porque suelen ser más fáciles de leer que la web oficial
URL = "https://www.noticiasdelparana.com.ar/resultados-de-la-quiniela" 
# (Nota: Esto es un ejemplo genérico, idealmente se busca la URL específica de la poceada)

def obtener_datos():
    # 1. Fingimos ser un navegador real para que no nos bloqueen
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(URL, headers=headers)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # --- AQUÍ COMIENZA LA MAGIA DE BUSCAR LOS NÚMEROS ---
        # Esta parte depende 100% de cómo esté hecha la página web hoy.
        # Este es un ejemplo de lógica de búsqueda:
        
        # Buscamos algo que diga "Poceada"
        # (Lógica simulada para el ejemplo, ya que no puedo navegar en tiempo real la web específica)
        
        datos_extraidos = {
            "numeroSorteo": 1234, # Esto debería extraerse
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "numerosGanadores": [],
            "pozoEstimado": "Estimado...",
            "ganadores5aciertos": 0,
            "monto4aciertos": "$0",
            "monto3aciertos": "$0",
            "monto2aciertos": "$0"
        }

        # SIMULACIÓN DE EXTRACCIÓN (Para que el script funcione y genere el JSON)
        # En un caso real, aquí haríamos: soup.find('div', class_='numeros-poceada')
        import random
        numeros = set()
        while len(numeros) < 10:
            numeros.add(random.randint(0, 99))
        
        datos_extraidos["numerosGanadores"] = sorted(list(numeros))
        datos_extraidos["pozoEstimado"] = "55.000.000" # Simulado
        
        # -----------------------------------------------------

        # 2. Leer el archivo actual (para mantener el historial)
        try:
            with open('datos_poceada.json', 'r') as f:
                historial = json.load(f)
        except FileNotFoundError:
            historial = []

        # 3. Agregamos el nuevo sorteo al principio
        # (Solo si es nuevo, aquí simplificamos agregando siempre para probar)
        historial.insert(0, datos_extraidos)

        # Guardamos máximo los últimos 50 sorteos para no hacer el archivo pesado
        historial = historial[:50]

        # 4. Guardar el archivo JSON actualizado
        with open('datos_poceada.json', 'w') as f:
            json.dump(historial, f, indent=4)
            
        print("✅ Datos actualizados correctamente")

    except Exception as e:
        print(f"❌ Error en el scraper: {e}")

if __name__ == "__main__":
    obtener_datos()