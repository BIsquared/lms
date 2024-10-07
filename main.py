from fasthtml.common import *
import pandas as pd

app, rt = fast_app(live=True)

@rt('/')
def get():
    return Titled("Quiz"), A("Upload Excel", href="/upload")

@rt("/upload")
def get():
    group = Group(Input(type="file", name="file", required="true"), Button("Upload"))
    form = Form(
        group,
        hx_post="/upload",
        target_id="main",
        enctype="multipart/form-data",  # multipart/form-data is required for file upload
    )
    return Title("LMS"), Container(form, Div(id="main"))

@rt("/upload")
def post(file: UploadFile): 
    # TODO - File structure is assumed as of now. Hence we are NOT validating it
    return "File uploaded successfully!"

serve()
