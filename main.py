from fasthtml.common import *
import openpyxl  # Additional Plugin for pandas to read Excel
import pandas as pd
from io import BytesIO
import tempfile
import xlwings as xw
import sqlite3

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
    "student": {
        "student_id": int,
        "username": str,
        "pk": "student_id",
    },
    "student_quiz_result": {
        "id": int,
        "student_id": int,
        "quiz_id": int,
        "completed": bool,
        "score": str,
        "pk": "id",
    },
    "student_quiz_response": {
        "id": int,
        "student_quiz_id": int,  # Foreign key linking to student_quiz_result Table
        "question_id": int,
        "selected_option": str,
        "pk": "id",
    },
}

# Redirect response for unauthenticated users
login_redir = RedirectResponse("/student/login", status_code=303)


# Beforeware to check authentication
def before(request, session):
    # Get authentication from session
    auth = request.scope["auth"] = session.get("auth", None)
    if not auth:
        return login_redir


bware = Beforeware(
    before,
    skip=[
        r"/favicon\.ico",
        r"/static/.*",
        r".*\.css",
        r"^/(?!.*student).*$|/student/(login|auth)",  # this will exclude any path that contains "student" in the endpoint except student login and auth pages
    ],
)

(
    app,
    route,
    questions_table,
    quizzes_table,
    quiz_questions_table,
    students_table,
    student_quiz_result_table,
    student_quiz_response_table,
) = fast_app(
    "data/quiz.db",
    live=True,
    tbls=tables_schema,
    hdrs=[custom_css],
    before=bware,
)


# Unpacking the table_object and dataclass
questions, Questions = questions_table
quizzes, Quizzes = quizzes_table
quiz_questions, QuizQuestions = quiz_questions_table
students, Students = students_table
student_quiz_result, StudentQuizResult = student_quiz_result_table
student_quiz_response, StudentQuizResponse = student_quiz_response_table

# To make the username unique
students.create_index(["username"], unique=True, if_not_exists=True)

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
        " | ",
        A("Student", href="/student/quiz"),
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


# Util function
def standardize_column(column_name):
    cleaned_column = column_name.strip().lower()
    # Replace consecutive spaces with a single underscore
    return re.sub(r"\s+", "_", cleaned_column)


# Util function
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


# Util function
def get_questions_by_question_ids(questions_id: list):
    if not questions_id:
        # vars is used to convert object to dict
        # because the else block returns list of dicts hence we standardized
        selected_quiz_questions = map(vars, questions())
    else:
        # Created a query to get all the selected questions like, 'id IN (1, 2)'
        query = "id IN ({}) ".format(", ".join(map(str, questions_id)))
        selected_quiz_questions = list(questions.rows_where(where=query))
    return selected_quiz_questions


def get_preview_questions(questions_id: list):
    selected_quiz_questions = get_questions_by_question_ids(questions_id)
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


# Util function
def get_question_ids_by_quiz_id(quiz_id: int):
    query = f"quiz_id = {quiz_id}"
    return [row["question_id"] for row in quiz_questions.rows_where(where=query)]


@route("/preview_quiz/{quiz_id}")
def get(quiz_id: int):
    quiz_name = quizzes.get(quiz_id).quiz_name
    quiz_questions_id = get_question_ids_by_quiz_id(quiz_id)
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


def render_quiz_details_for_teacher(quiz_data):
    question_count = len(get_question_ids_by_quiz_id(quiz_data.id))
    return Tr(
        Td(quiz_data.quiz_name),
        Td(question_count),
        Td(A("Show", href=f"/preview_quiz/{quiz_data.id}")),
    )


@route("/all_quizzes")
def get():
    all_quizzes = map(render_quiz_details_for_teacher, quizzes())
    table = Table(
        Thead(
            Tr(
                Th("Quiz Name"),
                Th("Total Questions"),
                Th("Preview"),
            )
        ),
        Tbody(*all_quizzes),
    )
    home_button = A(Button("Home"), href="/")
    container = Container(table, home_button)
    return Titled("All Quizzes", container)


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


## Student Pages ##


@route("/student/login")
def get():
    group = Group(
        Input(id="username", placeholder="Enter Username", required=True),
        Button("Login"),
    )
    form = Form(
        group,
        action="/student/auth",
        method="post",
    )
    return Titled("Student Login", form)


@route("/student/auth")
def post(student: Students, session):  # type: ignore
    username = student.username
    try:
        students.insert(student)
    except sqlite3.IntegrityError:
        # If the username already exists, do nothing
        pass
    except Exception as e:
        return P(e)
    session["auth"] = username
    return RedirectResponse("/student/quiz", status_code=303)


