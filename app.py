import streamlit as st
import json
import io
import csv
import zipfile
import tempfile
import logging
from datetime import date
from typing import Optional
from parsing import parse_create_tables
from filling import DataGenerator


# ----------------------------------------------------------------
# 1) Set up a custom logging handler to capture logs into Streamlit
# ----------------------------------------------------------------
class StreamlitLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        """
        A custom handler that redirects logs to Streamlit's session_state.
        We annotate logs as [INFO] or [ERROR] for clarity.
        """
        if "log_messages" not in st.session_state:
            st.session_state["log_messages"] = []

        level = record.levelname.upper()
        msg = record.getMessage()
        if level == "INFO":
            line = f"[INFO] {msg}"
        elif level == "ERROR":
            line = f"[ERROR] {msg}"
        else:
            line = f"[{level}] {msg}"
        st.session_state["log_messages"].append(line)


# Attach the custom Streamlit log handler
logger = logging.getLogger()
logger.setLevel(logging.INFO)
streamlit_handler = StreamlitLogHandler()
# Avoid duplicates if we reload:
if not any(isinstance(h, StreamlitLogHandler) for h in logger.handlers):
    logger.addHandler(streamlit_handler)


def export_data_as_json_in_memory(data: dict):
    """
    Convert the generated data (dict) into a JSON bytes in memory.

    Parameters
    ----------
    data : dict
        The generated data from DataGenerator.

    Returns
    -------
    bytes
        JSON-encoded bytes of the entire data.
    """
    return json.dumps(data, indent=2).encode("utf-8")


def export_data_as_csv_zip_in_memory(data: dict, tables_schema: dict) -> bytes:
    """
    Generate a ZIP archive in memory. Each table is stored as a separate CSV file.

    Parameters
    ----------
    data : dict
        The generated data from DataGenerator.
    tables_schema : dict
        The parsed schema dictionary (table -> columns, etc.).

    Returns
    -------
    bytes
        The ZIP archive content in memory (as bytes).
    """
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for table_name, rows in data.items():
            if not rows:
                continue
            output = io.StringIO()
            columns = [c['name'] for c in tables_schema[table_name]['columns']]
            writer = csv.DictWriter(output, fieldnames=columns)
            writer.writeheader()
            for row in rows:
                writer.writerow({col: row.get(col, "") for col in columns})
            zip_file.writestr(f"{table_name}.csv", output.getvalue())
    return zip_buffer.getvalue()


