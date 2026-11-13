begin;

truncate table
    dw_campo_real.fato_geracao,
    dw_campo_real.fato_preco,
    dw_campo_real.fato_clima,
    dw_campo_real.fato_parada
restart identity;

-- 1. dim_tempo (2025 e 2026)
with serie_horas as (
    select
        gs as data_hora,
        gs::date as data,
        extract(hour from gs)::smallint as hora,
        extract(day from gs)::smallint as dia,
        extract(month from gs)::smallint as mes,
        extract(quarter from gs)::smallint as trimestre,
        extract(year from gs)::smallint as ano,
        extract(isodow from gs)::smallint as dia_semana
    from generate_series(
        timestamp '2025-01-01 00:00:00',
        timestamp '2026-12-31 23:00:00',
        interval '1 hour'
    ) as gs
),
enriquecida as (
    select
        sh.data_hora,
        sh.data,
        sh.hora,
        sh.dia,
        sh.mes,
        case sh.mes
            when 1  then 'Janeiro'
            when 2  then 'Fevereiro'
            when 3  then 'Março'
            when 4  then 'Abril'
            when 5  then 'Maio'
            when 6  then 'Junho'
            when 7  then 'Julho'
            when 8  then 'Agosto'
            when 9  then 'Setembro'
            when 10 then 'Outubro'
            when 11 then 'Novembro'
            when 12 then 'Dezembro'
        end as nome_mes,
        to_char(sh.data, 'YYYY-MM') as ano_mes,
        sh.trimestre,
        sh.trimestre::text || 'º Tri' as nome_trimestre,
        sh.ano,
        sh.dia_semana,
        case sh.dia_semana
            when 1 then 'Segunda-feira'
            when 2 then 'Terça-feira'
            when 3 then 'Quarta-feira'
            when 4 then 'Quinta-feira'
            when 5 then 'Sexta-feira'
            when 6 then 'Sábado'
            when 7 then 'Domingo'
        end as nome_dia_semana,
        (sh.dia_semana in (6, 7)) as fim_de_semana,
        (fn.data is not null) as feriado,
        coalesce(fn.descricao, 'Não é feriado') as nome_feriado,
        coalesce(fn.tipo, 'Dia normal') as tipo_feriado,
        (sh.dia_semana not in (6, 7) and fn.data is null) as dia_util,
        case
            when (sh.mes = 12 and sh.dia >= 21) or sh.mes in (1, 2) or (sh.mes = 3 and sh.dia <= 20)
                then 'Verão'
            when (sh.mes = 3 and sh.dia >= 21) or sh.mes in (4, 5) or (sh.mes = 6 and sh.dia <= 20)
                then 'Outono'
            when (sh.mes = 6 and sh.dia >= 21) or sh.mes in (7, 8) or (sh.mes = 9 and sh.dia <= 22)
                then 'Inverno'
            else 'Primavera'
        end as estacao_ano
    from serie_horas sh
    left join campo_real_energia.feriado_nacional fn
        on fn.data = sh.data
)
insert into dw_campo_real.dim_tempo (
    data_hora, data, hora, dia, mes, nome_mes, ano_mes,
    trimestre, nome_trimestre, ano, dia_semana, nome_dia_semana,
    fim_de_semana, feriado, nome_feriado, tipo_feriado, dia_util,
    estacao_ano, patamar_carga
)
select
    e.data_hora,
    e.data,
    e.hora,
    e.dia,
    e.mes,
    e.nome_mes,
    e.ano_mes,
    e.trimestre,
    e.nome_trimestre,
    e.ano,
    e.dia_semana,
    e.nome_dia_semana,
    e.fim_de_semana,
    e.feriado,
    e.nome_feriado,
    e.tipo_feriado,
    e.dia_util,
    e.estacao_ano,
    case
        when e.dia_util then
            case
                when e.hora between 0 and 6 then 'Leve'
                when e.hora between 18 and 20 then 'Pesada'
                else 'Média'
            end
        else
            case
                when e.hora between 18 and 21 then 'Média'
                else 'Leve'
            end
    end as patamar_carga
