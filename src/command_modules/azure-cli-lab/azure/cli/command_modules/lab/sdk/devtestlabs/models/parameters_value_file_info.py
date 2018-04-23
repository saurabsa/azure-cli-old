# coding=utf-8
# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------
# coding: utf-8
# pylint: skip-file
from msrest.serialization import Model


class ParametersValueFileInfo(Model):
    """ParametersValueFileInfo.

    :param file_name: File name.
    :type file_name: str
    :param parameters_value_info: Parameters value information in the file.
    :type parameters_value_info: object
    """

    _attribute_map = {
        'file_name': {'key': 'fileName', 'type': 'str'},
        'parameters_value_info': {'key': 'parametersValueInfo', 'type': 'object'},
    }

    def __init__(self, file_name=None, parameters_value_info=None):
        self.file_name = file_name
        self.parameters_value_info = parameters_value_info
