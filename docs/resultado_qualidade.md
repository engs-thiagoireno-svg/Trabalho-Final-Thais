# Resultado da qualidade de dados (gerado por executar.py)

Execução: 12/11/2026 12:27

## Regras com falha (origem)

| Dimensão | Regra | Tabela | Avaliados | Falhas | % | Decisão |
| --- | --- | --- | ---: | ---: | ---: | --- |
| acuracia | energia_mwh_travado | campo_real_energia.medicao_geracao | 78792 | 72 | 0.09 | quarentena |
| acuracia | fator_de_escala_kwh_ou_virgula | campo_real_energia.medicao_geracao | 78767 | 25 | 0.03 | corrigir |
| acuracia | outlier_iqr_energia_mwh | campo_real_energia.medicao_geracao | 62195 | 26 | 0.04 | sinalizar |
| atualidade | atraso_chegada | campo_real_energia.medicao_geracao | 78798 | 316 | 0.4 | sinalizar |
| atualidade | parou_de_enviar | campo_real_energia.medicao_geracao | 9 | 1 | 11.11 | sinalizar |
| completude | horas_faltantes_medicao | campo_real_energia.medicao_geracao | 78840 | 96 | 0.12 | sinalizar |
| completude | horas_faltantes_pld | extracao.pld_horario | 35040 | 35040 | 100.0 | sinalizar |
| completude | nulo_ou_vazio_cadastro_usina | campo_real_energia.usina | 10 | 1 | 10.0 | corrigir |
| completude | nulo_ou_vazio_energia_mwh | campo_real_energia.medicao_geracao | 78798 | 6 | 0.01 | quarentena |
| consistencia | energia_acima_potencia_x_1h | campo_real_energia.medicao_geracao | 78773 | 26 | 0.03 | quarentena |
| consistencia | fim_antes_de_inicio | campo_real_energia.parada_usina | 11 | 1 | 9.09 | quarentena (parada) |
| consistencia | geracao_antes_inicio_operacao | campo_real_energia.medicao_geracao | 78773 | 4000 | 5.08 | sinalizar |
| consistencia | geracao_durante_parada | campo_real_energia.medicao_geracao | 78798 | 4 | 0.01 | quarentena |
| consistencia | recebido_em_antes_de_data_hora | campo_real_energia.medicao_geracao | 78798 | 25 | 0.03 | sinalizar |
| consistencia | solar_gerando_a_noite | campo_real_energia.medicao_geracao | 8235 | 4 | 0.05 | quarentena |
| consistencia | uf_incompativel_com_submercado | campo_real_energia.usina | 10 | 1 | 10.0 | corrigir |
| integridade_referencial | fk_id_usina | campo_real_energia.medicao_geracao | 78798 | 25 | 0.03 | quarentena |
| unicidade | duplicado_id_usina_data_hora | campo_real_energia.medicao_geracao | 78798 | 56 | 0.07 | descartar / quarentena |
| unicidade | duplicado_usina_coordenadas | campo_real_energia.usina | 10 | 2 | 20.0 | descartar |
| unicidade | duplicado_usina_nome | campo_real_energia.usina | 10 | 2 | 20.0 | descartar |
| validade | data_fora_de_2025 | campo_real_energia.medicao_geracao | 78798 | 1 | 0.0 | quarentena |
| validade | energia_negativa | campo_real_energia.medicao_geracao | 78792 | 4 | 0.01 | corrigir para 0 |
| validade | inicio_operacao_no_futuro | campo_real_energia.usina | 10 | 1 | 10.0 | sinalizar |
| validade | latitude_fora_do_brasil | campo_real_energia.usina | 10 | 1 | 10.0 | corrigir |

## Para onde foi cada linha da medição

| Destino | Linhas |
| --- | ---: |
| origem | 78798 |
| limpa | 78657 |
| quarentena | 117 |
| descartadas (cópia exata) | 24 |

## Antes × depois (total e por usina)

| Indicador | Recorte | Antes | Depois | Diferença | % |
| --- | --- | ---: | ---: | ---: | ---: |
| fator_capacidade_pct | usina CRE-BIO-005 | 264.781 | 52.437 | -212.344 | -80.2 |
| fator_capacidade_pct | usina CRE-EOL-003 | 31.023 | 30.909 | -0.114 | -0.37 |
| fator_capacidade_pct | usina CRE-EOL-007 | 46.974 | 46.975 | 0.001 | 0.0 |
| fator_capacidade_pct | usina CRE-PCH-002 | 59.747 | 59.721 | -0.026 | -0.04 |
| fator_capacidade_pct | usina CRE-UFV-004 | 21.434 | 21.367 | -0.067 | -0.31 |
| fator_capacidade_pct | usina CRE-UFV-006 | 21.419 | 21.404 | -0.015 | -0.07 |
| fator_capacidade_pct | usina CRE-UHE-001 | 61.760 | 61.687 | -0.073 | -0.12 |
| fator_capacidade_pct | usina CRE-UHE-008 | 56.097 | 56.097 | 0.000 | 0.0 |
| fator_capacidade_pct | usina CRE-UTE-009 | 29.026 | 28.986 | -0.040 | -0.14 |
| geracao_mwh | total | 3,867,483.087 | 3,118,868.656 | -748,614.431 | -19.36 |
| geracao_mwh | usina CRE-BIO-005 | 927,792.191 | 183,739.736 | -744,052.455 | -80.2 |
| geracao_mwh | usina CRE-EOL-003 | 135,880.602 | 135,381.602 | -499.000 | -0.37 |
| geracao_mwh | usina CRE-EOL-007 | 493,793.057 | 493,796.457 | 3.400 | 0.0 |
| geracao_mwh | usina CRE-PCH-002 | 130,846.387 | 130,789.903 | -56.484 | -0.04 |
| geracao_mwh | usina CRE-UFV-004 | 112,655.129 | 112,304.770 | -350.359 | -0.31 |
| geracao_mwh | usina CRE-UFV-006 | 168,867.998 | 168,751.198 | -116.800 | -0.07 |
| geracao_mwh | usina CRE-UHE-001 | 973,833.148 | 972,675.073 | -1,158.075 | -0.12 |
| geracao_mwh | usina CRE-UHE-008 | 540,550.015 | 540,550.015 | 0.000 | 0.0 |
| geracao_mwh | usina CRE-UTE-009 | 381,407.902 | 380,879.902 | -528.000 | -0.14 |
| registros | total | 78,798.000 | 78,657.000 | -141.000 | -0.18 |
