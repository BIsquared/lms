from fasthtml.common import *
import openpyxl
import pandas as pd
from io import BytesIO


# Check if the answer is correct or not.
def is_answer(answers, column_name):
    return True if column_name in answers else False


def render(quizs):
    qid = f"q-{quizs.id}"
    answers = quizs.answers
    edit_link = A("✏️", hx_get=f"/edit/{quizs.id}", hx_replace_url="true", target_id="main")
    delete_link = A("❌", hx_delete=f"/{quizs.id}", target_id=qid, hx_swap="outerHTML")
    return Tr(
        Td(quizs.tag),
        Td(quizs.question),
        Td(Strong(quizs.a) if is_answer(answers, "A") else quizs.a),
        Td(Strong(quizs.b) if is_answer(answers, "B") else quizs.b),
        Td(Strong(quizs.c) if is_answer(answers, "C") else quizs.c),
        Td(Strong(quizs.d) if is_answer(answers, "D") else quizs.d),
        Td(quizs.answers),
        Td(edit_link, " | ", delete_link),
        id=qid,
    )


column_names = ["Tag", "Question", "A", "B", "C", "D", "Answers", "Manage"]


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


question_redirect = RedirectResponse(
    "/questions", status_code=303
)  # To redirect to the questions page even if the method is not GET


# Standardize the column names
def clean_column_name(column_name):
    # Strip leading and trailing whitespace
    cleaned = column_name.strip()
    # Replace consecutive spaces with a single underscore
    cleaned = re.sub(r"\s+", "_", cleaned)
    # Convert to lowercase
    cleaned = cleaned.lower()
    return cleaned


# Convert the binary to a pandas dataframe
def convert_binary_to_df(file_content):
    data = BytesIO(file_content)  # Reading the binary data in memory
    df = pd.read_excel(data, dtype=object)
    # Standardize the column names
    df.columns = [clean_column_name(col) for col in df.columns]
    df.answers = df.answers.fillna("A")
    # Convert the na values to empty strings to store in DB.
    df = df.fillna("")
    return df


# Uploading the data to the database
def insert_data(df):
    lst = df.to_dict(orient="records")
    quizs.insert_all(lst, truncate=True)


# Main page
@rt("/")
def get():
    grp = Group(Input(type="file", name="file", required="true"), Button("Upload"))
    frm = Form(
        grp,
        id="upload-form",
        hx_post="/upload",
        target_id="main",
        hx_replace_url="true",
        enctype="multipart/form-data",  # multipart/form-data is required for file upload
    )
    all_ques_btn = Button("All Questions", hx_get="/questions", hx_replace_url="true", target_id="main") 
    return Container(frm, all_ques_btn, id="main")


# To upload the Excel file
@rt("/upload")
async def post(file: UploadFile):
    if not file.filename.endswith("xlsx"):
        return "Invalid file type!"
    file_content = await file.read()
    df = convert_binary_to_df(file_content)
    insert_data(df)
    return question_redirect


# Display all the questions as a table
@rt("/questions")
def get():
    table = Table(Thead(Tr(map(Th, column_names))), Tbody(*quizs()), cls="striped") if quizs() else P("No data")
    upload_btn = Button("Upload", hx_get="/", hx_replace_url="true", target_id="main")
    download_btn = A(Button("Export"), href="/download")
    ctn = (table, upload_btn, " ", download_btn)
    return Container(*ctn, id="main")

# Delete a question from the database
@rt("/{id}")
def delete(id: int):
    quizs.delete(id)


# Edit Page for each question
@rt("/edit/{id}")
def get(id: int):
    quiz = quizs.get(id)
    hdr = Div(
        Label("Tag", Input(type="text", id="tag", value=quiz.tag)),
        Label("Question", Textarea(quiz.question, type="text", id="question")),
        Hidden(id="id", value=quiz.id),
    )
    body = [
        Group(
            CheckboxX(is_answer(quiz.answers, "A"), id="A"), Input(id="a", value=quiz.a)
        ),
        Group(
            CheckboxX(is_answer(quiz.answers, "B"), id="B"), Input(id="b", value=quiz.b)
        ),
        Group(
            CheckboxX(is_answer(quiz.answers, "C"), id="C"), Input(id="c", value=quiz.c)
        ),
        Group(
            CheckboxX(is_answer(quiz.answers, "D"), id="D"), Input(id="d", value=quiz.d)
        ),
    ]
    ftr = Div(
        Button("Update", hx_post=f"/update", hx_replace_url="true", target_id="main"),
        " ",
        Button("Cancel", hx_get=f"/questions", hx_replace_url="true", target_id="main"),
    )
    return Container(
        Form(
            Card(*body, header=hdr, footer=ftr, id="edit-form"),
            hx_post=f"/update/{id}",
        ),
        id="main",
    )


# class to handle the checkboxes
@dataclass
class Options:
    A: bool
    B: bool
    C: bool
    D: bool


# Update the question
@rt("/update")
def post(option: Options, quiz: Quiz):
    answers = "".join(
        letter for letter, value in option.__dict__.items() if value
    )  # concating the correct options
    if answers:
        quiz.answers = answers
    else:
        quiz.answers = "A"
    quizs.update(quiz)
    return question_redirect


# Handeling the Excel Export.
@app.get("/download")
async def download_excel():
    # Create DataFrame and remove 'id' column
    try:
        df = pd.DataFrame(quizs()).drop("id", axis=1)
        df.columns = column_names[:-1]
    except KeyError:
        return RedirectResponse("/")
    # Create Excel file in memory
    output = BytesIO()
    with pd.ExcelWriter(output) as writer:
        df.to_excel(writer, index=False)

    # Prepare download headers
    headers = {"Content-Disposition": 'attachment; filename="quiz_data.xlsx"'}
    # Return Excel file as downloadable response
    return Response(
        output.getvalue(),
        headers=headers,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


serve()