def render_quiz_details_for_student(quiz_data, student_id):
    quiz = quizzes.get(quiz_data.id)
    question_count = len(get_question_ids_by_quiz_id(quiz_data.id))

    try:
        student_quiz_details = get_student_quiz_id(student_id, quiz_data.id)[0]
    except IndexError:
        is_completed = False
    else:
        is_completed = student_quiz_details["completed"]

    if is_completed:
        action_button = A(
            "Result", href=f"/student/quiz/{student_quiz_details["id"]}/result"
        )
        score = student_quiz_details["score"]
    else:
        action_button = A("Take", href=f"/student/take_quiz/{quiz_data.id}")
        score = "-"

    return Tr(
        Td(quiz.quiz_name),
        Td(question_count),
        Td(score),
        Td(action_button),
    )


@route("/student/quiz")
def get(auth):
    header = Grid(
        H1(f"Welcome {auth}"),
        Div(A("logout", href="/student/logout"), style="text-align: right"),
    )
    student_id = get_student_id_by_name(auth)
    all_quizzes = map(
        lambda quiz: render_quiz_details_for_student(quiz, student_id), quizzes()
    )
    table = Table(
        Thead(
            Tr(
                Th("Quiz Name"),
                Th("Total Questions"),
                Th("Score"),
                Th("Action"),
            )
        ),
        Tbody(all_quizzes),
    )
    return Title(f"Student page"), Container(header, table)


def generate_navigation_button(button_name: str, url: str, cls_name=None):
    method = {"hx_post": url} if button_name == "Submit" else {"hx_get": url}
    return Button(
        button_name,
        **method,
        hx_replace_url="true",
        target_id="quiz_container",
        hx_swap="outerHTML",
        cls=cls_name,
    )


# Util function
def get_student_id_by_name(student_name: str):
    query = "username = ?"
    student = list(students.rows_where(query, [student_name]))
    return student[0]["student_id"]


# Util function
def get_student_quiz_id(student_id: int, quiz_id: int):
    data = list(
        student_quiz_result.rows_where(
            "student_id = ? AND quiz_id = ?", [student_id, quiz_id]
        )
    )
    return data


# Util function
def get_student_score_rows(student_quiz_id: int, question_id: int):
    data = list(
        student_quiz_response.rows_where(
            "student_quiz_id = ? AND question_id = ?", [student_quiz_id, question_id]
        )
    )
    return data


def preloading_student_score(quiz_id: int, student_name: str):
    student_id = get_student_id_by_name(student_name)
    # Check if the student has already started or submitted the quiz
    try:
        student_quiz_id = get_student_quiz_id(student_id, quiz_id)[0]
    except IndexError:
        student_quiz_id = student_quiz_result.insert(
            StudentQuizResult(student_id=student_id, quiz_id=quiz_id, completed=False)
        )
    else:
        return None
    # Prepopulate the student_score table for storing the selected answers
    questions_id = get_question_ids_by_quiz_id(quiz_id)
    for question_id in questions_id:
        data = StudentQuizResponse(
            student_quiz_id=student_quiz_id.id,
            question_id=question_id,
            selected_option="",
        )
        student_quiz_response.insert(data)


def get_anwser_by_question_id(question_id: int):
    return questions.get(question_id).answers


def render_quiz_question(quiz_id: int, question_no: int, student_name: str):
    current_quiz_question_ids = get_question_ids_by_quiz_id(quiz_id)
    quiz_questions = get_questions_by_question_ids(current_quiz_question_ids)
    # First question is at index 0 and question_no starts from 1
    question = quiz_questions[question_no - 1]
    header = H5(f"{question_no}) {question["question"]}")
    student_id = get_student_id_by_name(student_name)
    student_quiz_id = get_student_quiz_id(student_id, quiz_id)[0]["id"]
    score = get_student_score_rows(student_quiz_id, question["id"])
    score = score[0]
    answers = get_anwser_by_question_id(question["id"])
    print(score)
    # Create a radio button for the available options only
    # And preselect the option that the student has already selected for it to retain the selected option when navigating to the next question.
    options = [
        Label(
            Input(
                type="checkbox" if len(answers) > 1 else "radio",
                name="selected_option",
                value=option.upper(),
                checked=(True if option.upper() in score["selected_option"] else False),
            ),
            Span(question[option]),
        )
        for option in ["a", "b", "c", "d"]
        if question[option]
    ]
    form = Form(
        *options,
        Hidden(name="score_id", value=score["id"]),
        hx_post="/student/quiz/answer",
        hx_swap="none",
        hx_trigger="change",  # It will trigger the for every action in the checkbox or radio button
    )

    previous_button = generate_navigation_button(
        "Previous", url=f"/student/quiz/previous/{quiz_id}/question/{question_no}"
    )
    next_button = generate_navigation_button(
        "Next", url=f"/student/quiz/next/{quiz_id}/question/{question_no}"
    )
    submit_button = generate_navigation_button(
        "Submit",
        url=f"/student/quiz/submit/{student_quiz_id}",
        cls_name="contrast",
    )

    footer = Grid(
        previous_button if question_no > 1 else None,
        Div(
            submit_button if question_no == len(quiz_questions) else next_button,
            style="text-align: right",
        ),
    )
    return Card(form, header=header, footer=footer)


