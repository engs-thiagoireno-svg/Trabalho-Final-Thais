import time
from utils import ler_config, buscar

cfg = ler_config()
cfg["requisicoes"]["timeout"] = "2"
cfg["requisicoes"]["tentativas"] = "3"
cfg["requisicoes"]["espera_inicial"] = "1"

inicio = time.time()
try:
    buscar("http://10.255.255.1", {}, cfg)
except RuntimeError as e:
    print("Erro esperado:", e)
print(f"Levou {time.time() - inicio:.1f} segundos")