def main():
    st.title("Data Filler Web UI")

    # Step 1: SQL Script & Dialect Selection
    st.markdown("""
    **Step 1**: Choose your SQL dialect and enter your SQL CREATE TABLE script below.
    The selected dialect (e.g. PostgreSQL or MySQL) is used to parse the schema.
    """)
    dialect = st.selectbox(
        "SQL Dialect",
        options=["postgres", "mysql", "sqlite", "oracle"],
        index=0,
        help="Choose the SQL dialect for your CREATE TABLE script."
    )

    if "tables_parsed" not in st.session_state:
        st.session_state["tables_parsed"] = None

    sql_script = st.text_area(
        "SQL Script",
        value="-- Paste your CREATE TABLE script here",
        height=250
    )

    if st.button("Parse SQL"):
        try:
            tables_parsed = parse_create_tables(sql_script.strip(), dialect=dialect)
            st.session_state["tables_parsed"] = tables_parsed
            logging.info("SQL parsed successfully!")
            st.success("SQL parsed successfully!")
        except Exception as e:
            logging.error(f"Error parsing SQL: {e}")
            st.error(f"Error parsing SQL: {e}")
            st.session_state["tables_parsed"] = None

    # Step 2: Configuration (only if the schema was parsed)
    if st.session_state["tables_parsed"] is not None:
        schema = st.session_state["tables_parsed"]
        st.markdown("### Parsed Tables")
        st.json(schema)

        st.markdown("---")
        st.markdown("## Step 2: Configuration")

        # predefined_values
        st.subheader("`predefined_values` (JSON)")
        default_predef = json.dumps({
            "global": {
                "sex": ["M", "F"]
            }
        }, indent=2)
        predefined_values_str = st.text_area(
            "Enter `predefined_values` (JSON)",
            value=default_predef,
            height=200
        )

        # column_type_mappings
        st.subheader("`column_type_mappings` (JSON)")
        default_colmap = json.dumps({
            "global": {
                "first_name": "first_name",
                "last_name": "last_name",
                "email": "email"
            }
        }, indent=2)
        column_type_mappings_str = st.text_area(
            "Enter `column_type_mappings` (JSON)",
            value=default_colmap,
            height=200
        )

        # num_rows_per_table
        st.subheader("`num_rows_per_table` (JSON)")
        default_numrows = json.dumps({tbl: 10 for tbl in schema}, indent=2)
        num_rows_per_table_str = st.text_area(
            "Enter `num_rows_per_table` (JSON)",
            value=default_numrows,
            height=150
        )

        # global_num_rows
        st.subheader("Global Number of Rows (Fallback)")
        global_num_rows = st.number_input(
            "Global num_rows (fallback if table not configured)",
            min_value=1,
            value=10
        )

        # Automatic Column Mapping Guessing
        st.subheader("Automatic Column Mapping Guessing")
        guess_mapping = st.checkbox("Enable automatic column mapping guessing", value=False)
        threshold_for_guessing = st.slider("Fuzzy matching threshold", 0.0, 1.0, 0.8) if guess_mapping else 0.8

        # Button to preview inferred mappings if user wants
        if guess_mapping:
            st.write("Use the preview button if you want to see how columns might be auto-mapped.")
            if st.button("Preview Inferred Mappings"):
                # We assume DataGenerator includes a method like `preview_inferred_mappings()`,
                # or we can replicate logic from ColumnMappingsGenerator.
                # For demonstration, we'll call the method if it exists.
                dg_temp = DataGenerator(
                    tables=schema,
                    num_rows=global_num_rows,
                    guess_column_type_mappings=True,
                    threshold_for_guessing=threshold_for_guessing
                )
                logging.info("Previewing auto-inferred mappings with a sample of 5 rows per table...")
                # The user wants to see sample data from the 'preview_inferred_mappings' method
                dg_temp.preview_inferred_mappings(num_preview=5)

        # Step 3: Generate Data and Export
        st.markdown("---")
        st.markdown("## Step 3: Generate Data")

        if st.button("Generate Data"):
            try:
                # Parse JSON configurations
                logging.info("Reading JSON user configurations...")
                predefined_values = json.loads(predefined_values_str)
                column_type_mappings = json.loads(column_type_mappings_str)
                num_rows_per_table = json.loads(num_rows_per_table_str)

                data_generator = DataGenerator(
                    tables=schema,
                    num_rows=global_num_rows,
                    predefined_values=predefined_values,
                    column_type_mappings=column_type_mappings,
                    num_rows_per_table=num_rows_per_table,
                    guess_column_type_mappings=guess_mapping,
                    threshold_for_guessing=threshold_for_guessing
                )

                logging.info("Generating synthetic data...")
                generated_data = data_generator.generate_data()
                st.success("Data generated successfully!")
                logging.info("Data generation complete.")

                # Show preview: first 5 rows per table
                st.markdown("### Data Preview (first 5 rows per table)")
                preview_data = {tbl: rows[:5] for tbl, rows in generated_data.items()}
                st.json(preview_data)

                # Provide download buttons:
                logging.info("Preparing SQL Insert queries for download.")
                sql_insert_str = data_generator.export_as_sql_insert_query()
                st.download_button(
                    label="Download SQL Insert Queries",
                    data=sql_insert_str,
                    file_name="fake_data.sql",
                    mime="text/plain"
                )

                logging.info("Preparing JSON data for download.")
                json_bytes = export_data_as_json_in_memory(generated_data)
                st.download_button(
                    label="Download Data (JSON)",
                    data=json_bytes,
                    file_name="fake_data.json",
                    mime="application/json"
                )

                logging.info("Preparing CSV data as a ZIP in memory.")
                csv_zip = export_data_as_csv_zip_in_memory(generated_data, schema)
                st.download_button(
                    label="Download Data (CSV ZIP)",
                    data=csv_zip,
                    file_name="fake_data_csv.zip",
                    mime="application/zip"
                )

            except Exception as e:
                logging.error(f"Error generating data: {e}")
                st.error(f"Error generating data: {e}")

    st.markdown("---")
    st.markdown("## Log Output")
    log_messages = st.session_state.get("log_messages", [])
    if log_messages:
        st.text_area("Logs (most recent last)", "\n".join(log_messages), height=200)
    else:
        st.write("No logs available.")


if __name__ == "__main__":
    main()