from enriquecida e
order by e.data_hora
on conflict (data_hora) do update set
    feriado       = excluded.feriado,
    nome_feriado  = excluded.nome_feriado,
    tipo_feriado  = excluded.tipo_feriado,
    dia_util      = excluded.dia_util,
    estacao_ano   = excluded.estacao_ano,
    patamar_carga = excluded.patamar_carga;

-- 2. dim_submercado
insert into dw_campo_real.dim_submercado (cod_submercado, nome, regioes)
select
    rtrim(s.cod_submercado) as cod_submercado,
    s.nome,
    s.regioes
from campo_real_energia.submercado s
order by rtrim(s.cod_submercado)
on conflict (cod_submercado) do update set
    nome    = excluded.nome,
    regioes = excluded.regioes;

-- 3. dim_fonte
insert into dw_campo_real.dim_fonte (
    id_fonte_origem, cod_fonte, descricao, renovavel, intermitente
)
select
    f.id_fonte,
    rtrim(f.cod_fonte) as cod_fonte,
    f.descricao,
    f.renovavel,
    f.intermitente
from campo_real_energia.fonte_energia f
order by f.id_fonte
on conflict (cod_fonte) do update set
    id_fonte_origem = excluded.id_fonte_origem,
    descricao       = excluded.descricao,
    renovavel       = excluded.renovavel,
    intermitente    = excluded.intermitente;

-- 4. dim_usina (SCD Tipo 2 para potencia/situacao/fonte/submercado; Tipo 1 para os demais)
update dw_campo_real.dim_usina du
set
    id_usina_origem      = ul.id_usina,
    nome                 = ul.nome,
    uf                   = rtrim(ul.uf),
    municipio            = ul.municipio,
    latitude             = ul.latitude,
    longitude            = ul.longitude,
    data_inicio_operacao = ul.data_inicio_operacao,
    fonte                = coalesce(df.descricao, 'Desconhecido'),
    renovavel            = coalesce(df.renovavel, false),
    intermitente         = coalesce(df.intermitente, false),
    submercado           = coalesce(ds.nome, 'Desconhecido')
from qualidade.usina_limpa ul
left join dw_campo_real.dim_fonte df
    on df.id_fonte_origem = ul.id_fonte
left join dw_campo_real.dim_submercado ds
    on ds.cod_submercado = rtrim(ul.cod_submercado)
where du.cod_usina = ul.cod_usina
  and du.registro_atual = true
  and du.potencia_mw = ul.potencia_mw
  and du.situacao = ul.situacao
  and du.cod_fonte = coalesce(df.cod_fonte, 'DESC')
  and du.cod_submercado = coalesce(ds.cod_submercado, 'ND');

update dw_campo_real.dim_usina du
set
    vigencia_fim   = current_date - 1,
    registro_atual = false
from qualidade.usina_limpa ul
left join dw_campo_real.dim_fonte df
    on df.id_fonte_origem = ul.id_fonte
left join dw_campo_real.dim_submercado ds
    on ds.cod_submercado = rtrim(ul.cod_submercado)
where du.cod_usina = ul.cod_usina
  and du.registro_atual = true
  and (
      du.potencia_mw <> ul.potencia_mw
      or du.situacao <> ul.situacao
      or du.cod_fonte <> coalesce(df.cod_fonte, 'DESC')
      or du.cod_submercado <> coalesce(ds.cod_submercado, 'ND')
  );

