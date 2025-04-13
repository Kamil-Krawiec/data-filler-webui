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

# Set up logging if not already configured
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def main():
    st.title("Data Filler Web UI")

    # -- Step 1: SQL Script & Dialect Selection --
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
            st.success("SQL script parsed successfully!")
            logger.info("SQL parsed successfully.")
        except Exception as e:
            st.error(f"Error parsing SQL: {e}")
            logger.error(f"Error parsing SQL: {e}")
            st.session_state["tables_parsed"] = None

    # -- Step 2: Configuration Section --
    if st.session_state["tables_parsed"] is not None:
        schema = st.session_state["tables_parsed"]
        st.markdown("### Parsed Tables")
        st.json(schema)

        st.markdown("---")
        st.markdown("## Step 2: Configuration")

        st.subheader("`predefined_values` (JSON)")
        default_predef = json.dumps({"global": {"sex": ["M", "F"]}}, indent=2)
        predefined_values_str = st.text_area(
            "Enter `predefined_values` as JSON",
            value=default_predef,
            height=200
        )

        st.subheader("`column_type_mappings` (JSON)")
        default_colmap = json.dumps({
            "global": {
                "first_name": "first_name",
                "last_name": "last_name",
                "email": "email"
            }
        }, indent=2)
        column_type_mappings_str = st.text_area(
            "Enter `column_type_mappings` as JSON",
            value=default_colmap,
            height=200
        )

        st.subheader("`num_rows_per_table` (JSON)")
        default_numrows = json.dumps({tbl: 10 for tbl in schema}, indent=2)
        num_rows_per_table_str = st.text_area(
            "Enter `num_rows_per_table` as JSON",
            value=default_numrows,
            height=150
        )

        st.subheader("Global Number of Rows (Fallback)")
        global_num_rows = st.number_input(
            "Global num_rows (fallback if a table is not configured)",
            min_value=1,
            value=10
        )

        # Optional: Automatic Column Mapping Guessing
        st.subheader("Automatic Column Mapping Guessing")
        guess_mapping = st.checkbox("Enable automatic column mapping guessing", value=False)
        threshold_for_guessing = st.slider("Fuzzy matching threshold", 0.0, 1.0, 0.8) if guess_mapping else 0.8

        # -- Step 3: Generate Data --
        st.markdown("---")
        st.markdown("## Step 3: Generate Data")
        if st.button("Generate Data"):
            try:
                # Parse JSON configurations
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

                generated_data = data_generator.generate_data()
                st.success("Data generated successfully!")
                st.markdown("### Data Preview (first 5 rows per table)")
                preview_data = {tbl: rows[:5] for tbl, rows in generated_data.items()}
                st.json(preview_data)
                logger.info("Data generation complete.")

                # -- Data Export using built-in export_data_files --
                # Use a temporary directory to capture exported files
                with tempfile.TemporaryDirectory() as tmpdirname:
                    # Export SQL - data is written to a single SQL file in the temporary directory.
                    data_generator.export_data_files(tmpdirname, file_type="SQL")
                    sql_path = os.path.join(tmpdirname, "data_inserts.sql")
                    with open(sql_path, "r", encoding="utf-8") as f:
                        sql_insert_str = f.read()
                    st.download_button(
                        label="Download SQL Insert Queries",
                        data=sql_insert_str,
                        file_name="fake_data.sql",
                        mime="text/plain"
                    )

                    # Export JSON - data is written as one JSON file per table.
                    data_generator.export_data_files(tmpdirname, file_type="JSON")
                    # Zip all JSON files together
                    json_zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(json_zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
                        for json_file in glob.glob(os.path.join(tmpdirname, "*.json")):
                            zipf.write(json_file, arcname=os.path.basename(json_file))
                    st.download_button(
                        label="Download Data (JSON ZIP)",
                        data=json_zip_buffer.getvalue(),
                        file_name="fake_data_json.zip",
                        mime="application/zip"
                    )

                    # Export CSV - data is written as one CSV file per table.
                    data_generator.export_data_files(tmpdirname, file_type="CSV")
                    # Zip all CSV files together
                    csv_zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(csv_zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
                        for csv_file in glob.glob(os.path.join(tmpdirname, "*.csv")):
                            zipf.write(csv_file, arcname=os.path.basename(csv_file))
                    st.download_button(
                        label="Download Data (CSV ZIP)",
                        data=csv_zip_buffer.getvalue(),
                        file_name="fake_data_csv.zip",
                        mime="application/zip"
                    )

            except Exception as e:
                st.error(f"Error generating data: {e}")
                logger.error(f"Error generating data: {e}")

    st.markdown("---")
    st.markdown("## Log Output")
    log_messages = st.session_state.get("log_messages", [])
    if log_messages:
        st.text_area("Logs (most recent last)", "\n".join(log_messages), height=200)
    else:
        st.write("No logs available.")


if __name__ == "__main__":
    main()