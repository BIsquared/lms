from fasthtml.common import *
import openpyxl  # Additional Plugin for pandas to read Excel
import pandas as pd
from io import BytesIO
import tempfile
import xlwings as xw

selected_questions_id = []


def render_row(questions):
    return Tr(
        Td(
            Form(
                A(
                    "✅" if questions.id in selected_questions_id else "⬜",
                    hx_post="/select_question",
                ),
                Hidden(id="question_id", value=questions.id),
            )
        ),
        Td(questions.question),
        Td(questions.a),
        Td(questions.b),
        Td(questions.c),
        Td(questions.d),
        Td(questions.answers),
        Td(questions.tag),
    )


custom_css = Style(
    """
    .freeze-header{
    position: sticky;
    top: 0;
      }
    .freeze-btn{
    position: sticky;
    bottom: 10px;
    margin-left: 10px;
    }
    """
)

tables_schema = {
    "questions": {  # This question table has the all uploaded question with answers
        "id": int,
        "question": str,
        "a": str,
        "b": str,
        "c": str,
        "d": str,
        "answers": str,
        "tag": str,
        "pk": "id",
    },
    "quizzes": {  # This quizzess table is master table for the quiz_questions table
        "id": int,
        "quiz_name": str,
        "pk": "id",
    },
    "quiz_questions": {  # This table is for the mapping of quiz and questions
        "id": int,
        "quiz_id": int,  # Foreign key linking to quizzes
        "question_id": int,  # Foreign key linking to questions
        "pk": "id",
    },
}


app, route, questions_table, quizzes_table, quiz_questions_table = fast_app(
    "data/quiz.db",
    live=True,
    tbls=tables_schema,
    hdrs=[custom_css],
)

# Unpacking the table_object and dataclass
questions, Questions = questions_table
quizzes, Quizzes = quizzes_table
quiz_questions, QuizQuestions = quiz_questions_table

column_names = ["Select", "Question", "A", "B", "C", "D", "Answer", "Tag"]


@route("/")
def get():
    return Titled(
        "Quiz",
        A("Upload Excel", href="/upload"),
        " | ",
        A("All Questions", href="/questions"),
        " | ",
        A("All Quizzes", href="/all_quizzes"),
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
    questions.insert_all(data, truncate=True)
    return (
        P("Successfully added"),
        # It will redirect to '/questions' after 1 sec
        Meta(http_equiv="refresh", content="1; url=/questions"),
    )


@route("/questions")
def get():
    table = Table(
        Thead(Tr(map(Th, column_names)), cls="freeze-header"),
        Tbody(map(render_row, questions())),
        cls="striped",
    )
    export_button = A(Button("Export"), href="/download")
    preview_button = A(Button("Preview"), href="/preview_questions")
    buttons = Div(export_button, " ", preview_button, cls="freeze-btn")
    return Container(table), buttons


def render_question(questions):
    return Li(questions["question"])


def get_preview_questions(questions_id: list):
    if not questions_id:
        # vars is used to convert object to dict
        # because the else block returns list of dicts hence we standardized
        selected_quiz_questions = map(vars, questions())
    else:
        # Created a query to get all the selected questions like, 'id IN (1, 2)'
        query = "id IN ({}) ".format(", ".join(map(str, questions_id)))
        selected_quiz_questions = list(questions.rows_where(where=query))
    preview_questions = Div(
        H4("Questions"),
        Ol(
            map(
                render_question,
                selected_quiz_questions,
            )
        ),
    )
    return preview_questions


@route("/preview_questions")
def get():
    quiz_name_input = Input(
        placeholder="Enter Quiz Name", id="quiz_name", required=True
    )
    form = Form(
        Group(quiz_name_input, Button("Submit")),
        method="POST",
        action="/create_quiz",
    )
    back_to_select = A(Button("Back to select"), href="/questions")
    card = Card(
        get_preview_questions(selected_questions_id), header=form, footer=back_to_select
    )
    return Titled("Create Quiz", card)


def get_quiz_questions_id(quiz_id: int):
    query = f"quiz_id = {quiz_id}"
    return [row["question_id"] for row in quiz_questions.rows_where(where=query)]


@route("/preview_quiz/{quiz_id}")
def get(quiz_id: int):
    quiz_name = quizzes.get(quiz_id).quiz_name
    quiz_questions_id = get_quiz_questions_id(quiz_id)
    preview_questions = get_preview_questions(quiz_questions_id)
    back_button = A(Button("Back"), href="/all_quizzes")
    card = Card(
        preview_questions,
        footer=back_button,
    )
    return Title("Quiz Preview"), Container("Quiz Name", H1(quiz_name), card)


@route("/create_quiz")
def post(quiz_name: Quizzes):  # type:ignore
    global selected_questions_id
    quiz_data = quizzes.insert(quiz_name)
    for question_id in selected_questions_id:
        quiz_questions.insert(quiz_id=quiz_data.id, question_id=question_id)

    # Clear the selected questions after creating the quiz
    selected_questions_id = []
    return (
        P("Successfully Created Quiz"),
        # It will redirect to '/questions' after 1 sec
        Meta(http_equiv="refresh", content="1; url=/all_quizzes"),
    )


def render_quiz_name(quiz):
    question_count = len(get_quiz_questions_id(quiz.id))
    return Tr(
        Td(quiz.quiz_name),
        Td(question_count),
        Td(A("Show", href=f"/preview_quiz/{quiz.id}")),
    )


@route("/all_quizzes")
def get():
    all_quizzes = map(render_quiz_name, quizzes())
    table = Table(
        Thead(Tr(Th("Quiz Name"), Th("Total Quetions"), Th("Preview"))),
        Tbody(*all_quizzes),
    )
    return Titled("All Quizzes", table)


@route("/select_question")
def post(question_id: int):
    if question_id in selected_questions_id:
        selected_questions_id.remove(question_id)
        return "⬜"
    else:
        selected_questions_id.append(question_id)
        return "✅"


@route("/download")
def get():
    df = pd.DataFrame(questions()).drop("id", axis=1).rename(columns=str.capitalize)
    # Create a temporary directory to store the Excel file becasue xlwings doesn't support direct streaming
    temp_dir = tempfile.mkdtemp()
    temp_file_path = os.path.join(temp_dir, "quiz_data.xlsx")
    try:
        with xw.App(visible=False) as app:
            workbook = app.books.add()
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
