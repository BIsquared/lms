from fasthtml.common import *
import pandas as pd
from io import BytesIO


app, rt, quizs, Quiz = fast_app(
    "data/quiz.db",
    live=True,
    id=int,
    question=str,
    a=str,
    b=str,
    c=str,
    d=str,
    answers=str,
    tag=str,
    pk="id",
)


@rt("/")
def get():
    return Titled("Quiz", A("Upload Excel", href="/upload"))


@rt("/upload")
def get():
    group = Group(
        Input(
            type="file",
            name="file",
            accept=".xlsx",  # This restict user to upload only excel file with .xlsx extension
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


def standardize_columns(column_name):
    cleaned_columns = column_name.strip().lower()
    # Replace consecutive spaces with a single underscore
    return re.sub(r"\s+", "_", cleaned_columns)


def convert_binary_to_df(file_content):
    # Create a BytesIO object to read it as excel
    excel_data = BytesIO(file_content)
    df = pd.read_excel(excel_data, dtype=object)
    df.columns = [standardize_columns(col) for col in df.columns]
    # If there is no answer then the default answer is 'A'
    df.answers = df.answers.fillna("A") 
    # Convert null values to empty strings for storing in DB
    df = df.fillna("")
    return df


@rt("/upload")
async def post(file: UploadFile):
    if not file.filename.endswith("xlsx"):  
        return "Invalid file type! - Only .xlsx files are allowed"
    file_content = await file.read()
    df = convert_binary_to_df(file_content)
    data = df.to_dict(
        orient="records"  # This will give each row as a dict value with column name as key
    )
    quizs.insert_all(data)
    return P("Successfully added to DB")


serve()
