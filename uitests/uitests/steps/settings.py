# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.


import behave
import uitests.vscode.settings


@behave.given('the workspace setting "{name}" has the value "{value}"')
def given_workspace_setting(context, name, value):
    uitests.vscode.settings.update_workspace_settings(context, {name: value})


@behave.given('the workspace setting "{name}" is enabled')
def given_workspace_setting_enabled(context, name):
    uitests.vscode.settings.update_workspace_settings(context, {name: True})


@behave.given('the workspace setting "{name}" is disabled')
def given_workspace_setting_disabled(context, name):
    uitests.vscode.settings.update_workspace_settings(context, {name: False})


@behave.when('I update the workspace setting "{name}" with the value "{value}"')
def given_workspace_setting_value(context, name, value):
    uitests.vscode.settings.update_workspace_settings(context, {name: value})


@behave.when('I enable the workspace setting "{name}"')
def when_workspace_setting_enable(context, name):
    uitests.vscode.settings.update_workspace_settings(context, {name: True})


@behave.when('I disable the workspace setting "{name}"')
def when_workspace_setting_disable(context, name):
    uitests.vscode.settings.update_workspace_settings(context, {name: False})


@behave.given('the workspace setting "{name}" does not exist')
def given_workspace_setting_is_removed(context, name):
    uitests.vscode.settings.remove_workspace_setting(context, name)


@behave.when('I remove the workspace setting "{name}"')
def when_workspace_setting_is_removed(context, name):
    uitests.vscode.settings.remove_workspace_setting(context, name)


@behave.then('the workspace setting "{name}" is enabled')
def then_workspace_setting_enabled(context, name):
    assert uitests.vscode.settings.get_setting(context, name) is True


@behave.then('the workspace setting "{name}" is disabled')
def then_workspace_setting_disabled(context, name):
    assert uitests.vscode.settings.get_setting(context, name) is False


@behave.then('the workspace setting "{name}" is "{value}"')
def then_workspace_setting_value(context, name, value):
    assert uitests.vscode.settings.get_setting(context, name) == value


@behave.then('the workspace setting "{name}" contains the value "{value}"')
def then_workspace_setting_contains_value(context, name, value):
    assert value in uitests.vscode.settings.get_setting(context, name)
