from fasthtml.common import *
import pandas as pd

app, rt = fast_app(live=True)

@rt('/')
def get():
    return Titled("Quiz")

serve()
