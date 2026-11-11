-- data quality checks, run_pipeline.py prints every result

use warehouse compute_wh;
use database supply_chain;

-- row counts per layer
select
    'bronze.chokepoints_daily_raw' as object_name,
    count(*) as row_count
from bronze.chokepoints_daily_raw
union all
select
    'bronze.chokepoints_meta_raw' as object_name,
    count(*) as row_count
from bronze.chokepoints_meta_raw
union all
select
    'silver.dim_chokepoint' as object_name,
    count(*) as row_count
from silver.dim_chokepoint
union all
select
    'silver.fct_chokepoint_daily' as object_name,
    count(*) as row_count
from silver.fct_chokepoint_daily
union all
select
    'silver.dim_date' as object_name,
    count(*) as row_count
from silver.dim_date
union all
select
    'gold.chokepoint_weekly' as object_name,
    count(*) as row_count
from gold.chokepoint_weekly
union all
select
    'gold.disruption_monitor' as object_name,
    count(*) as row_count
from gold.disruption_monitor
union all
select
    'gold.red_sea_rerouting' as object_name,
    count(*) as row_count
from gold.red_sea_rerouting;

-- date coverage and the windows gold uses
select count(*) as days_covered from silver.dim_date;
select * from silver.data_bounds;

-- must be 0
select count(*) as duplicate_keys
from (
    select
        chokepoint_id,
        transit_date
    from silver.fct_chokepoint_daily
    group by chokepoint_id, transit_date
    having count(*) > 1
) as dupes;

-- must return 3 rows, the chokepoints behind gold.red_sea_rerouting
select
    chokepoint_id,
    chokepoint_name
from silver.dim_chokepoint
where
    chokepoint_name ilike '%suez%'
    or chokepoint_name ilike '%mandeb%'
    or chokepoint_name ilike '%good hope%';

-- current status
select
    chokepoint_name,
    avg_daily_last_30d,
    avg_daily_same_30d_ly,
    change_pct,
    status
from gold.disruption_monitor
order by change_pct;
