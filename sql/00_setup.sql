-- warehouse, database and one schema per medallion layer

create warehouse if not exists compute_wh warehouse_size = 'XSMALL' auto_suspend = 60 auto_resume = true;

create database if not exists supply_chain;

create schema if not exists supply_chain.bronze;
create schema if not exists supply_chain.silver;
create schema if not exists supply_chain.gold;
