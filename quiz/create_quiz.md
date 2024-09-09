# Teacher creates Quiz by uploading an Excel file. 

## User Story
As a teacher,
I want to upload an Excel file containing multiple-choice quiz questions and answers,
So that I can quickly create a new quiz without manual entry.

## Excel File format
Columns:
1. Subject - Fill down, if necessary so that only the first value is specified
2. Topic - Fill down
3. Question Type (e.g., Multiple Choice) - default is blank = MCQ
4. Answer Count (1 or more - default is blank = 1 answer)
5. Question
6. Answer 1 to 4 as standard, but can be less or more
7. Tag 1 or more 

Scenario: Teacher uploads a valid Excel file
    Given I am on the quiz creation page
    When I select and upload the Excel file
    Then the app should validate the file format and content
    And a new quiz should be automatically created with the questions from the Excel file
    And I should be able to view all the quiz questions and their answer options