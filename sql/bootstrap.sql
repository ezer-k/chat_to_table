-- WorldTable account bootstrap. Run as ACCOUNTADMIN in a fresh Snowflake account.
-- Account-level web search must also be enabled in:
-- AI & ML -> Agents -> Settings -> Enable web search.

USE ROLE ACCOUNTADMIN;

CREATE DATABASE IF NOT EXISTS WORLDTABLE;
CREATE SCHEMA IF NOT EXISTS WORLDTABLE.APP;
CREATE SCHEMA IF NOT EXISTS WORLDTABLE.RESULTS;

CREATE WAREHOUSE IF NOT EXISTS WORLDTABLE_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE;

CREATE TABLE IF NOT EXISTS WORLDTABLE.APP.DATASETS (
  DATASET_ID VARCHAR PRIMARY KEY,
  TITLE VARCHAR NOT NULL,
  QUESTION VARCHAR NOT NULL,
  DEFINITION VARCHAR,
  TABLE_NAME VARCHAR,
  ROW_COUNT NUMBER,
  CREATED_AT TIMESTAMP_TZ DEFAULT CURRENT_TIMESTAMP(),
  CREATED_BY VARCHAR DEFAULT CURRENT_USER()
);

CREATE TABLE IF NOT EXISTS WORLDTABLE.APP.EVIDENCE (
  DATASET_ID VARCHAR NOT NULL,
  ROW_NUMBER NUMBER,
  SOURCE_URL VARCHAR NOT NULL,
  SOURCE_TITLE VARCHAR,
  NOTE VARCHAR,
  RETRIEVED_AT TIMESTAMP_TZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE OR REPLACE AGENT WORLDTABLE.APP.RESEARCH_AGENT
  COMMENT = 'Researches public web data and returns cited, tabular JSON.'
  PROFILE = '{"display_name":"WorldTable Research Agent","color":"blue"}'
  FROM SPECIFICATION
  $$
  models:
    orchestration: openai-gpt-5-mini

  orchestration:
    budget:
      seconds: 180
      tokens: 24000

  instructions:
    orchestration: |
      Use Web Search for every research request. Prefer primary, official, and recent sources.
      Research enough sources to support every returned row. Never invent missing values.
    response: |
      Return ONLY valid JSON, without Markdown fences or surrounding prose.
      The JSON object must use this shape:
      {
        "title": "short dataset title",
        "definition": "scope, definitions, units, geography, and as-of date",
        "columns": [{"name":"snake_case_name","type":"TEXT|NUMBER|FLOAT|BOOLEAN|DATE"}],
        "rows": [{"field":"value", "source_urls":["https://..."]}],
        "limitations": ["important caveat"]
      }
      Every row must contain source_urls. Use null when a fact cannot be verified.
      Column names must be safe snake_case identifiers. Do not include source_urls in columns.
      Limit results to the row count requested by the user, with a hard maximum of 100 rows.

  tools:
    - tool_spec:
        type: web_search
        name: Web Search
  $$;

GRANT DATABASE ROLE SNOWFLAKE.CORTEX_AGENT_USER TO ROLE ACCOUNTADMIN;
GRANT USAGE ON DATABASE WORLDTABLE TO ROLE ACCOUNTADMIN;
GRANT USAGE ON SCHEMA WORLDTABLE.APP TO ROLE ACCOUNTADMIN;
GRANT USAGE ON AGENT WORLDTABLE.APP.RESEARCH_AGENT TO ROLE ACCOUNTADMIN;
GRANT USAGE ON WAREHOUSE WORLDTABLE_WH TO ROLE ACCOUNTADMIN;
GRANT USAGE ON COMPUTE POOL SYSTEM_COMPUTE_POOL_CPU TO ROLE ACCOUNTADMIN;

