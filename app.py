import streamlit as st
import json
import os
import io
import csv
import zipfile
import tempfile
import glob
import logging
from datetime import date
from parsing import parse_create_tables
from filling import DataGenerator


# ----------------------------------------------------------------
# Custom streamlit logger handler to capture log messages
# ----------------------------------------------------------------
class StreamlitLogHandler(logging.Handler):
    """
    A custom handler that captures logs and stores them in Streamlit's session_state.
    Each log is annotated with its level (e.g. [INFO], [ERROR]) for clarity.
    """

    def emit(self, record: logging.LogRecord) -> None:
        if "log_messages" not in st.session_state:
            st.session_state["log_messages"] = []
        lvl = record.levelname.upper()
        msg = record.getMessage()
        if lvl == "INFO":
            line = f"[INFO] {msg}"
        elif lvl == "ERROR":
            line = f"[ERROR] {msg}"
        else:
            line = f"[{lvl}] {msg}"
        st.session_state["log_messages"].append(line)


# ----------------------------------------------------------------
# Configure logging to avoid duplicate logs and propagation
# ----------------------------------------------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.propagate = False

if not any(isinstance(h, StreamlitLogHandler) for h in logger.handlers):
    logger.addHandler(StreamlitLogHandler())



def export_files_zip_in_memory(directory: str, pattern: str) -> bytes:
    """
    Zip all files from a given directory that match the pattern in memory.

    Parameters
    ----------
    directory : str
        Directory containing exported files.
    pattern : str
        Glob pattern (e.g. "*.json" or "*.csv").

    Returns
    -------
    bytes
        The ZIP archive content in memory.
    """
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        for fpath in glob.glob(os.path.join(directory, pattern)):
            zipf.write(fpath, arcname=os.path.basename(fpath))
    return zip_buffer.getvalue()


