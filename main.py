from fasthtml.common import *
import pandas as pd
from io import BytesIO
import tempfile
import xlwings as xw


def render(quizzes):
    return Tr(
        Td(quizzes.question),
        Td(quizzes.a),
        Td(quizzes.b),
        Td(quizzes.c),
        Td(quizzes.d),
        Td(quizzes.answers),
        Td(quizzes.tag),
    )


custom_css = Style(
    """
    .freeze-header{
    position: sticky;
    top: 0;
      }
    """
)


app, route, quizzes, Quiz = fast_app(
    "data/quiz.db",
    live=True,
    render=render,
    id=int,
    question=str,
    a=str,
    b=str,
    c=str,
    d=str,
    answers=str,
    tag=str,
    pk="id",
    hdrs=[custom_css],
)

column_names = ["Question", "A", "B", "C", "D", "Answer", "Tag"]


@route("/")
def get():
    return Titled(
        "Quiz",
        A("Upload Excel", href="/upload"),
        " | ",
        A("All Questions", href="/questions"),
    )


@route("/upload")
def get():
    group = Group(
        Input(
            type="file",
            name="file",
            accept=".xlsx",
            required="true",
        ),
        Button("Upload"),
    )
    form = Form(
        group,
        hx_post="/upload",
        target_id="main",
        enctype="multipart/form-data",  # multipart/form-data is required for file upload
    )
    return Title("LMS"), Container(form, Div(id="main"))


def standardize_column(column_name):
    cleaned_column = column_name.strip().lower()
    # Replace consecutive spaces with a single underscore
    return re.sub(r"\s+", "_", cleaned_column)


def convert_binary_to_df(file_content):
    # Create a BytesIO object to read it as excel
    excel_data = BytesIO(file_content)
    df = pd.read_excel(excel_data, dtype=object)
    df.columns = [standardize_column(col) for col in df.columns]
    # If there is no answer then the default answer is 'A'
    df.answers = df.answers.fillna("A")
    return df


@route("/upload")
async def post(file: UploadFile):
    if not file.filename.endswith("xlsx"):
        return "Invalid file type! - Only .xlsx files are allowed"
    file_content = await file.read()
    df = convert_binary_to_df(file_content)
    # To easily insert all the data into db we need to convert it to list of dict
    data = df.to_dict(
        orient="records"  # This will give each row as a dict value with column name as key
    )
    # For testing purposes we are deleting all the data from db before inserting new data
    quizzes.insert_all(data, truncate=True)
    return (
        P("Successfully added"),
        # It will redirect to '/questions' after 1 sec
        Meta(http_equiv="refresh", content="1; url=/questions"),
    )


@route("/questions")
def get():
    table = Table(
        Thead(Tr(map(Th, column_names)), cls="freeze-header"),
        Tbody(*quizzes()),
        cls="striped",
    )
    export_button = A(Button("Export"), href="/download")
    return Container(table, export_button)


@route("/download")
def get():
    df = pd.DataFrame(quizzes()).drop("id", axis=1).rename(columns=str.capitalize)
    # Create a temporary directory to store the Excel file becasue xlwings doesn't support direct streaming
    temp_dir = tempfile.mkdtemp()
    temp_file_path = os.path.join(temp_dir, "quiz_data.xlsx")
    try:
        with xw.Book() as workbook:
            sheet = workbook.sheets.active
            starting_cell = sheet.range("A1")
            starting_cell.options(index=False).value = df
            table_range = starting_cell.expand("table")
            table = sheet.tables.add(table_range, name="Quiz_table")
            table.range.column_width = 35
            table.range.api.WrapText = True

            workbook.save(temp_file_path)
        # For streaming we need to read the file content into a BytesIO object
        with open(temp_file_path, "rb") as file_content:
            output = BytesIO(file_content.read())
    finally:
        os.remove(temp_file_path)
        os.rmdir(temp_dir)

    headers = {
        "Content-Disposition": "attachment; filename=quiz_data.xlsx",
        "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # This is to tell the browser that this is an excel file
    }
    return StreamingResponse(output, headers=headers)


serve()
