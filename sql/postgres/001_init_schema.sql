CREATE TABLE IF NOT EXISTS rule_versions (
    rule_version        varchar(16) PRIMARY KEY,
    rule_name           varchar(64) NOT NULL,
    rule_snapshot       jsonb NOT NULL,
    is_active           boolean NOT NULL DEFAULT false,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS stocks_master (
    ts_code             varchar(32) PRIMARY KEY,
    stock_name          varchar(64) NOT NULL,
    market              varchar(16) NOT NULL,
    sw_level1_industry  varchar(64) NOT NULL,
    list_status         varchar(16) NOT NULL,
    latest_report_period varchar(16),
    audit_opinion       varchar(64),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS scoring_runs (
    run_id                  varchar(64) PRIMARY KEY,
    rule_version            varchar(16) NOT NULL REFERENCES rule_versions(rule_version),
    data_version            varchar(64) NOT NULL,
    run_status              varchar(16) NOT NULL,
    total_stocks            integer,
    passed_filter_count     integer,
    key_watch_count         integer,
    watch_count             integer,
    started_at              timestamptz NOT NULL,
    finished_at             timestamptz,
    error_message           text,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_scoring_runs_status
        CHECK (run_status IN ('running', 'success', 'failed'))
);

CREATE TABLE IF NOT EXISTS stock_latest_scores (
    ts_code                                      varchar(32) PRIMARY KEY
                                                 REFERENCES stocks_master(ts_code),
    run_id                                       varchar(64) NOT NULL
                                                 REFERENCES scoring_runs(run_id),

    stock_name                                   varchar(64) NOT NULL,
    market                                       varchar(16) NOT NULL,
    sw_level1_industry                           varchar(64) NOT NULL,
    latest_report_period                         varchar(16),
    audit_opinion                                varchar(64),

    current_pool                                 varchar(16),
    total_score                                  numeric(5,2),
    industry_rank                                integer,
    industry_total                               integer,
    global_rank                                  integer,

    biz_quality_score                            numeric(5,2),
    growth_delivery_score                        numeric(5,2),
    financial_quality_score                      numeric(5,2),
    valuation_fit_score                          numeric(5,2),

    gross_margin_avg_3y                          numeric(8,4),
    roe_avg_3y                                   numeric(8,4),
    net_margin_avg_3y                            numeric(8,4),
    industry_position_score_raw                  numeric(5,2),
    revenue_pct_in_industry                      numeric(5,2),
    nonrec_np_pct_in_industry                    numeric(5,2),
    market_cap_pct_in_industry                   numeric(5,2),

    revenue_cagr_3y                              numeric(8,4),
    nonrec_np_cagr_3y                            numeric(8,4),
    shareholder_return_ratio_3y                  numeric(8,4),
    dividend_sum_3y                              numeric(18,2),
    buyback_sum_3y                               numeric(18,2),
    parent_np_sum_3y                             numeric(18,2),

    cash_conversion_ratio_3y                     numeric(8,4),
    asset_liability_ratio_latest                 numeric(8,4),
    capital_return_stability_score_raw           numeric(5,2),
    roe_std_3y                                   numeric(8,4),
    industry_roe_std_median_3y                   numeric(8,4),
    roe_stability_gap                            numeric(8,4),

    pe_ttm                                       numeric(10,4),
    pb_latest                                    numeric(10,4),
    dividend_yield_avg_3y                        numeric(8,4),

    gross_margin_score                           numeric(5,2),
    roe_score                                    numeric(5,2),
    net_margin_score                             numeric(5,2),
    industry_position_score                      numeric(5,2),
    revenue_cagr_score                           numeric(5,2),
    nonrec_np_cagr_score                         numeric(5,2),
    shareholder_return_score                     numeric(5,2),
    cash_conversion_score                        numeric(5,2),
    asset_liability_score                        numeric(5,2),
    capital_return_stability_score               numeric(5,2),
    pe_score                                     numeric(5,2),
    pb_score                                     numeric(5,2),
    dividend_yield_score                         numeric(5,2),

    manual_review_required                       boolean NOT NULL DEFAULT false,
    is_filtered                                  boolean NOT NULL DEFAULT false,
    filter_reasons                               jsonb NOT NULL DEFAULT '[]'::jsonb,
    cashflow_warning                             boolean NOT NULL DEFAULT false,
    short_debt_warning                           boolean NOT NULL DEFAULT false,
    pe_invalid                                   boolean NOT NULL DEFAULT false,
    pb_invalid                                   boolean NOT NULL DEFAULT false,
    data_missing                                 boolean NOT NULL DEFAULT false,
    warning_tags                                 jsonb NOT NULL DEFAULT '[]'::jsonb,

    gross_margin_weighted_score                  numeric(6,2),
    roe_weighted_score                           numeric(6,2),
    net_margin_weighted_score                    numeric(6,2),
    industry_position_weighted_score             numeric(6,2),
    revenue_cagr_weighted_score                  numeric(6,2),
    nonrec_np_cagr_weighted_score                numeric(6,2),
    shareholder_return_weighted_score            numeric(6,2),
    cash_conversion_weighted_score               numeric(6,2),
    asset_liability_weighted_score               numeric(6,2),
    capital_return_stability_weighted_score      numeric(6,2),
    pe_weighted_score                            numeric(6,2),
    pb_weighted_score                            numeric(6,2),
    dividend_yield_weighted_score                numeric(6,2),

    biz_quality_weighted_score                   numeric(6,2),
    growth_delivery_weighted_score               numeric(6,2),
    financial_quality_weighted_score             numeric(6,2),
    valuation_fit_weighted_score                 numeric(6,2),

    rule_version                                 varchar(16) NOT NULL
                                                 REFERENCES rule_versions(rule_version),
    data_version                                 varchar(64) NOT NULL,
    updated_at                                   timestamptz NOT NULL DEFAULT now(),
    scored_at                                    timestamptz NOT NULL,

    CONSTRAINT chk_stock_latest_scores_pool
        CHECK (
            current_pool IS NULL
            OR current_pool IN ('重点观察池', '观察池')
        ),
    CONSTRAINT chk_stock_latest_scores_total_score
        CHECK (
            total_score IS NULL
            OR (total_score >= 0 AND total_score <= 100)
        ),
    CONSTRAINT chk_stock_latest_scores_dimension_scores
        CHECK (
            (biz_quality_score IS NULL OR (biz_quality_score >= 0 AND biz_quality_score <= 100))
            AND (growth_delivery_score IS NULL OR (growth_delivery_score >= 0 AND growth_delivery_score <= 100))
            AND (financial_quality_score IS NULL OR (financial_quality_score >= 0 AND financial_quality_score <= 100))
            AND (valuation_fit_score IS NULL OR (valuation_fit_score >= 0 AND valuation_fit_score <= 100))
        )
);

CREATE TABLE IF NOT EXISTS stock_run_scores (
    LIKE stock_latest_scores INCLUDING DEFAULTS INCLUDING CONSTRAINTS
);

ALTER TABLE IF EXISTS stock_run_scores
    DROP CONSTRAINT IF EXISTS stock_run_scores_pkey;

ALTER TABLE IF EXISTS stock_run_scores
    DROP CONSTRAINT IF EXISTS stock_latest_scores_pkey;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'stock_run_scores'::regclass
          AND contype = 'p'
    ) THEN
        ALTER TABLE stock_run_scores
            ADD PRIMARY KEY (run_id, ts_code);
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_stock_run_scores_run_id
    ON stock_run_scores (run_id);

CREATE INDEX IF NOT EXISTS idx_stock_run_scores_run_pool
    ON stock_run_scores (run_id, current_pool);

CREATE INDEX IF NOT EXISTS idx_stock_run_scores_run_industry
    ON stock_run_scores (run_id, sw_level1_industry);

CREATE TABLE IF NOT EXISTS scoring_tasks (
    task_id                  varchar(64) PRIMARY KEY,
    run_id                   varchar(64)
                             REFERENCES scoring_runs(run_id),
    task_status              varchar(16) NOT NULL,
    apply_mode               varchar(16) NOT NULL,
    requested_scope          jsonb NOT NULL DEFAULT '{}'::jsonb,
    requested_rule_snapshot  jsonb,
    total_count              integer,
    done_count               integer NOT NULL DEFAULT 0,
    failed_count             integer NOT NULL DEFAULT 0,
    progress_stage           varchar(32),
    latest_message           text,
    log_path                 varchar(255),
    error_message            text,
    created_at               timestamptz NOT NULL DEFAULT now(),
    started_at               timestamptz,
    finished_at              timestamptz,
    updated_at               timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_scoring_tasks_status
        CHECK (task_status IN ('queued', 'running', 'success', 'failed')),
    CONSTRAINT chk_scoring_tasks_apply_mode
        CHECK (apply_mode IN ('run_once', 'save_as_default'))
);

CREATE INDEX IF NOT EXISTS idx_scoring_tasks_created_at
    ON scoring_tasks (created_at DESC);

CREATE TABLE IF NOT EXISTS run_rule_snapshots (
    run_id             varchar(64) PRIMARY KEY
                       REFERENCES scoring_runs(run_id),
    apply_mode         varchar(16) NOT NULL,
    rule_snapshot      jsonb NOT NULL,
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_run_rule_snapshots_apply_mode
        CHECK (apply_mode IN ('default', 'run_once', 'save_as_default'))
);

CREATE TABLE IF NOT EXISTS report_writebacks (
    ts_code              varchar(32) PRIMARY KEY
                         REFERENCES stocks_master(ts_code),
    latest_view          text,
    current_focus        text,
    action_tag           varchar(16) NOT NULL,
    target_note          text,
    source_report_path   varchar(255),
    updated_at           timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_report_writebacks_action_tag
        CHECK (action_tag IN ('重点跟踪', '继续观察', '等待买点', '暂不跟踪'))
);

ALTER TABLE IF EXISTS stocks_master
    ADD COLUMN IF NOT EXISTS latest_report_period varchar(16);

ALTER TABLE IF EXISTS stocks_master
    ADD COLUMN IF NOT EXISTS audit_opinion varchar(64);

ALTER TABLE IF EXISTS stock_latest_scores
    ADD COLUMN IF NOT EXISTS latest_report_period varchar(16);

ALTER TABLE IF EXISTS stock_latest_scores
    ADD COLUMN IF NOT EXISTS audit_opinion varchar(64);
