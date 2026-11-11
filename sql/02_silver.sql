-- silver: cleaned, conformed, deduplicated
-- on a real account these are dynamic tables (target_lag = 'downstream'). the emulator
-- recomputes dynamic tables on every read, so here they are materialized with ctas.

use warehouse compute_wh;
use schema supply_chain.silver;

-- country / iso3 / locode / trade shares only apply to ports, they are empty for chokepoints
create or replace table dim_chokepoint as
select
    portid as chokepoint_id,
    portname as chokepoint_name,
    lat,
    lon,
    vessel_count_total,
    vessel_count_container,
    vessel_count_tanker,
    vessel_count_dry_bulk,
    industry_top1,
    industry_top2,
    industry_top3
from supply_chain.bronze.chokepoints_meta_raw
where portid is not null;

-- one row per chokepoint per day, latest record wins if the source sends duplicates
create or replace table fct_chokepoint_daily as
select
    transit_date,
    portid as chokepoint_id,
    portname as chokepoint_name,
    n_container,
    n_dry_bulk,
    n_general_cargo,
    n_roro,
    n_tanker,
    n_cargo,
    n_total,
    capacity_container,
    capacity_tanker,
    capacity_cargo,
    capacity as capacity_total
from supply_chain.bronze.chokepoints_daily_raw
where
    transit_date is not null
    and portid is not null
qualify row_number() over (partition by portid, transit_date order by objectid desc) = 1;

-- date functions run once per day (~1.4k rows) instead of once per fact row
create or replace table dim_date as
select
    transit_date as date_day,
    date_trunc('week', transit_date) as week_start,
    date_trunc('month', transit_date) as month_start
from (select distinct transit_date from fct_chokepoint_daily) as days;

-- one row with the as-of date and the comparison windows (last 30 days vs same 30 days ly).
-- order by + limit instead of max(): the emulator evaluates date functions around an
-- aggregate row by row, which hung for minutes.
create or replace table data_bounds as
select
    as_of_date,
    dateadd(day, -29, as_of_date) as last_30d_start,
    dateadd(day, -394, as_of_date) as ly_30d_start,
    dateadd(day, -365, as_of_date) as ly_30d_end,
    date_trunc('month', as_of_date) as current_month
from (
    select date_day as as_of_date
    from dim_date
    order by date_day desc
    limit 1
) as latest;
