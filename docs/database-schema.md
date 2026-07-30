# مدل پایگاه داده

Migration اولیه جداول زیر را ایجاد می‌کند:

`data_sources`, `data_ingestion_runs`, `assets`, `asset_prices`, `funds`, `fund_nav_history`, `fund_market_history`, `fund_metrics`, `bank_products`, `economic_indicators`, `investor_profiles`, `recommendation_runs`, `recommendation_allocations`, `strategy_definitions`, `backtest_runs`, `backtest_metrics`.

رکوردهای مالی دارای `source_id`, `observed_at`, `valid_at`, `currency` و `quality_status` هستند. PostgreSQL محیط اصلی و SQLite جایگزین توسعه/تست است.

Migration `0003` جداول `market_indices`, `market_index_history`, `market_instruments`,
`instrument_market_history`, `fund_instrument_mappings`, `inflation_series`,
`inflation_observations`, `bank_product_versions`, `data_quality_events` و
`portfolio_rebalance_plans` را اضافه می‌کند. تاریخ و شناسه پایدار Unique Constraint دارند؛
مقادیر مالی Decimal و تاریخ مشاهده timezone-aware است.
