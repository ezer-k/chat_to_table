# WorldTable

WorldTable is a Snowflake-native research application. Ask for real-world information in tabular form, let a Cortex Agent research the public web, inspect the cited result, and persist it as an ordinary Snowflake table that can be joined with private warehouse data.

## MVP capabilities

- Natural-language research requests
- Cortex Agent web search
- Structured, typed tabular output
- Row-level source URLs
- Interactive table preview
- CSV download
- Persistent Snowflake result tables and evidence records
- Container-runtime Streamlit interface

## Architecture

```text
Streamlit in Snowflake
  -> SNOWFLAKE.CORTEX.DATA_AGENT_RUN
  -> Cortex Agent + built-in web search
  -> validated JSON dataset
  -> interactive dataframe
  -> WORLDTABLE.RESULTS.<generated table>
```

## Prerequisites

- A Snowflake account in a region supporting Cortex Agents and container-runtime Streamlit
- `ACCOUNTADMIN` for initial setup
- Snowflake CLI 3.14 or newer
- Git and Python 3.11+
- Available Snowflake credits

## Deploy from scratch

1. Clone this repository.

   ```bash
   git clone <repository-url>
   cd worldtable
   ```

2. Install Snowflake CLI.

   ```bash
   python -m pip install "snowflake-cli>=3.14"
   snow --version
   ```

3. Configure a Snowflake CLI connection. Do not commit credentials.

   ```bash
   snow connection add
   snow connection test
   ```

4. In Snowsight, enable account-level web search:

   `AI & ML` → `Agents` → `Settings` → `Enable web search`

   Snowflake sends generated search queries to its web-search provider. Review the notice shown by Snowflake before enabling it.

5. Run the idempotent bootstrap script as `ACCOUNTADMIN`.

   ```bash
   snow sql -f sql/bootstrap.sql
   ```

6. Deploy the container-runtime Streamlit app.

   ```bash
   snow streamlit deploy worldtable --replace --open
   ```

7. Ask a bounded test question, such as:

   ```text
   List the 15 largest passenger-car manufacturers worldwide with headquarters
   country, parent company, and latest reported annual production. Cite every row.
   ```

8. Review the result and select **Save as Snowflake table**. Query it with:

   ```sql
   SHOW TABLES IN SCHEMA WORLDTABLE.RESULTS;
   SELECT * FROM WORLDTABLE.RESULTS.<TABLE_NAME>;
   ```

## Cost controls

- The query warehouse is X-Small and suspends after 60 seconds.
- The agent is limited to 180 seconds and 24,000 orchestration tokens per request.
- The UI enforces a maximum of 100 rows.
- Suspend the Streamlit compute pool or undeploy the app when it is not being demonstrated.
- Monitor `SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AGENT_USAGE_HISTORY` and warehouse metering.

## Reproducing on another account

All durable project state is represented by:

- `sql/bootstrap.sql`: databases, schemas, warehouse, tables, grants, and agent specification
- `snowflake.yml`: Streamlit runtime, compute pool, warehouse, and artifacts
- `requirements.txt`: Python dependencies
- `streamlit_app.py`: complete application
- `sql/teardown.sql`: removal procedure

The only intentional manual account-level action is enabling Cortex Agent web search. This setting cannot safely be assumed by an install script because it controls transmission of search queries outside Snowflake.

## Teardown

The following permanently removes WorldTable data and compute objects:

```bash
snow sql -f sql/teardown.sql
```

## Known MVP limitations

- Research quality depends on source availability and Cortex Agent behavior.
- JSON conformance may occasionally fail; the UI reports the error rather than saving malformed data.
- Citations are currently recorded at row level, not individual-cell level.
- Saving a second dataset with the same generated title can collide with an existing table name.
- The synchronous SQL wrapper does not stream intermediate research progress.