@route("/student/take_quiz/{quiz_id}")
def get(quiz_id: int, auth):
    preloading_student_score(quiz_id, student_name=auth)
    return RedirectResponse(f"/student/take_quiz/{quiz_id}/question/1", status_code=303)


@route("/student/quiz/answer")
async def post(score_id: int, req):  # type:ignore
    form_data = await req.form()
    del_values = form_data.getlist("selected_option")
    selected_option = "".join(del_values)

    score = student_quiz_response.get(score_id)
    score.selected_option = selected_option
    student_quiz_response.update(score)


@route("/student/quiz/next/{quiz_id}/question/{question_no}")
def get(quiz_id: int, question_no: int):
    return RedirectResponse(f"/student/take_quiz/{quiz_id}/question/{question_no + 1}")


@route("/student/quiz/previous/{quiz_id}/question/{question_no}")
def get(quiz_id: int, question_no: int):
    return RedirectResponse(f"/student/take_quiz/{quiz_id}/question/{question_no - 1}")


@route("/student/quiz/submit/{student_quiz_id}")
def post(student_quiz_id: int):
    # Calculate the total score
    total_score = 0
    quiz_questions_with_answers = evaluate_answers(student_quiz_id)
    for question in quiz_questions_with_answers:
        answer_length = len(question["answers"])
        for option in question["selected_option"]:
            if option in question["answers"]:
                score = 1 / answer_length
                total_score += score
    total_score = (
        int(total_score) if total_score.is_integer() else round(total_score, 1)
    )

    total_score_string = f"{total_score}/{len(quiz_questions_with_answers)}"
    # Update the student_quiz_result table
    student_quiz = student_quiz_result.get(student_quiz_id)
    student_quiz.score = total_score_string
    student_quiz.completed = True
    student_quiz_result.update(student_quiz)
    return RedirectResponse(f"/student/quiz/{student_quiz_id}/result", status_code=303)


@route("/student/quiz/{student_quiz_id}/result")
def get(student_quiz_id: int):
    student_quiz = student_quiz_result.get(student_quiz_id)
    quiz_name = quizzes.get(student_quiz.quiz_id).quiz_name
    header = f"Quiz: {quiz_name}"
    back_button = A(Button("Home"), href="/student/quiz")
    quiz_questions_with_answers = evaluate_answers(student_quiz_id)
    answers = []
    for i, question in enumerate(quiz_questions_with_answers, start=1):
        answers.append(render_quiz_result(question, i))
    return Titled(header, P(f"Score: {student_quiz.score}"), *answers, back_button)


def evaluate_answers(student_quiz_id: int):
    selected_options = list(
        student_quiz_response.rows_where("student_quiz_id = ?", [student_quiz_id])
    )
    quiz_questions_with_answers = []
    for question in selected_options:
        current_question = questions.get(question["question_id"]).__dict__
        current_question["student_quiz_id"] = question["student_quiz_id"]
        current_question["selected_option"] = question["selected_option"]
        quiz_questions_with_answers.append(current_question)
    return quiz_questions_with_answers


def render_quiz_result(question: dict, question_no: int):
    header = H5(f"{question_no}) {question['question']}")
    question_option = []
    for option in ["a", "b", "c", "d"]:
        if question[option]:
            is_invalid = "None"
            is_checked = None
            selected_option = question["selected_option"].lower()
            correct_answer = question["answers"].lower()
            if option in correct_answer:
                # set the correct answer as a green checkmark
                is_invalid = "false"
            if option in selected_option:
                is_checked = True
            if option in selected_option and not option in correct_answer:
                is_invalid = "true"

            question_option.append(
                Label(
                    Input(
                        type="checkbox",
                        aria_invalid=is_invalid,
                        checked=is_checked,
                        onClick="return false;",  # disable the checkbox without degrading the color
                    ),
                    question[option],
                )
            )
    card = Card(*question_option, header=header)
    return card


@route("/student/take_quiz/{quiz_id}/question/{question_no}")
def get(quiz_id: int, question_no: int, auth):
    current_quiz = quizzes.get(quiz_id)
    quiz_name = current_quiz.quiz_name
    current_question = render_quiz_question(quiz_id, question_no, student_name=auth)
    return Container(H3(f"Quiz: {quiz_name}"), current_question, id="quiz_container")


@route("/student/logout")
def get(sess):
    if "auth" in sess:
        del sess["auth"]
    return login_redir


serve()
