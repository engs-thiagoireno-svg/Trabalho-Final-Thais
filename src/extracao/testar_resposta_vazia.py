import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from utils import ler_config, conectar, abrir_log, fechar_log
from ccee_pld import extrair_resource, definir_status


class RespostaVazia(BaseHTTPRequestHandler):
    def do_GET(self):
        corpo = json.dumps(
            {"success": True, "result": {"total": 0, "records": []}}
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, *args):
        pass


servidor = HTTPServer(("127.0.0.1", 8765), RespostaVazia)
threading.Thread(target=servidor.serve_forever, daemon=True).start()

cfg = ler_config()
cfg["ccee"]["url"] = "http://127.0.0.1:8765"
conn = conectar(cfg)
id_log = abrir_log(conn, "teste_resposta_vazia", "ccee_simulada")

resultado = extrair_resource(conn, cfg, "resource-de-teste")
status = definir_status([resultado], [])
fechar_log(conn, id_log, resultado["lidas"], resultado["gravadas"],
           status, " | ".join(resultado["avisos"]))

conn.close()
servidor.shutdown()
print("Status:", status)
print("Avisos:", resultado["avisos"])