import streamlit as st
import json
from config import sql_script as default_sql
from parsing import parse_create_tables
from filling import DataGenerator


def main():
    st.title("Data Filler Web UI")

    #
    # -----------------------------------------------------------
    # STEP 1: SQL Script Input
    # -----------------------------------------------------------
    st.markdown(
        """
        **Step 1**: Paste or modify your **SQL CREATE script** below, then click
        **Parse SQL**. Once it’s successfully parsed, additional configuration steps will appear.
        """
    )
    if "tables_parsed" not in st.session_state:
        st.session_state["tables_parsed"] = None

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

    #
    # -----------------------------------------------------------
    # STEP 2: Show subsequent configs only if we have parsed tables
    # -----------------------------------------------------------
    if st.session_state["tables_parsed"] is not None:
        tables_parsed = st.session_state["tables_parsed"]

        st.markdown("### Parsed Tables")
        st.json(tables_parsed)

        # Extended explanation of each configuration section
        st.markdown(
            """
            ---
            **Step 2**: Provide your configuration for:

            1. **`predefined_values`**  
               A dictionary that can specify global or per-table/per-column fixed choices.
               You can set arrays of possible values. For example:

               ```
               {
                 "global": {
                   "sex": ["M", "F"]
                 },
                 "Categories": {
                   "category_name": [
                     "Fiction", "Non-fiction", "Science"
                   ]
                 }
               }
               ```
               - **`global`** applies to **every** table or column if it matches.  
               - Table-specific keys apply only to that table’s columns.

            2. **`column_type_mappings`**  
               A dictionary that can specify how each column should be filled. You can use:
               - A **string** with a Faker method name (e.g. `"email"`, `"last_name"`)
               - A **lambda** (like `"lambda fake, row: fake.date_of_birth()"`)
               - A custom logic string recognized by your code.

               **Example**:
               ```
               {
                 "global": {
                   "first_name": "first_name",
                   "last_name": "last_name",
                   "email": "email"
                 },
                 "Authors": {
                   "birth_date": "date_of_birth"
                 }
               }
               ```

            3. **`num_rows_per_table`**  
               A dictionary specifying how many rows to generate **per table**.  
               **Example**:
               ```
               {
                 "Categories": 10,
                 "Members": 20,
                 "Books": 200
               }
               ```

            4. **Global `num_rows`**  
               A fallback value used if a table is *not* listed in `num_rows_per_table`.
               For example, if `Books` is not in `num_rows_per_table`, we use `num_rows`.
            ---
            """
        )

        # Prepare placeholder JSON examples without inline comments
        example_predef = {
            "global": {
                "sex": ["M", "F"]
            }
        }
        example_colmap = {
            "global": {
                "first_name": "first_name",
                "last_name": "last_name",
                "email": "email"
            }
        }
        example_numrows = {}

        # Add empty placeholders for each discovered table
        for tbl_name, tbl_def in tables_parsed.items():
            example_predef[tbl_name] = {}
            example_colmap[tbl_name] = {}
            example_numrows[tbl_name] = 10

        # Convert each dictionary to a clean JSON string (no comments)
        predef_example_str = json.dumps(example_predef, indent=2)
        colmap_example_str = json.dumps(example_colmap, indent=2)
        numrows_example_str = json.dumps(example_numrows, indent=2)

        # Now the actual text areas where user edits final JSON
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

        # A final fallback for any unspecified table
        st.subheader("Global Number of Rows (Fallback)")
        global_num_rows = st.number_input(
            "num_rows (used if a table is not specified above)",
            min_value=1,
            value=10
        )

        #
        # -----------------------------------------------------------
        # STEP 3: GENERATE DATA
        # -----------------------------------------------------------
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

                # Initialize DataGenerator
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
