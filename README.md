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

## Qualidade de dados (Etapa 2)

Avalia as tabelas de origem (`campo_real_energia`) e as externas (`extracao.pld_horario`,
`extracao.clima_horario`), grava as métricas no banco, gera dados limpos e quarentena no schema
`qualidade` e mede o impacto da limpeza (antes × depois). A origem nunca é alterada.

### Como rodar

1. O script cria o schema `qualidade` sozinho (roda `sql/02_qualidade_ddl.sql`, que só cria o que não existe e não mexe nos outros schemas). Se preferir, dá para rodar esse arquivo no DBeaver com Alt+X.
2. Confira se o seu `config/config.ini` tem a seção `[qualidade]` (veja `config/config.example.ini`).
3. Instale as bibliotecas (`pip install -r requirements.txt`; a etapa 2 usa também o SQLAlchemy).
4. Na raiz do projeto, rode:
   ```
   python -m src.qualidade.executar
   ```
   Precisa ser com `-m`, a partir da raiz, porque os arquivos da qualidade importam uns aos outros.

Pode rodar quantas vezes quiser: métricas, profiling e antes × depois acumulam por `data_execucao`;
as tabelas limpas e de quarentena são recriadas a cada execução. Se `extracao.pld_horario` estiver
vazia (CCEE bloqueada), a qualidade do PLD aparece como 100% faltante e a receita não é calculada;
quando o PLD for carregado, basta rodar de novo.

Ao final, o script gera `docs/resultado_qualidade.md`, com cada regra que falhou, a decisão tomada e o antes × depois.

### O que fica no schema `qualidade`

| Tabela | Conteúdo |
|---|---|
| `metricas_qualidade` | 1 linha por regra × tabela × execução (na origem e na limpa) |
| `decisoes` | decisão (corrigir, descartar, quarentena, sinalizar) e justificativa de cada regra |
| `profiling` | perfil de cada coluna de cada tabela |
| `antes_depois` | geração, fator de capacidade e receita, antes e depois da limpeza |
| `usina_limpa` / `usina_quarentena` | cadastro corrigido / cadastro duplicado |
| `parada_usina_limpa` / `parada_usina_quarentena` | paradas válidas / inválidas |
| `medicao_geracao_limpa` / `medicao_geracao_quarentena` | medição limpa, com flags / registros separados, com o motivo |
| `pld_horario_limpo` / `clima_horario_limpo` | PLD e clima prontos para o DW |

**O DW carrega das tabelas `*_limpa` e `*_limpo`**, não da origem nem do schema `extracao`.

### Código

| Arquivo | Função |
|---|---|
| `src/qualidade/conexao.py` | lê o `config.ini` e conecta |
| `src/qualidade/profiling.py` | perfil de qualquer tabela |
| `src/qualidade/regras.py` | regras reutilizáveis, cobrindo as 7 dimensões |
| `src/qualidade/decisoes.py` | decisão e justificativa de cada regra; correções de cadastro documentadas |
| `src/qualidade/limpeza.py` | correção, deduplicação, quarentena e flags |
| `src/qualidade/antes_depois.py` | indicadores antes × depois |
| `src/qualidade/executar.py` | roda tudo e gera o resumo |
