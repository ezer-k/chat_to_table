import json
import re
import uuid
from datetime import date
from typing import Any

import pandas as pd
import streamlit as st
from snowflake.snowpark.context import get_active_session


AGENT_NAME = "WORLDTABLE.APP.RESEARCH_AGENT!LIVE"
RESULT_SCHEMA = "WORLDTABLE.RESULTS"
MAX_ROWS = 100


def quote_ident(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_]", "_", value).strip("_").upper()
    if not safe or safe[0].isdigit():
        safe = f"DATASET_{safe}"
    return f'"{safe[:200]}"'


def research_prompt(question: str, row_limit: int) -> str:
    return f"""Create a cited table answering this request:
{question}

Return at most {min(row_limit, MAX_ROWS)} rows. Establish a precise definition and as-of date.
Return only the JSON object required by your response instructions."""


def extract_response_text(response: dict[str, Any]) -> str:
    chunks: list[str] = []
    for item in response.get("content", []):
        if item.get("type") == "text":
            text = item.get("text", "")
            if isinstance(text, dict):
                text = text.get("text", "")
            chunks.append(str(text))
    if not chunks and isinstance(response.get("text"), str):
        chunks.append(response["text"])
    return "\n".join(chunks).strip()


def parse_dataset(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.I | re.S)
    data = json.loads(cleaned)
    required = {"title", "definition", "columns", "rows"}
    missing = required - set(data)
    if missing:
        raise ValueError(f"Agent response is missing: {', '.join(sorted(missing))}")
    if not isinstance(data["rows"], list) or len(data["rows"]) > MAX_ROWS:
        raise ValueError("Agent returned an invalid number of rows")
    names = [c["name"] for c in data["columns"]]
    for row in data["rows"]:
        row.setdefault("source_urls", [])
        for name in names:
            row.setdefault(name, None)
    return data


def run_agent(session, question: str, row_limit: int) -> dict[str, Any]:
    body = {
        "messages": [{
            "role": "user",
            "content": [{"type": "text", "text": research_prompt(question, row_limit)}],
        }],
        "background": False,
        "stream": False,
        "tool_choice": {"type": "auto", "name": ["Web Search"]},
    }
    result = session.sql(
        "SELECT TRY_PARSE_JSON(SNOWFLAKE.CORTEX.DATA_AGENT_RUN(?, ?)) AS RESPONSE",
        params=[AGENT_NAME, json.dumps(body)],
    ).collect()[0]["RESPONSE"]
    response = result if isinstance(result, dict) else json.loads(str(result))
    return parse_dataset(extract_response_text(response))


def dataframe_for(dataset: dict[str, Any]) -> pd.DataFrame:
    names = [column["name"] for column in dataset["columns"]]
    return pd.DataFrame([{name: row.get(name) for name in names} for row in dataset["rows"]])


def save_dataset(session, dataset: dict[str, Any], question: str) -> str:
    dataset_id = str(uuid.uuid4())
    table_ident = quote_ident(dataset["title"])
    table_name = f"{RESULT_SCHEMA}.{table_ident}"
    frame = dataframe_for(dataset)
    session.write_pandas(
        frame,
        table_name=table_ident.strip('"'),
        database="WORLDTABLE",
        schema="RESULTS",
        auto_create_table=True,
        overwrite=False,
    )
    session.sql(
        """INSERT INTO WORLDTABLE.APP.DATASETS
        (DATASET_ID, TITLE, QUESTION, DEFINITION, TABLE_NAME, ROW_COUNT)
        SELECT ?, ?, ?, ?, ?, ?""",
        params=[dataset_id, dataset["title"], question, dataset["definition"], table_name, len(frame)],
    ).collect()
    evidence_rows = []
    for index, row in enumerate(dataset["rows"], start=1):
        for url in row.get("source_urls", []):
            evidence_rows.append((dataset_id, index, str(url), None, None))
    if evidence_rows:
        session.create_dataframe(
            evidence_rows,
            schema=["DATASET_ID", "ROW_NUMBER", "SOURCE_URL", "SOURCE_TITLE", "NOTE"],
        ).write.mode("append").save_as_table("WORLDTABLE.APP.EVIDENCE")
    return table_name


st.set_page_config(page_title="WorldTable", page_icon="🌍", layout="wide")
st.title("🌍 WorldTable")
st.caption("Turn a real-world research question into a cited, joinable Snowflake table.")

session = get_active_session()
question = st.text_area(
    "What table should we research?",
    placeholder="List the 30 largest car manufacturers worldwide with headquarters country, parent company, and latest annual production.",
    height=110,
)
row_limit = st.number_input("Maximum rows", min_value=1, max_value=MAX_ROWS, value=25)

if st.button("Research", type="primary", disabled=not question.strip()):
    with st.spinner("Searching and structuring public sources…"):
        try:
            st.session_state.dataset = run_agent(session, question.strip(), int(row_limit))
            st.session_state.question = question.strip()
        except Exception as exc:
            st.error(f"Research failed: {exc}")

dataset = st.session_state.get("dataset")
if dataset:
    st.subheader(dataset["title"])
    st.write(dataset["definition"])
    frame = dataframe_for(dataset)
    st.dataframe(frame, use_container_width=True, hide_index=True)
    st.download_button(
        "Download CSV",
        frame.to_csv(index=False).encode("utf-8"),
        file_name=f"worldtable-{date.today().isoformat()}.csv",
        mime="text/csv",
    )

    sources = sorted({url for row in dataset["rows"] for url in row.get("source_urls", [])})
    with st.expander(f"Sources ({len(sources)})"):
        for url in sources:
            st.markdown(f"- [{url}]({url})")
    if dataset.get("limitations"):
        with st.expander("Limitations"):
            for limitation in dataset["limitations"]:
                st.write(f"- {limitation}")

    if st.button("Save as Snowflake table"):
        with st.spinner("Saving dataset and evidence…"):
            try:
                saved = save_dataset(session, dataset, st.session_state.question)
                st.success(f"Saved as {saved}")
                st.code(f"SELECT * FROM {saved};", language="sql")
            except Exception as exc:
                st.error(f"Save failed: {exc}")

