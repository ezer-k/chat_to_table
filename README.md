# WorldTable

WorldTable is a Snowflake-native research application. Ask for real-world information in tabular form, let a Cortex Agent research the public web, inspect the cited result, and persist it as an ordinary Snowflake table that can be joined with private warehouse data.

## MVP capabilities

- Natural-language research requests
- Cortex Agent web search
- Structured, typed tabular output
- Row-level source URLs
- Interactive table preview and CSV download
- Persistent Snowflake result tables and evidence records
- Container-runtime Streamlit interface
- Snowflake-native Git installation and updates

## Architecture

```text
Public GitHub repository
  -> Snowflake Git repository clone
  -> Git-hosted idempotent installer
  -> container-runtime Streamlit
  -> Cortex Agent + built-in web search
  -> validated JSON dataset
  -> interactive dataframe
  -> WORLDTABLE.RESULTS.<generated table>
```

## Prerequisites

- A Snowflake account in a region supporting Cortex Agents and container-runtime Streamlit
- `ACCOUNTADMIN` for initial setup
- Available Snowflake credits
- Account-level Cortex Agent web search enabled

## Install from scratch: one worksheet

1. Sign in to Snowsight and open a new SQL worksheet.

2. Enable account-level web search under:

   `AI & ML` -> `Agents` -> `Settings` -> `Enable web search`

   Snowflake sends generated search queries to its web-search provider. Review the notice shown by Snowflake before enabling it.

3. Paste and run this installer:

   ```sql
   USE ROLE ACCOUNTADMIN;

   CREATE DATABASE IF NOT EXISTS WORLDTABLE;
   CREATE SCHEMA IF NOT EXISTS WORLDTABLE.APP;

   CREATE API INTEGRATION IF NOT EXISTS WORLDTABLE_GITHUB_API
     API_PROVIDER = GIT_HTTPS_API
     API_ALLOWED_PREFIXES = ('https://github.com/ezer-k/chat_to_table')
     ENABLED = TRUE;

   CREATE GIT REPOSITORY IF NOT EXISTS WORLDTABLE.APP.SOURCE
     API_INTEGRATION = WORLDTABLE_GITHUB_API
     ORIGIN = 'https://github.com/ezer-k/chat_to_table.git';

   ALTER GIT REPOSITORY WORLDTABLE.APP.SOURCE FETCH;

   EXECUTE IMMEDIATE FROM
     @WORLDTABLE.APP.SOURCE/branches/main/sql/install.sql;
   ```

   The same bootstrap is stored in [`sql/setup_git.sql`](sql/setup_git.sql).

4. Open `Projects` -> `Streamlit` -> `WorldTable`.

5. Ask a bounded test question, for example:

   ```text
   List the 15 largest passenger-car manufacturers worldwide with headquarters
   country, parent company, and latest reported annual production. Cite every row.
   ```

6. Review the result and select **Save as Snowflake table**. Query saved results with:

   ```sql
   SHOW TABLES IN SCHEMA WORLDTABLE.RESULTS;
   SELECT * FROM WORLDTABLE.RESULTS.<TABLE_NAME>;
   ```

## Update from GitHub

After changes are merged into `main`, run:

```sql
EXECUTE IMMEDIATE FROM
  @WORLDTABLE.APP.SOURCE/branches/main/sql/update.sql;
```

The update fetches the latest branch and redeploys the agent and Streamlit app. Saved datasets and evidence tables are preserved.

## Optional Snowflake CLI workflow

Snowflake-native Git is the primary installation path. Contributors who prefer the CLI can clone the repository, configure a Snowflake connection, and run the same scripts:

```bash
git clone https://github.com/ezer-k/chat_to_table.git
cd chat_to_table
snow connection add
snow connection test
snow sql -f sql/setup_git.sql
```

## Cost controls

- The query warehouse is X-Small and suspends after 60 seconds.
- The agent is limited to 180 seconds and 24,000 orchestration tokens per request.
- The UI enforces a maximum of 100 rows.
- Suspend the Streamlit compute pool or drop the app when it is not being demonstrated.
- Monitor `SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AGENT_USAGE_HISTORY` and warehouse metering.

## Reproducing on another account

All durable project state is version controlled:

- `sql/setup_git.sql`: initial public GitHub connection
- `sql/install.sql`: database objects, grants, agent, and Streamlit deployment
- `sql/update.sql`: fetch and redeploy procedure
- `streamlit_app.py`: complete application
- `requirements.txt`: container dependencies
- `snowflake.yml`: optional CLI project definition
- `sql/teardown.sql`: removal procedure

The only intentional manual account-level action is enabling Cortex Agent web search. This setting controls transmission of search queries outside Snowflake and should not be silently enabled by an installer.

## Teardown

The following permanently removes WorldTable data, application objects, warehouse, Git clone, and Git API integration:

```sql
EXECUTE IMMEDIATE FROM
  @WORLDTABLE.APP.SOURCE/branches/main/sql/teardown.sql;
```

Because the teardown drops the Git repository along with the database, run it only once. The same file can also be copied from GitHub into a worksheet if the repository object is unavailable.

## Known MVP limitations

- Research quality depends on source availability and Cortex Agent behavior.
- JSON conformance may occasionally fail; the UI reports the error rather than saving malformed data.
- Citations are recorded at row level, not individual-cell level.
- Saving a second dataset with the same generated title can collide with an existing table name.
- The synchronous SQL wrapper does not stream intermediate research progress.