def main():
    st.title("Data Filler Web UI")

    # ----------------------------------------------------------------
    # Step 1: SQL Script & Dialect Selection
    # ----------------------------------------------------------------
    st.markdown("""
    **Step 1**: Choose your SQL dialect and paste your SQL CREATE TABLE script below.
    The selected dialect (e.g., PostgreSQL or MySQL) is used to parse the schema.
    """)
    dialect = st.selectbox(
        "SQL Dialect",
        options=["postgres", "mysql", "sqlite", "oracle"],
        index=0,
        help="Choose the SQL dialect for your CREATE TABLE script."
    )

    if "tables_parsed" not in st.session_state:
        st.session_state["tables_parsed"] = None
    if "data_generator" not in st.session_state:
        st.session_state["data_generator"] = None

    sql_script = st.text_area("SQL Script", "-- Paste your CREATE TABLE script here", height=250)

    if st.button("Parse SQL"):
        try:
            tables_parsed = parse_create_tables(sql_script.strip(), dialect=dialect)
            st.session_state["tables_parsed"] = tables_parsed
            st.session_state["data_generator"] = None  # Clear previous instance
            st.success("SQL script parsed successfully!")
            logger.info("SQL script parsed successfully using dialect '%s'.", dialect)
        except Exception as e:
            st.session_state["tables_parsed"] = None
            st.session_state["data_generator"] = None
            st.error(f"Error parsing SQL: {e}")
            logger.error("Error parsing SQL: %s", e)

    # ----------------------------------------------------------------
    # Step 2: Configuration Section (only if schema is parsed)
    # ----------------------------------------------------------------
    if st.session_state["tables_parsed"] is not None:
        schema = st.session_state["tables_parsed"]
        st.markdown("### Parsed Tables")
        st.json(schema)

        st.markdown("---")
        st.markdown("## Step 2: Configuration")

        st.subheader("`predefined_values` (JSON)")
        default_predef = json.dumps({"global": {"sex": ["M", "F"]}}, indent=2)
        predefined_values_str = st.text_area("Enter `predefined_values` as JSON", value=default_predef, height=200)

        st.subheader("`column_type_mappings` (JSON)")
        default_colmap = json.dumps({
            "global": {
                "first_name": "first_name",
                "last_name": "last_name",
                "email": "email"
            }
        }, indent=2)
        column_type_mappings_str = st.text_area("Enter `column_type_mappings` as JSON", value=default_colmap,
                                                height=200)

        st.subheader("`num_rows_per_table` (JSON)")
        default_numrows = json.dumps({tbl: 10 for tbl in schema}, indent=2)
        num_rows_per_table_str = st.text_area("Enter `num_rows_per_table` as JSON", value=default_numrows, height=150)

        st.subheader("Global Number of Rows (Fallback)")
        global_num_rows = st.number_input("Global num_rows (fallback if a table is not configured)", min_value=1,
                                          value=10)

        st.subheader("Automatic Column Mapping Guessing")
        guess_mapping = st.checkbox("Enable automatic column mapping guessing", value=False)
        threshold_for_guessing = st.slider("Fuzzy matching threshold", 0.0, 1.0, 0.8) if guess_mapping else 0.8

        # Optionally, a preview button for auto-mappings if desired…
        if guess_mapping and st.button("Preview Inferred Mappings"):
            try:
                # Create a temporary generator instance solely for previewing mappings.
                dg_preview = DataGenerator(
                    tables=schema,
                    num_rows=5,
                    guess_column_type_mappings=True,
                    threshold_for_guessing=threshold_for_guessing
                )
                st.text("Previewing inferred mappings (5 sample rows per table):")
                dg_preview.preview_inferred_mappings(num_preview=5)
                logger.info("Auto-inferred column mapping preview complete.")
            except Exception as e:
                st.error(f"Error previewing mappings: {e}")
                logger.error("Error previewing mappings: %s", e)

        # ----------------------------------------------------------------
        # Step 3: Generate Data
        # ----------------------------------------------------------------
        st.markdown("---")
        st.markdown("## Step 3: Generate Data")
        if st.button("Generate Data"):
            try:
                logger.info("Reading JSON configuration for data generation...")
                predefined_values = json.loads(predefined_values_str)
                column_type_mappings = json.loads(column_type_mappings_str)
                num_rows_per_table = json.loads(num_rows_per_table_str)

                dg = DataGenerator(
                    tables=schema,
                    num_rows=global_num_rows,
                    predefined_values=predefined_values,
                    column_type_mappings=column_type_mappings,
                    num_rows_per_table=num_rows_per_table,
                    guess_column_type_mappings=guess_mapping,
                    threshold_for_guessing=threshold_for_guessing
                )

                generated_data = dg.generate_data()
                st.session_state["data_generator"] = dg  # Store the generator instance
                st.success("Data generated successfully!")
                logger.info("Data generation complete.")

                st.markdown("### Data Preview (first 5 rows per table)")
                preview_data = {tbl: rows[:5] for tbl, rows in generated_data.items()}
                st.json(preview_data)

            except Exception as e:
                st.session_state["data_generator"] = None
                st.error(f"Error generating data: {e}")
                logger.error("Error generating data: %s", e)

    # ----------------------------------------------------------------
    # Step 4: Download Exported Data (only if data generated)
    # ----------------------------------------------------------------
    if st.session_state.get("data_generator") is not None:
        st.markdown("---")
        st.markdown("## Step 4: Export & Download Data")
        # Get the DataGenerator instance from session_state.
        dg_export = st.session_state["data_generator"]

        with tempfile.TemporaryDirectory() as tmpdir:
            # 1) SQL Export
            dg_export.export_data_files(tmpdir, file_type="SQL")
            sql_path = os.path.join(tmpdir, "data_inserts.sql")
            if os.path.exists(sql_path):
                with open(sql_path, "r", encoding="utf-8") as f:
                    sql_content = f.read()
                st.download_button(
                    label="Download SQL Insert Queries",
                    data=sql_content,
                    file_name="fake_data.sql",
                    mime="text/plain"
                )

            # 2) JSON Export (exported per table) -> Zip them
            dg_export.export_data_files(tmpdir, file_type="JSON")
            json_zip_bytes = export_files_zip_in_memory(tmpdir, "*.json")
            st.download_button(
                label="Download Data (JSON ZIP)",
                data=json_zip_bytes,
                file_name="fake_data_json.zip",
                mime="application/zip"
            )

            # 3) CSV Export (exported per table) -> Zip them
            dg_export.export_data_files(tmpdir, file_type="CSV")
            csv_zip_bytes = export_files_zip_in_memory(tmpdir, "*.csv")
            st.download_button(
                label="Download Data (CSV ZIP)",
                data=csv_zip_bytes,
                file_name="fake_data_csv.zip",
                mime="application/zip"
            )

    # ----------------------------------------------------------------
    # Step 5: Log Output
    # ----------------------------------------------------------------
    st.markdown("---")
    st.markdown("## Log Output")
    if "log_messages" in st.session_state and st.session_state["log_messages"]:
        st.text_area("Logs (most recent last)", "\n".join(st.session_state["log_messages"]), height=200)
    else:
        st.write("No logs available.")


if __name__ == "__main__":
    main()
