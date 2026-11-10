# Testes de falha da extração

Aqui estão os testes que mostram o que o extrator faz quando a fonte dá problema.

## 1. Fonte bloqueada (CCEE)

- **Teste:** rodar `ccee_pld.py` com a CCEE bloqueada.
- **Resultado:** a CCEE respondeu erro 403 nos dois anos. O extrator registrou `erro` no log, com 0 linhas gravadas, e não salvou nada pela metade.
- **Prova:** print do log em `docs/evidencias/`.

## 2. Fonte que não responde (timeout)

- **Teste:** `testar_timeout.py` chama um endereço que não responde, com espera máxima de 2 segundos e 3 tentativas.
- **Resultado:** o `buscar()` tentou 3 vezes, esperando 1, 2 e 4 segundos entre elas, e depois parou com o erro `falhou apos 3 tentativas`. Levou 13 segundos.

## 3. Resposta vazia

- **Teste:** `testar_resposta_vazia.py` usa um servidor falso que responde "nenhum registro".
- **Resultado:** o extrator marcou o status `vazio`, avisou que o mês pode não estar publicado e não gravou nada. A execução ficou no log como `teste_resposta_vazia`.

## Ainda não testado

- **Erros 429 e 5xx:** o `buscar()` tenta de novo nesses casos, mas eles não apareceram nas execuções.
- **Colunas diferentes na resposta da CCEE:** a checagem existe no `ccee_pld.py`, mas só dá para ver com dados reais, quando o acesso abrir.