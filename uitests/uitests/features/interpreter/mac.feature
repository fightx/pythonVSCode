@mac
Feature: Mac Interpreter

    Scenario: Select an invalid interpreter
        When I select the default mac Interpreter
        Then a message with the text "You have selected the macOS system install of Python, which is not recommended for use with the Python extension. Some functionality will be limited, please select a different interpreter." is displayed
