-- gold: tables the app reads
-- on a real account these are dynamic tables (target_lag = '1 day'), ctas on the emulator.
-- the as-of date comes from the data, not current_date(): portwatch lags by a few days.

use warehouse compute_wh;
use schema supply_chain.gold;

-- weekly transits with yoy, complete weeks only so partial weeks don't look like drops
create or replace table chokepoint_weekly as
with weekly as (
    select
        d.week_start,
        f.chokepoint_id,
        f.chokepoint_name,
        sum(f.n_total) as transits_total,
        sum(f.n_container) as transits_container,
        sum(f.n_tanker) as transits_tanker,
        sum(f.n_dry_bulk) as transits_dry_bulk,
        sum(f.capacity_total) as capacity_total,
        count(*) as days_in_week
    from supply_chain.silver.fct_chokepoint_daily as f
    inner join supply_chain.silver.dim_date as d on f.transit_date = d.date_day
    group by 1, 2, 3
)

select
    week_start,
    chokepoint_id,
    chokepoint_name,
    transits_total,
    transits_container,
    transits_tanker,
    transits_dry_bulk,
    capacity_total,
    lag(transits_total, 52) over (partition by chokepoint_id order by week_start) as transits_total_ly,
    round(
        100 * (
            transits_total
            / nullif(lag(transits_total, 52) over (partition by chokepoint_id order by week_start), 0)
            - 1
        ),
        1
    ) as yoy_pct
from weekly
where days_in_week = 7;

-- last 30 days vs the same 30 days a year earlier, reads only rows inside the two windows.
-- -25% or worse = disrupted, +25% or more = surge
create or replace table disruption_monitor as
with windows as (
    select
        f.chokepoint_id,
        f.chokepoint_name,
        max(b.as_of_date) as as_of_date,
        avg(case when f.transit_date >= b.last_30d_start then f.n_total end) as avg_daily_last_30d,
        avg(case when f.transit_date <= b.ly_30d_end then f.n_total end) as avg_daily_same_30d_ly
    from supply_chain.silver.fct_chokepoint_daily as f
    cross join supply_chain.silver.data_bounds as b
    where
        f.transit_date >= b.last_30d_start
        or (f.transit_date >= b.ly_30d_start and f.transit_date <= b.ly_30d_end)
    group by 1, 2
)

select
    chokepoint_id,
    chokepoint_name,
    as_of_date,
    round(avg_daily_last_30d, 1) as avg_daily_last_30d,
    round(avg_daily_same_30d_ly, 1) as avg_daily_same_30d_ly,
    round(100 * (avg_daily_last_30d / nullif(avg_daily_same_30d_ly, 0) - 1), 1) as change_pct,
    case
        when avg_daily_last_30d / nullif(avg_daily_same_30d_ly, 0) <= 0.75 then 'DISRUPTED'
        when avg_daily_last_30d / nullif(avg_daily_same_30d_ly, 0) >= 1.25 then 'SURGE'
        else 'NORMAL'
    end as status
from windows;

-- monthly suez + bab el-mandeb vs cape of good hope, current (incomplete) month excluded.
-- the 3 chokepoints are picked from the 28-row dimension, the fact table is joined by id.
create or replace table red_sea_rerouting as
with routes as (
    select
        chokepoint_id,
        case
            when chokepoint_name ilike '%suez%' then 'SUEZ'
            when chokepoint_name ilike '%mandeb%' then 'MANDEB'
            when chokepoint_name ilike '%good hope%' then 'CAPE'
        end as route
    from supply_chain.silver.dim_chokepoint
    where
        chokepoint_name ilike '%suez%'
        or chokepoint_name ilike '%mandeb%'
        or chokepoint_name ilike '%good hope%'
)

select
    d.month_start as month,
    sum(case when r.route = 'SUEZ' then f.n_total end) as suez_canal,
    sum(case when r.route = 'MANDEB' then f.n_total end) as bab_el_mandeb,
    sum(case when r.route = 'CAPE' then f.n_total end) as cape_of_good_hope,
    sum(case when r.route = 'SUEZ' then f.n_container end) as suez_container,
    sum(case when r.route = 'CAPE' then f.n_container end) as cape_container
from supply_chain.silver.fct_chokepoint_daily as f
inner join routes as r on f.chokepoint_id = r.chokepoint_id
inner join supply_chain.silver.dim_date as d on f.transit_date = d.date_day
cross join supply_chain.silver.data_bounds as b
where d.month_start < b.current_month
group by 1;
