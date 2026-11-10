from utils import ler_config, conectar, buscar

cfg = ler_config()
conn = conectar(cfg)
with conn.cursor() as cur:
    cur.execute("select cod_usina, latitude, longitude "
                "from campo_real_energia.usina where cod_usina = 'CRE-UHE-001'")
    cod, lat, lon = cur.fetchone()

om = cfg["open_meteo"]
params = {"latitude": float(lat), "longitude": float(lon),
          "start_date": "2025-01-01", "end_date": "2025-01-02",
          "hourly": om["variaveis"], "timezone": om["timezone"]}
r = buscar(om["url"], params, cfg)
dados = r.json()
print(r.status_code, cod, dados["latitude"], dados["longitude"])
print(list(dados["hourly"].keys()))
print(len(dados["hourly"]["time"]), dados["hourly"]["time"][0])