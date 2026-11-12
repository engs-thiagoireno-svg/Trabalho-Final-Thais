"""Decisão justificada para cada regra (corrigir, descartar, quarentena ou sinalizar).

Este catálogo é gravado em qualidade.decisoes e vai para o relatório de qualidade.
Toda correção feita no código precisa estar explicada aqui.
"""

DECISOES = {
    # ---------------- completude
    "horas_faltantes_medicao": (
        "sinalizar", "Não há linha para limpar e preencher seria inventar geração. "
                     "A lacuna fica registrada e reduz o fator de capacidade da usina."),
    "nulo_ou_vazio_energia_mwh": (
        "quarentena", "Sem valor medido não há o que valorar; imputar média seria inventar dado."),
    "nulo_ou_vazio_cadastro_usina": (
        "corrigir", "O campo vazio pertence a um cadastro duplicado, que é descartado "
                    "(ver duplicado_usina_nome / duplicado_usina_coordenadas)."),
    "horas_faltantes_pld": ("sinalizar", "Hora sem PLD não tem preço; a receita dessa hora fica sem valor. "
                                         "Se a CCEE bloquear a extração (erro 403), a falha é de 100%."),
    "horas_faltantes_clima": ("sinalizar", "Lacuna da fonte externa; não afeta a geração."),
    # ---------------- unicidade
    "duplicado_id_usina_data_hora": (
        "descartar / quarentena", "Fica 1 linha por usina e hora: a leitura automática (SCADA) "
        "tem prioridade sobre o lançamento MANUAL e, na mesma origem, vale a primeira chegada. "
        "Cópia com os mesmos valores é descartada; cópia com valor diferente vai para a quarentena."),
    "duplicado_usina_nome": (
        "descartar", "Mesmo nome (ignorando caixa, acento e espaço) e mesmas coordenadas indicam a "
                     "mesma usina física. Fica o cadastro completo; o outro é mapeado para ele."),
    "duplicado_usina_coordenadas": ("descartar", "Ver duplicado_usina_nome."),
    # ---------------- validade
    "energia_negativa": (
        "corrigir para 0", "Valor negativo pequeno (até 2% da potência) é consumo dos serviços "
        "auxiliares, não geração. Negativo maior que isso vai para a quarentena."),
    "data_fora_de_2025": (
        "quarentena", "Fora do período medido. Corrigir o ano criaria duplicata com a leitura "
                      "automática que já existe para a mesma hora."),
    "latitude_fora_do_brasil": (
        "corrigir", "Sinal invertido: com o sinal trocado a coordenada cai no município cadastrado."),
    "longitude_fora_do_brasil": ("corrigir", "Mesmo critério da latitude."),
    "inicio_operacao_no_futuro": (
        "sinalizar", "A data real não é dedutível; a usina gera durante todo 2025, então a data "
                     "está errada, mas não afeta os indicadores. Não usar em vigência de SCD."),
    "pld_fora_piso_teto_horario": (
        "quarentena", "Preço fora do limite regulatório da ANEEL não pode ser PLD válido."),
    "dominio_cod_submercado": ("quarentena", "Submercado fora de SE, S, NE, N não tem PLD."),
    "dominio_tipo": ("sinalizar", "Tipo de parada fora de Programada/Forçada; padronizar se óbvio."),
    "dominio_origem": ("sinalizar", "Origem da medição fora de SCADA/MANUAL."),
    "duplicado_data_hora_cod_submercado": ("descartar", "Mesmo preço repetido para a mesma hora."),
    "duplicado_cod_usina_data_hora": ("descartar", "Mesmo ponto de clima repetido na mesma hora."),
    "horas_faltantes_pld_2026": ("sinalizar", "Lacuna no PLD de 2026 até o último mês publicado."),
    "clima_radiacao_fora_faixa": ("quarentena", "Radiação fora de 0 a 1.400 W/m² não é física."),
    "clima_vento_10m_fora_faixa": ("quarentena", "Vento a 10 m fora de 0 a 60 m/s não é plausível."),
    "clima_vento_100m_fora_faixa": ("quarentena", "Vento a 100 m fora de 0 a 80 m/s não é plausível."),
    "clima_temperatura_fora_faixa": ("quarentena", "Temperatura fora de -10 a 50 °C não é plausível no Brasil."),
    "clima_chuva_fora_faixa": ("quarentena", "Chuva negativa ou acima de 300 mm/h não é plausível."),
    "dominio_uf": ("corrigir", "Padronizar grafia quando o valor é óbvio; caso contrário, sinalizar."),
    # ---------------- consistência
    "energia_acima_potencia_x_1h": (
        "quarentena", "Fisicamente impossível. Se o valor for 10x/1000x a geração típica, "
                      "é corrigido antes (ver fator_de_escala); o que sobra vai para a quarentena."),
    "geracao_durante_parada": (
        "quarentena", "A usina estava em parada registrada; valorar essa geração inflaria a receita."),
    "solar_gerando_a_noite": ("quarentena", "Sem radiação solar não há geração fotovoltaica."),
    "fim_antes_de_inicio": (
        "quarentena (parada)", "Trocar as datas seria suposição; a parada não entra no cálculo de perdas."),
    "recebido_em_antes_de_data_hora": (
        "sinalizar", "Erro no carimbo de chegada; aparece junto com outros problemas da mesma linha."),
    "uf_incompativel_com_submercado": (
        "corrigir", "UF corrigida a partir das coordenadas e do município; o submercado confirma."),
    "geracao_antes_inicio_operacao": ("sinalizar", "Sintoma de data de início errada no cadastro."),
    "disponibilidade_acima_potencia": ("quarentena", "Disponibilidade não pode passar da potência instalada."),
    # ---------------- acurácia
    "fator_de_escala_kwh_ou_virgula": (
        "corrigir", "Valor 1000x (planilha em kWh) ou 10x (vírgula deslocada) a mediana do mês da "
                    "usina; dividido, volta para o perfil normal e cabe na potência. O original fica "
                    "em energia_mwh_original."),
    "energia_mwh_travado": (
        "quarentena", "Mesmo valor por 6 h ou mais em fonte que varia hora a hora é medidor travado: "
                      "o número não foi medido, mesmo parecendo plausível."),
    "outlier_iqr_energia_mwh": ("sinalizar", "Outlier não é erro por si só (pico de vento é real)."),
    # ---------------- integridade referencial
    "fk_id_usina": (
        "quarentena", "Sem usina válida não há submercado, logo não há PLD para valorar. "
                      "Evita também colisão de chave no membro desconhecido (-1) do DW."),
    "fk_id_fonte": ("quarentena", "Fonte inexistente no cadastro."),
    "fk_cod_submercado": ("quarentena", "Submercado inexistente no cadastro."),
    "fk_cod_usina_clima": ("quarentena", "Ponto de clima sem usina correspondente."),
    # ---------------- atualidade
    "atraso_chegada": (
        "sinalizar", "O valor pode estar correto; só chegou tarde. Fica na limpa com flag_atraso."),
    "parou_de_enviar": ("sinalizar", "Lacuna no fim do período, registrada no relatório."),
}

# Correções manuais de cadastro: só quando há evidência em outros atributos da própria linha.
CORRECOES_CADASTRO = [
    # (cod_usina, coluna, valor_novo, justificativa)
    ("CRE-BIO-005", "uf", "SP",
     "Município Sertãozinho nas coordenadas -21,14 / -47,99 fica em SP; submercado SE confirma."),
]