insert into dw_campo_real.dim_usina (
    id_usina_origem, cod_usina, nome,
    sk_fonte, cod_fonte, fonte, renovavel, intermitente,
    sk_submercado, cod_submercado, submercado,
    uf, municipio, latitude, longitude, potencia_mw,
    data_inicio_operacao, situacao, vigencia_inicio, vigencia_fim, registro_atual
)
select
    ul.id_usina as id_usina_origem,
    ul.cod_usina,
    ul.nome,
    coalesce(df.sk_fonte, -1) as sk_fonte,
    coalesce(df.cod_fonte, 'DESC') as cod_fonte,
    coalesce(df.descricao, 'Desconhecido') as fonte,
    coalesce(df.renovavel, false) as renovavel,
    coalesce(df.intermitente, false) as intermitente,
    coalesce(ds.sk_submercado, -1) as sk_submercado,
    coalesce(ds.cod_submercado, 'ND') as cod_submercado,
    coalesce(ds.nome, 'Desconhecido') as submercado,
    rtrim(ul.uf) as uf,
    ul.municipio,
    ul.latitude,
    ul.longitude,
    ul.potencia_mw,
    ul.data_inicio_operacao,
    ul.situacao,
    case
        when exists (
            select 1 from dw_campo_real.dim_usina d_ant
            where d_ant.cod_usina = ul.cod_usina and d_ant.registro_atual = false
        ) then current_date
        when coalesce(ul.flag_inicio_operacao_invalido, false)
             or ul.data_inicio_operacao > date '2025-01-01'
            then date '2025-01-01'
        else ul.data_inicio_operacao
    end as vigencia_inicio,
    null as vigencia_fim,
    true as registro_atual
from qualidade.usina_limpa ul
left join dw_campo_real.dim_fonte df
    on df.id_fonte_origem = ul.id_fonte
left join dw_campo_real.dim_submercado ds
    on ds.cod_submercado = rtrim(ul.cod_submercado)
where not exists (
    select 1
    from dw_campo_real.dim_usina du
    where du.cod_usina = ul.cod_usina
      and du.registro_atual = true
)
order by ul.id_usina;

-- 5. dim_tipo_parada
insert into dw_campo_real.dim_tipo_parada (tipo, motivo)
select distinct
    p.tipo,
    p.motivo
from qualidade.parada_usina_limpa p
order by p.tipo, p.motivo
on conflict (tipo, motivo) do nothing;

-- 6. fato_preco
insert into dw_campo_real.fato_preco (
    sk_tempo, sk_submercado, pld_rs_mwh
)
select
    coalesce(dt.sk_tempo, -1) as sk_tempo,
    coalesce(ds.sk_submercado, -1) as sk_submercado,
    p.pld_rs_mwh
from qualidade.pld_horario_limpo p
left join dw_campo_real.dim_tempo dt
    on dt.data_hora = p.data_hora
left join dw_campo_real.dim_submercado ds
    on ds.cod_submercado = rtrim(p.cod_submercado)
on conflict (sk_tempo, sk_submercado) do update set
    pld_rs_mwh = excluded.pld_rs_mwh;

-- 7. fato_geracao
insert into dw_campo_real.fato_geracao (
    sk_tempo, sk_usina, sk_fonte, sk_submercado,
    energia_mwh, disponibilidade_mw, pld_rs_mwh, receita_rs,
    flag_outlier, flag_atraso
)
select
    coalesce(dt.sk_tempo, -1) as sk_tempo,
    coalesce(du.sk_usina, -1) as sk_usina,
    coalesce(du.sk_fonte, -1) as sk_fonte,
    coalesce(du.sk_submercado, -1) as sk_submercado,
    m.energia_mwh,
    m.disponibilidade_mw,
    fp.pld_rs_mwh,
    case
        when fp.pld_rs_mwh is not null
            then round(m.energia_mwh * fp.pld_rs_mwh, 2)
        else null
    end as receita_rs,
    coalesce(m.flag_outlier, false) as flag_outlier,
    coalesce(m.flag_atraso, false) as flag_atraso
from qualidade.medicao_geracao_limpa m
left join dw_campo_real.dim_tempo dt
    on dt.data_hora = m.data_hora
left join dw_campo_real.dim_usina du
    on du.id_usina_origem = m.id_usina
   and m.data_hora::date >= du.vigencia_inicio
   and (du.vigencia_fim is null or m.data_hora::date <= du.vigencia_fim)
left join dw_campo_real.fato_preco fp
    on fp.sk_tempo = coalesce(dt.sk_tempo, -1)
   and fp.sk_submercado = coalesce(du.sk_submercado, -1);

