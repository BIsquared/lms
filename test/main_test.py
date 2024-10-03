from playwright.sync_api import Page, expect
import pandas as pd
import os

upload_file_path = r"D:\Projects\lms\data\dummy_data.xlsx"    

def test_file_upload_and_display(page: Page) -> None:
    page.goto("http://localhost:5001/")
    
    page.get_by_role("textbox").set_input_files(upload_file_path)

    page.get_by_role("button", name="Upload").click(timeout=2000)

    # to ensure the table is visible
    data_table = page.locator('table:has-text("")')
    expect(data_table).to_be_visible()

    # To ensure the excel is displayed correctly
    first_cell = page.get_by_role("cell", name="Sorting is applied to the New")
    expect(first_cell).to_have_text("Sorting is applied to the New Query")

    second_cell = page.get_by_role("cell", name="Remove Duplicates on all")
    expect(second_cell).to_have_text("Remove Duplicates on all columns")

    third_cell = page.get_by_role("cell", name="Which of these questions are")
    expect(third_cell).to_have_text("Which of these questions are associated with the transaction tables?")

def test_file_export_and_verify(page: Page) -> None:
    page.goto("http://localhost:5001/questions")

    # Download the file
    with page.expect_download() as download_info:
        page.get_by_role("button", name="Export").click()
    download = download_info.value
    
    # Ensure the download is complete
    download_path = download.suggested_filename
    download.save_as(download_path)

    # Read and verify the downloaded file
    try:
        original_df = pd.read_excel(upload_file_path)
        downloaded_df = pd.read_excel(download_path)
        
        # Compare the dataframes
        assert original_df.equals(downloaded_df)
    finally:
        # Clean up: remove the downloaded file
        if os.path.exists(download_path):
            os.remove(download_path)
