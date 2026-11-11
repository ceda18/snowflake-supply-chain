-- bronze: csv files -> internal stage -> raw tables, typed on load, no business logic
-- placeholders are filled by scripts/run_pipeline.py:
--   <% data_dir %>      absolute path to data/raw
--   <% each:pattern %>  run the statement once per matching file
--                       (the emulator loads max 50k rows per file)

use warehouse compute_wh;
use schema supply_chain.bronze;

create or replace file format csv_format
    type = csv
    skip_header = 1
    field_optionally_enclosed_by = '"'
    null_if = ('')
    empty_field_as_null = true;

create or replace stage raw_stage
    file_format = csv_format;

put 'file://<% data_dir %>/<% each:chokepoints_daily_*.csv %>' @raw_stage auto_compress = false overwrite = true;
put 'file://<% data_dir %>/<% each:chokepoints_meta_*.csv %>' @raw_stage auto_compress = false overwrite = true;

-- column order must match the csv header
create or replace table chokepoints_daily_raw (
    transit_date date, -- "date" in the source
    year integer,
    month integer,
    day integer,
    portid varchar,
    portname varchar,
    n_container integer,
    n_dry_bulk integer,
    n_general_cargo integer,
    n_roro integer,
    n_tanker integer,
    n_cargo integer,
    n_total integer,
    capacity_container number(18, 2),
    capacity_dry_bulk number(18, 2),
    capacity_general_cargo number(18, 2),
    capacity_roro number(18, 2),
    capacity_tanker number(18, 2),
    capacity_cargo number(18, 2),
    capacity number(18, 2),
    objectid integer
);

copy into chokepoints_daily_raw
from @raw_stage/<% each:chokepoints_daily_*.csv %>
file_format = (format_name = csv_format);

create or replace table chokepoints_meta_raw (
    portid varchar,
    portname varchar,
    country varchar,
    iso3 varchar,
    continent varchar,
    fullname varchar,
    lat float,
    lon float,
    vessel_count_total integer,
    vessel_count_container integer,
    vessel_count_dry_bulk integer,
    vessel_count_general_cargo integer,
    vessel_count_roro integer,
    vessel_count_tanker integer,
    industry_top1 varchar,
    industry_top2 varchar,
    industry_top3 varchar,
    share_country_maritime_import varchar,
    share_country_maritime_export varchar,
    locode varchar,
    pageid varchar,
    countrynoaccents varchar,
    objectid integer
);

copy into chokepoints_meta_raw
from @raw_stage/<% each:chokepoints_meta_*.csv %>
file_format = (format_name = csv_format);