-- 8. fato_clima
insert into dw_campo_real.fato_clima (
    sk_tempo, sk_usina, sk_fonte, sk_submercado,
    temperatura_c, radiacao_wm2, vento_10m_ms, vento_100m_ms, vento_ms, chuva_mm
)
select
    coalesce(dt.sk_tempo, -1) as sk_tempo,
    coalesce(du.sk_usina, -1) as sk_usina,
    coalesce(du.sk_fonte, -1) as sk_fonte,
    coalesce(du.sk_submercado, -1) as sk_submercado,
    c.temperatura_c,
    c.radiacao_wm2,
    c.vento_10m_ms,
    c.vento_100m_ms,
    c.vento_100m_ms as vento_ms,
    c.chuva_mm
from qualidade.clima_horario_limpo c
left join dw_campo_real.dim_tempo dt
    on dt.data_hora = c.data_hora
left join dw_campo_real.dim_usina du
    on du.cod_usina = c.cod_usina
   and c.data_hora::date >= du.vigencia_inicio
   and (du.vigencia_fim is null or c.data_hora::date <= du.vigencia_fim);

-- 9. fato_parada
with horas_paradas as (
    select
        p.id_parada,
        p.id_usina,
        gs as data_hora,
        extract(hour from gs)::int as hora
    from qualidade.parada_usina_limpa p
    cross join lateral generate_series(p.inicio, p.fim, interval '1 hour') as gs
),
perfil_horario_usina as (
    select
        m.id_usina,
        extract(hour from m.data_hora)::int as hora,
        avg(m.energia_mwh) as media_energia_mwh
    from qualidade.medicao_geracao_limpa m
    where not exists (
        select 1
        from horas_paradas hp
        where hp.id_usina = m.id_usina
          and hp.data_hora = m.data_hora
    )
    group by m.id_usina, extract(hour from m.data_hora)::int
),
perdas_por_parada as (
    select
        hp.id_parada,
        count(hp.data_hora)::numeric(8,2) as horas_parada,
        round(sum(coalesce(phu.media_energia_mwh, 0))::numeric, 3) as energia_nao_gerada_mwh,
        case
            when count(fp.pld_rs_mwh) > 0
                then round(sum(coalesce(phu.media_energia_mwh, 0) * fp.pld_rs_mwh)::numeric, 2)
            else null
        end as receita_nao_gerada_rs
    from horas_paradas hp
    left join perfil_horario_usina phu
        on phu.id_usina = hp.id_usina and phu.hora = hp.hora
    left join dw_campo_real.dim_tempo dt
        on dt.data_hora = hp.data_hora
    left join dw_campo_real.dim_usina du
        on du.id_usina_origem = hp.id_usina and du.registro_atual = true
    left join dw_campo_real.fato_preco fp
        on fp.sk_tempo = dt.sk_tempo and fp.sk_submercado = du.sk_submercado
    group by hp.id_parada
)
insert into dw_campo_real.fato_parada (
    id_parada_origem, sk_tempo_inicio, sk_tempo_fim,
    sk_usina, sk_fonte, sk_submercado, sk_tipo_parada,
    horas_parada, energia_nao_gerada_mwh, receita_nao_gerada_rs
)
select
    p.id_parada as id_parada_origem,
    coalesce(dt_ini.sk_tempo, -1) as sk_tempo_inicio,
    coalesce(dt_fim.sk_tempo, -1) as sk_tempo_fim,
    coalesce(du.sk_usina, -1) as sk_usina,
    coalesce(du.sk_fonte, -1) as sk_fonte,
    coalesce(du.sk_submercado, -1) as sk_submercado,
    coalesce(dtp.sk_tipo_parada, -1) as sk_tipo_parada,
    pp.horas_parada,
    pp.energia_nao_gerada_mwh,
    pp.receita_nao_gerada_rs
from qualidade.parada_usina_limpa p
join perdas_por_parada pp
    on pp.id_parada = p.id_parada
left join dw_campo_real.dim_tempo dt_ini
    on dt_ini.data_hora = p.inicio
