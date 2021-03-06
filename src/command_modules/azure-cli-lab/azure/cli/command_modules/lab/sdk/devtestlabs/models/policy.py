# coding=utf-8
# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------
# coding: utf-8
# pylint: skip-file
from msrest.serialization import Model


class Policy(Model):
    """A Policy.

    :param description: The description of the policy.
    :type description: str
    :param status: The status of the policy. Possible values include:
     'Enabled', 'Disabled'
    :type status: str or :class:`PolicyStatus
     <azure.mgmt.devtestlabs.models.PolicyStatus>`
    :param fact_name: The fact name of the policy (e.g. LabVmCount, LabVmSize,
     MaxVmsAllowedPerLab, etc. Possible values include: 'UserOwnedLabVmCount',
     'UserOwnedLabPremiumVmCount', 'LabVmCount', 'LabPremiumVmCount',
     'LabVmSize', 'GalleryImage', 'UserOwnedLabVmCountInSubnet',
     'LabTargetCost'
    :type fact_name: str or :class:`PolicyFactName
     <azure.mgmt.devtestlabs.models.PolicyFactName>`
    :param fact_data: The fact data of the policy.
    :type fact_data: str
    :param threshold: The threshold of the policy (i.e. a number for
     MaxValuePolicy, and a JSON array of values for AllowedValuesPolicy).
    :type threshold: str
    :param evaluator_type: The evaluator type of the policy (i.e.
     AllowedValuesPolicy, MaxValuePolicy). Possible values include:
     'AllowedValuesPolicy', 'MaxValuePolicy'
    :type evaluator_type: str or :class:`PolicyEvaluatorType
     <azure.mgmt.devtestlabs.models.PolicyEvaluatorType>`
    :param created_date: The creation date of the policy.
    :type created_date: datetime
    :param provisioning_state: The provisioning status of the resource.
    :type provisioning_state: str
    :param unique_identifier: The unique immutable identifier of a resource
     (Guid).
    :type unique_identifier: str
    :param id: The identifier of the resource.
    :type id: str
    :param name: The name of the resource.
    :type name: str
    :param type: The type of the resource.
    :type type: str
    :param location: The location of the resource.
    :type location: str
    :param tags: The tags of the resource.
    :type tags: dict
    """

    _attribute_map = {
        'description': {'key': 'properties.description', 'type': 'str'},
        'status': {'key': 'properties.status', 'type': 'str'},
        'fact_name': {'key': 'properties.factName', 'type': 'str'},
        'fact_data': {'key': 'properties.factData', 'type': 'str'},
        'threshold': {'key': 'properties.threshold', 'type': 'str'},
        'evaluator_type': {'key': 'properties.evaluatorType', 'type': 'str'},
        'created_date': {'key': 'properties.createdDate', 'type': 'iso-8601'},
        'provisioning_state': {'key': 'properties.provisioningState', 'type': 'str'},
        'unique_identifier': {'key': 'properties.uniqueIdentifier', 'type': 'str'},
        'id': {'key': 'id', 'type': 'str'},
        'name': {'key': 'name', 'type': 'str'},
        'type': {'key': 'type', 'type': 'str'},
        'location': {'key': 'location', 'type': 'str'},
        'tags': {'key': 'tags', 'type': '{str}'},
    }

    def __init__(self, description=None, status=None, fact_name=None, fact_data=None, threshold=None, evaluator_type=None, created_date=None, provisioning_state=None, unique_identifier=None, id=None, name=None, type=None, location=None, tags=None):
        self.description = description
        self.status = status
        self.fact_name = fact_name
        self.fact_data = fact_data
        self.threshold = threshold
        self.evaluator_type = evaluator_type
        self.created_date = created_date
        self.provisioning_state = provisioning_state
        self.unique_identifier = unique_identifier
        self.id = id
        self.name = name
        self.type = type
        self.location = location
        self.tags = tags
