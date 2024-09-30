from fasthtml.common import *
from fh_bootstrap import *
import pandas as pd
import io

def answer_highlight(answers, column_name, value):
    # Check if the column name contains "answer"
    return Strong(value) if column_name in answers else value

def render(quizs):
    answers = quizs.answers.lower()

    return Tr(
            Td(quizs.tag),
            Td(quizs.question),
            Td(answer_highlight(answers, "a", quizs.a)),
            Td(answer_highlight(answers, "b", quizs.b)),
            Td(answer_highlight(answers, "c", quizs.c)),
            Td(answer_highlight(answers, "d", quizs.d)),
            Td(quizs.answers),
        )

column_names = ["Tag", "Question", "A", "B", "C", "D", "Answers"]

app, rt, quizs, Quiz = fast_app("data/quiz.db", live=True, render=render, 
                   id=int, tag=str, question=str, a=str, b=str, c=str, d=str, answers=str, pk='id')


def clean_column_name(column_name):
    # Strip leading and trailing whitespace
    cleaned = column_name.strip()
    # Replace consecutive spaces with a single underscore
    cleaned = re.sub(r"\s+", "_", cleaned)
    # Convert to lowercase
    cleaned = cleaned.lower()
    return cleaned


def convert_binary_to_df(file_content):
    data = io.BytesIO(file_content) # convert the binary to excel data
    df = pd.read_excel(data, dtype=object)
    # Standardize the column names
    df.columns = [clean_column_name(col) for col in df.columns]
    df.answers = df.answers.fillna("A")
    # Convert the na values to empty strings to store in DB.
    df = df.fillna("")
    # print(df)
    return df

def insert_data(df):
    lst = df.to_dict(orient="records")
    for row in lst:
        # print(Quiz(row))
        quizs.insert(Quiz(**row))

@rt("/")
def get():
    grp = Group(Input(type="file", name="file", required="true"), Button("Upload"))
    frm = Form(
        grp,
        id="upload-form",
        hx_post="/upload",
        target_id="response",
        enctype="multipart/form-data", # multipart/form-data is required for file upload
    )
    return Titled("Upload File", frm, id="response")


@rt("/upload")
async def post(file: UploadFile):
    if not file.filename.endswith("xlsx"):
        return "Invalid file type!"
    file_content = await file.read()
    df = convert_binary_to_df(file_content)
    insert_data(df)
    table = Table(Thead(Tr(map(Th, column_names))),Tbody(*quizs()), cls="striped")
    return Titled("Questions", table)


serve()
