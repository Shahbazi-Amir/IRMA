# مدل پایگاه داده

Migration اولیه جداول زیر را ایجاد می‌کند:

`data_sources`, `data_ingestion_runs`, `assets`, `asset_prices`, `funds`, `fund_nav_history`, `fund_market_history`, `fund_metrics`, `bank_products`, `economic_indicators`, `investor_profiles`, `recommendation_runs`, `recommendation_allocations`, `strategy_definitions`, `backtest_runs`, `backtest_metrics`.

رکوردهای مالی دارای `source_id`, `observed_at`, `valid_at`, `currency` و `quality_status` هستند. PostgreSQL محیط اصلی و SQLite جایگزین توسعه/تست است.
