import re
import requests

URL = "https://dadosabertos.ccee.org.br/api/3/action/package_show"
HEADERS = {"User-Agent": "Mozilla/5.0 (trabalho-academico-dw-campo-real)"}
r = requests.get(URL, params={"id": "pld_horario"}, headers=HEADERS, timeout=60)
print(r.status_code, r.headers.get("server"))
texto = re.sub(r"<style.*?</style>", "", r.text, flags=re.S)
texto = re.sub(r"<[^>]+>", " ", texto)
print(" ".join(texto.split())[:1200])