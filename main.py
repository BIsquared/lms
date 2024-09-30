from fasthtml.common import *
from fh_bootstrap import *
import pandas as pd
import io


def is_answer(answers, column_name):
    # Check if the column name contains "answer"
    return True if column_name in answers else False


def render(quizs):
    answers = quizs.answers.lower()
    edit_link = A("Edit", hx_get=f"/edit/{quizs.id}", target_id="main")
    return Tr(
        Td(quizs.tag),
        Td(quizs.question),
        Td(Strong(quizs.a) if is_answer(answers, "a") else quizs.a),
        Td(Strong(quizs.b) if is_answer(answers, "b") else quizs.b),
        Td(Strong(quizs.c) if is_answer(answers, "c") else quizs.c),
        Td(Strong(quizs.d) if is_answer(answers, "d") else quizs.d),
        Td(quizs.answers),
        Td(edit_link),
    )


column_names = ["Tag", "Question", "A", "B", "C", "D", "Answers", "Edit"]

app, rt, quizs, Quiz = fast_app(
    "data/quiz.db",
    live=True,
    render=render,
    id=int,
    tag=str,
    question=str,
    a=str,
    b=str,
    c=str,
    d=str,
    answers=str,
    pk="id",
)


def clean_column_name(column_name):
    # Strip leading and trailing whitespace
    cleaned = column_name.strip()
    # Replace consecutive spaces with a single underscore
    cleaned = re.sub(r"\s+", "_", cleaned)
    # Convert to lowercase
    cleaned = cleaned.lower()
    return cleaned


def convert_binary_to_df(file_content):
    data = io.BytesIO(file_content)  # convert the binary to excel data
    df = pd.read_excel(data, dtype=object)
    # Standardize the column names
    df.columns = [clean_column_name(col) for col in df.columns]
    df.answers = df.answers.str.lower().fillna("a")
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
        target_id="main",
        enctype="multipart/form-data",  # multipart/form-data is required for file upload
    )
    all_ques_btn = Button("All Questions", hx_get="/questions", target_id="main")
    return Titled("Upload File", frm, all_ques_btn, id="main")


def display_table():
    table = Table(Thead(Tr(map(Th, column_names))), Tbody(*quizs()), cls="striped")
    return Titled("Questions", table, id="main")


@rt("/upload")
async def post(file: UploadFile):
    if not file.filename.endswith("xlsx"):
        return "Invalid file type!"
    file_content = await file.read()
    df = convert_binary_to_df(file_content)
    insert_data(df)
    return display_table()


@rt("/questions")
def get():
    return display_table()


@rt("/edit/{id}")
def get(id: int):
    quiz = quizs.get(id)
    hdr = Div(
        Label("Question"),
        Input(type="text", id="question", value=quiz.question),
    )
    ftr = Div(
        Button("Update", hx_post=f"/update/{id}", target_id="edit-form"),
        " ",
        Button("Cancel", hx_get=f"/questions", target_id="main"),
    )
    return Titled(
        "Edit",
        Form(
            Card( header=hdr, footer=ftr, id="edit-form"),
            # hx_post=f"/update/{id}",
        ),
    )


serve()
