import streamlit as st
import json

from parsing import parse_create_tables
from filling import DataGenerator


def main():
    st.title("Data Filler Web UI")

    st.write(
        """
        **Step 1**: Paste or modify your SQL CREATE script below, then click **Parse SQL**.
        Once it’s successfully parsed, additional configuration steps will appear.
        """
    )

    # ----------------------------------------------------------------
    # STEP 1: SQL Script input
    # ----------------------------------------------------------------
    if "tables_parsed" not in st.session_state:
        st.session_state["tables_parsed"] = None

    default_sql = """\
CREATE TABLE Authors (
    author_id SERIAL PRIMARY KEY,
    sex CHAR(1) NOT NULL,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    birth_date DATE NOT NULL
);

CREATE TABLE Categories (
    category_id SERIAL PRIMARY KEY,
    category_name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE Books (
    book_id SERIAL PRIMARY KEY,
    title VARCHAR(100) NOT NULL,
    isbn VARCHAR(13) NOT NULL UNIQUE,
    author_id INT NOT NULL,
    publication_year INT NOT NULL,
    category_id INT NOT NULL,
    penalty_rate DECIMAL(5,2) NOT NULL
);
"""
    sql_script = st.text_area(
        "SQL Script",
        value=default_sql,
        height=200
    )

    if st.button("Parse SQL"):
        try:
            tables_parsed = parse_create_tables(sql_script.strip())
            st.session_state["tables_parsed"] = tables_parsed
            st.success("SQL script parsed successfully!")
        except Exception as e:
            st.error(f"Error parsing SQL script: {e}")
            st.session_state["tables_parsed"] = None

    # ----------------------------------------------------------------
    # STEP 2: Show subsequent configs only if we have parsed tables
    # ----------------------------------------------------------------
    if st.session_state["tables_parsed"] is not None:
        tables_parsed = st.session_state["tables_parsed"]

        st.write("### Parsed Tables")
        st.json(tables_parsed)

        st.write(
            """
            **Step 2**: Provide your configuration for:

            - `predefined_values`: A dictionary that can specify global or per-table/per-column fixed choices.
            - `column_type_mappings`: A dictionary that can specify how to fill columns (Faker method, custom lambda, etc.).
            - `num_rows_per_table`: A dictionary for row counts per table.
            - A global fallback `num_rows`.
            """
        )

        # Show some helper “example” JSON with the actual table/columns commented out
        # so the user knows the table/column structure. We’ll build a commented “hint.”
        example_predef = {
            "global": {
                "sex": ["M", "F"]
            },
            # Placeholders for each table & column, so user knows how they might fill it:
        }
        example_colmap = {
            "global": {
                "first_name": "first_name",
                "last_name": "last_name",
                "email": "email"
            },
            # Placeholders for each table & column as well
        }
        example_numrows = {}

        # Build table-based placeholders
        for tbl_name, tbl_def in tables_parsed.items():
            # For predefined_values
            example_predef[tbl_name] = {
                # "column_name": ["Possible", "Values"],
            }
            # For column_type_mappings
            example_colmap[tbl_name] = {
                # "column_name": "faker_method_or_lambda"
            }
            # For num_rows_per_table
            example_numrows[tbl_name] = 10

        # Convert these dicts to strings with JSON, but we’ll place a comment for each column
        # so the user sees it. We do that by building the JSON, then appending comments.
        def dict_to_json_with_comments(d, tables_parsed):
            """
            Convert the placeholder dict to a JSON string
            and then append commentary lines with table/column info.
            """
            base_json = json.dumps(d, indent=2)
            lines = base_json.splitlines()
            lines.append("")
            lines.append("// Tables & columns discovered:")
            for tname, tdef in tables_parsed.items():
                lines.append(f"// Table: {tname}")
                for col in tdef["columns"]:
                    lines.append(f"//   - {col['name']}")
                lines.append("")
            return "\n".join(lines)

        predef_example_str = dict_to_json_with_comments(example_predef, tables_parsed)
        colmap_example_str = dict_to_json_with_comments(example_colmap, tables_parsed)
        numrows_example_str = json.dumps(example_numrows, indent=2)

        st.subheader("`predefined_values` (JSON)")
        predefined_values_str = st.text_area(
            "Define `predefined_values` as JSON",
            value=predef_example_str,
            height=250
        )

        st.subheader("`column_type_mappings` (JSON)")
        column_type_mappings_str = st.text_area(
            "Define `column_type_mappings` as JSON",
            value=colmap_example_str,
            height=250
        )

        st.subheader("`num_rows_per_table` (JSON)")
        num_rows_per_table_str = st.text_area(
            "Define `num_rows_per_table` as JSON",
            value=numrows_example_str,
            height=150
        )

        st.subheader("Global Number of Rows (Fallback)")
        global_num_rows = st.number_input(
            "num_rows (used if a table is not specified above)",
            min_value=1,
            value=10
        )

        # ----------------------------------------------------------------
        # STEP 3: GENERATE DATA
        # ----------------------------------------------------------------
        if st.button("Generate Data"):
            try:
                # Parse each JSON config
                try:
                    predefined_values = json.loads(predefined_values_str)
                except Exception as ex:
                    st.error(f"Invalid JSON in predefined_values: {ex}")
                    return

                try:
                    column_type_mappings = json.loads(column_type_mappings_str)
                except Exception as ex:
                    st.error(f"Invalid JSON in column_type_mappings: {ex}")
                    return

                try:
                    num_rows_per_table = json.loads(num_rows_per_table_str)
                except Exception as ex:
                    st.error(f"Invalid JSON in num_rows_per_table: {ex}")
                    return

                data_generator = DataGenerator(
                    tables=tables_parsed,
                    num_rows=global_num_rows,
                    predefined_values=predefined_values,
                    column_type_mappings=column_type_mappings,
                    num_rows_per_table=num_rows_per_table
                )

                # Generate data
                fake_data = data_generator.generate_data()

                st.success("Fake data generated successfully!")
                st.write("**Preview of generated data (Python dict):**")
                st.json(fake_data)

                # Prepare the SQL
                sql_insert = data_generator.export_as_sql_insert_query()

                # Download button
                st.download_button(
                    label="Download SQL Insert Queries",
                    data=sql_insert,
                    file_name="fake_data.sql",
                    mime="text/plain"
                )

            except Exception as e:
                st.error(f"Error generating data: {e}")


if __name__ == "__main__":
    main()