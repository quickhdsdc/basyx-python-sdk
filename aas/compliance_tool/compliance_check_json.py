# Copyright 2020 PyI40AAS Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
# specific language governing permissions and limitations under the License.
"""
Module which offers functions to use in a confirmation tool related to json files

check_schema: Checks if a json file is conform to official JSON schema as defined in the 'Details of the Asset
              Administration Shell' specification of Plattform Industrie 4.0

check_deserialization: Checks if a json file can be deserialized

check_aas_example: Checks if a json file consist the data of the example data defined in
                   aas.examples.data.example_aas.py

check_json_files_equivalence: Checks if two json files have the same data regardless of their order

All functions reports any issues using the given StateManager by adding new steps and associated LogRecords
"""
import json
import logging
from typing import Optional, Tuple

from .. import model
from ..adapter import aasx
from ..adapter.json import json_deserialization, JSON_SCHEMA_FILE
from ..examples.data import example_aas, create_example
from ..examples.data._helper import AASDataChecker
from .state_manager import ComplianceToolStateManager, Status


def check_schema(file_path: str, state_manager: ComplianceToolStateManager) -> None:
    """
    checks a given file against the official json schema and reports any issues using the given StateManager

    add the steps: 'Open file', 'Read file and check if it is conform to the json syntax' and 'Validate file against
    official json schema'

    :param file_path: path to the file which should be checked
    :param state_manager: manager to log the steps
    """
    logger = logging.getLogger('compliance_check')
    logger.addHandler(state_manager)
    logger.propagate = False
    logger.setLevel(logging.INFO)

    state_manager.add_step('Open file')
    try:
        # open given file
        file_to_be_checked = open(file_path, 'r', encoding='utf-8-sig')
    except IOError as error:
        state_manager.set_step_status(Status.FAILED)
        logger.error(error)
        state_manager.add_step('Read file and check if it is conform to the json syntax')
        state_manager.set_step_status(Status.NOT_EXECUTED)
        state_manager.add_step('Validate file against official json schema')
        state_manager.set_step_status(Status.NOT_EXECUTED)
        return
    try:
        with file_to_be_checked:
            state_manager.set_step_status(Status.SUCCESS)
            # read given file and check if it is conform to the json syntax
            state_manager.add_step('Read file and check if it is conform to the json syntax')
            json_to_be_checked = json.load(file_to_be_checked)
            state_manager.set_step_status(Status.SUCCESS)
    except json.decoder.JSONDecodeError as error:
        state_manager.set_step_status(Status.FAILED)
        logger.error(error)
        state_manager.add_step('Validate file against official json schema')
        state_manager.set_step_status(Status.NOT_EXECUTED)
        return

    # load json schema
    with open(JSON_SCHEMA_FILE, 'r', encoding='utf-8-sig') as json_file:
        aas_json_schema = json.load(json_file)
    state_manager.add_step('Validate file against official json schema')

    # validate given file against schema
    try:
        import jsonschema  # type: ignore
    except ImportError as error:
        state_manager.set_step_status(Status.NOT_EXECUTED)
        logger.error("Python package 'jsonschema' is required for validating the JSON file.", error)
        return

    try:
        jsonschema.validate(instance=json_to_be_checked, schema=aas_json_schema)
    except jsonschema.exceptions.ValidationError as error:
        state_manager.set_step_status(Status.FAILED)
        logger.error(error)
        return

    state_manager.set_step_status(Status.SUCCESS)
    return


def check_deserialization(file_path: str, state_manager: ComplianceToolStateManager,
                          file_info: Optional[str] = None) -> model.DictObjectStore:
    """
    Deserializes a JSON AAS file and reports any issues using the given StateManager

    add the steps: 'Open {} file' and 'Read {} file and check if it is conform to the json schema'

    :param file_path: given file which should be deserialized
    :param state_manager: manager to log the steps
    :param file_info: additional information about the file for name of the steps
    :return: returns the deserialized object store
    """
    logger = logging.getLogger('compliance_check')
    logger.addHandler(state_manager)
    logger.propagate = False
    logger.setLevel(logging.INFO)

    # create handler to get logger info
    logger_deserialization = logging.getLogger(json_deserialization.__name__)
    logger_deserialization.addHandler(state_manager)
    logger_deserialization.propagate = False
    logger_deserialization.setLevel(logging.INFO)

    if file_info:
        state_manager.add_step('Open {} file'.format(file_info))
    else:
        state_manager.add_step('Open file')
    try:
        # open given file
        file_to_be_checked = open(file_path, 'r', encoding='utf-8-sig')
    except IOError as error:
        state_manager.set_step_status(Status.FAILED)
        logger.error(error)
        if file_info:
            state_manager.add_step('Read file {} and check if it is deserializable'.format(file_info))
        else:
            state_manager.add_step('Read file and check if it is deserializable')
        state_manager.set_step_status(Status.NOT_EXECUTED)
        return model.DictObjectStore()

    with file_to_be_checked:
        state_manager.set_step_status(Status.SUCCESS)
        # read given file and check if it is conform to the official json schema
        if file_info:
            state_manager.add_step('Read file {} and check if it is deserializable'.format(file_info))
        else:
            state_manager.add_step('Read file and check if it is deserializable')
        obj_store = json_deserialization.read_aas_json_file(file_to_be_checked, True)

    state_manager.set_step_status_from_log()

    return obj_store


def check_aas_example(file_path: str, state_manager: ComplianceToolStateManager) -> None:
    """
    Checks if a file contains all elements of the aas example and reports any issues using the given StateManager

    calls the check_deserialization and add the steps: 'Check if data is equal to example data'

    :param file_path: given file which should be checked
    :param state_manager: manager to log the steps
    """
    # create handler to get logger info
    logger_example = logging.getLogger(example_aas.__name__)
    logger_example.addHandler(state_manager)
    logger_example.propagate = False
    logger_example.setLevel(logging.INFO)

    obj_store = check_deserialization(file_path, state_manager)

    if state_manager.status in (Status.FAILED, Status.NOT_EXECUTED):
        state_manager.add_step('Check if data is equal to example data')
        state_manager.set_step_status(Status.NOT_EXECUTED)
        return

    checker = AASDataChecker(raise_immediately=False)

    state_manager.add_step('Check if data is equal to example data')
    checker.check_object_store(obj_store, create_example())

    state_manager.add_log_records_from_data_checker(checker)


def check_json_files_equivalence(file_path_1: str, file_path_2: str, state_manager: ComplianceToolStateManager) -> None:
    """
    Checks if two json files contain the same elements in any order and reports any issues using the given StateManager

    calls the check_deserialization for ech file and add the steps: 'Check if data in files are equal'

    :param file_path_1: given first file which should be checked
    :param file_path_2: given second file which should be checked
    :param state_manager: manager to log the steps
    """
    logger = logging.getLogger('compliance_check')
    logger.addHandler(state_manager)
    logger.propagate = False
    logger.setLevel(logging.INFO)

    obj_store_1 = check_deserialization(file_path_1, state_manager, 'first')

    obj_store_2 = check_deserialization(file_path_2, state_manager, 'second')

    if state_manager.status is Status.FAILED:
        state_manager.add_step('Check if data in files are equal')
        state_manager.set_step_status(Status.NOT_EXECUTED)
        return

    checker = AASDataChecker(raise_immediately=False)
    try:
        state_manager.add_step('Check if data in files are equal')
        checker.check_object_store(obj_store_1, obj_store_2)
    except (KeyError, AssertionError) as error:
        state_manager.set_step_status(Status.FAILED)
        logger.error(error)
        return

    state_manager.add_log_records_from_data_checker(checker)