left join dw_campo_real.dim_tempo dt_fim
    on dt_fim.data_hora = p.fim
left join dw_campo_real.dim_usina du
    on du.id_usina_origem = p.id_usina
   and p.inicio::date >= du.vigencia_inicio
   and (du.vigencia_fim is null or p.inicio::date <= du.vigencia_fim)
left join dw_campo_real.dim_tipo_parada dtp
    on dtp.tipo = p.tipo and dtp.motivo = p.motivo
order by p.id_parada;

commit;

-- Validação 1: Contagem e soma de energia (limpa vs fato_geracao)
select
    l.qtd_limpa,
    f.qtd_dw,
    (f.qtd_dw - l.qtd_limpa) as diff_linhas,
    l.energia_limpa_mwh,
    f.energia_dw_mwh,
    (f.energia_dw_mwh - l.energia_limpa_mwh) as diff_energia_mwh
from (
    select count(*) as qtd_limpa, round(sum(energia_mwh), 3) as energia_limpa_mwh
    from qualidade.medicao_geracao_limpa
) l
cross join (
    select count(*) as qtd_dw, round(sum(energia_mwh), 3) as energia_dw_mwh
    from dw_campo_real.fato_geracao
) f;

-- Validação 2: Volumetria e registros no membro desconhecido (-1)
select 'dim_tempo' as tabela, count(*) as total_linhas, count(*) filter (where sk_tempo = -1) as membro_desconhecido from dw_campo_real.dim_tempo
union all
select 'dim_submercado', count(*), count(*) filter (where sk_submercado = -1) from dw_campo_real.dim_submercado
union all
select 'dim_fonte', count(*), count(*) filter (where sk_fonte = -1) from dw_campo_real.dim_fonte
union all
select 'dim_usina', count(*), count(*) filter (where sk_usina = -1) from dw_campo_real.dim_usina
union all
select 'dim_tipo_parada', count(*), count(*) filter (where sk_tipo_parada = -1) from dw_campo_real.dim_tipo_parada
union all
select 'fato_geracao', count(*), count(*) filter (where sk_tempo = -1 or sk_usina = -1) from dw_campo_real.fato_geracao
union all
select 'fato_preco', count(*), count(*) filter (where sk_tempo = -1 or sk_submercado = -1) from dw_campo_real.fato_preco
union all
select 'fato_clima', count(*), count(*) filter (where sk_tempo = -1 or sk_usina = -1) from dw_campo_real.fato_clima
union all
select 'fato_parada', count(*), count(*) filter (where sk_tempo_inicio = -1 or sk_usina = -1) from dw_campo_real.fato_parada;

-- Validação 3: Teste manual de receita (geração x PLD) em uma hora
with pld_teste as (
    select
        dt.sk_tempo,
        ds.sk_submercado,
        coalesce(fp.pld_rs_mwh, 58.60::numeric(10,2)) as pld_rs_mwh
    from dw_campo_real.dim_tempo dt
    cross join dw_campo_real.dim_submercado ds
    left join dw_campo_real.fato_preco fp
        on fp.sk_tempo = dt.sk_tempo and fp.sk_submercado = ds.sk_submercado
    where dt.data_hora = timestamp '2025-07-15 19:00:00'
      and ds.cod_submercado = 'S'
)
select
    dt.data_hora,
    du.cod_usina,
    ds.cod_submercado,
    fg.energia_mwh,
    pt.pld_rs_mwh,
    round(fg.energia_mwh * pt.pld_rs_mwh, 2) as receita_calculada_rs
from dw_campo_real.fato_geracao fg
join dw_campo_real.dim_tempo dt on dt.sk_tempo = fg.sk_tempo
join dw_campo_real.dim_usina du on du.sk_usina = fg.sk_usina
join dw_campo_real.dim_submercado ds on ds.sk_submercado = fg.sk_submercado
join pld_teste pt on pt.sk_tempo = fg.sk_tempo and pt.sk_submercado = fg.sk_submercado
where du.cod_usina = 'CRE-UHE-001';
