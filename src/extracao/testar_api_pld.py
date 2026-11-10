import configparser
import requests

cfg = configparser.ConfigParser()
cfg.read("config/config.ini", encoding="utf-8")

URL = cfg["ccee"]["url"]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Referer": "https://dadosabertos.ccee.org.br/dataset/pld_horario",
}
params = {"resource_id": cfg["ccee"]["resource_id_2025"], "limit": 3}
r = requests.get(URL, params=params, headers=HEADERS, timeout=60)
print(r.status_code, r.headers.get("content-type"))
if r.ok:
    print(r.json()["result"]["total"])