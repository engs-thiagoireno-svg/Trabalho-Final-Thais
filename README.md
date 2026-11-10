## Extração (Etapa 1)

A extração busca os dados de duas fontes e guarda no banco do grupo, no schema `extracao`.

| Fonte | O que traz | Script | Tabelas |
|---|---|---|---|
| Open-Meteo | Clima de 2025 de cada usina | `src/extracao/open_meteo.py` | `raw_clima`, `clima_horario` |
| CCEE | PLD por hora (2025 e 2026) | `src/extracao/ccee_pld.py` | `raw_pld`, `pld_horario` |

### Requisitos

- Python 3 e as bibliotecas do `requirements.txt` (`requests`, `pandas`, `psycopg2-binary`)
- Acesso ao banco PostgreSQL do grupo (Neon)

### Como rodar

1. Copie `config/config.example.ini` para `config/config.ini` e preencha a senha do banco. Esse arquivo não vai para o Git.
2. Instale as bibliotecas:
   ```
   pip install -r requirements.txt
   ```
3. Rode os scripts:
   ```
   python src\extracao\open_meteo.py
   python src\extracao\ccee_pld.py
   ```

O banco do grupo já tem a origem e o clima carregados. **Não rode o script da origem de novo**, porque ele apaga e recria o schema `campo_real_energia`.

### Como funciona

- **Duas versões de cada dado:** a `raw_*` guarda a resposta exatamente como chegou, e a outra tabela guarda o dado tratado, pronto para uso.
- **Pode rodar de novo sem duplicar:** o clima pula a usina que já foi gravada, e o PLD atualiza os valores que já existem.
- **Erros temporários:** se a fonte demorar ou falhar, o script tenta de novo, esperando um pouco mais a cada vez.
- **Registro:** cada execução fica na tabela `extracao.log_extracao`, com o status `ok`, `ok_com_avisos`, `parcial`, `vazio` ou `erro`.

### Problemas conhecidos

- **CCEE bloqueada:** a CCEE responde erro 403 para o Python, mas abre no navegador. Nesse caso o script registra `erro` no log e não grava dados pela metade. Os testes de falha estão em `docs/testes_de_falha.md`.
- **`CRE-EOL-07`:** é uma cópia repetida de `CRE-EOL-007` e é ignorada.
- **`CRE-UFV-004`:** a latitude está positiva na origem. O sinal é corrigido só no pedido ao Open-Meteo, e a origem não é alterada.
- **Coordenadas do Open-Meteo:** a API ajusta a coordenada para a grade do modelo. O valor ajustado fica guardado na `raw_clima`.

## Fontes de dados

- **PLD horário:** CCEE, portal de dados abertos (dadosabertos.ccee.org.br). Licença CC-BY 4.0.
- **Clima:** Open-Meteo (open-meteo.com). Uso não comercial, com atribuição.