# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------
# pylint: skip-file

# coding=utf-8
# --------------------------------------------------------------------------
# Code generated by Microsoft (R) AutoRest Code Generator 0.17.0.0
# Changes may cause incorrect behavior and will be lost if the code is
# regenerated.
# --------------------------------------------------------------------------

from msrest.serialization import Model


class DeploymentAcs(Model):
    """Deployment operation parameters.

    Variables are only populated by the server, and will be ignored when
    sending a request.

    :ivar uri: URI referencing the template. Default value:
     "https://azuresdkci.blob.core.windows.net/templatehost/CreateAcs_2016-10-18/azuredeploy.json"
     .
    :vartype uri: str
    :param content_version: If included it must match the ContentVersion in
     the template.
    :type content_version: str
    :param admin_username: User name for the Linux Virtual Machines. Default
     value: "azureuser" .
    :type admin_username: str
    :param agent_count: The number of agents for the cluster.  Note, for
     DC/OS clusters you will also get 1 or 2 public agents in addition to
     these seleted masters. Default value: "3" .
    :type agent_count: str
    :param agent_vm_size: The size of the Virtual Machine. Default value:
     "Standard_D2_v2" .
    :type agent_vm_size: str
    :param dns_name_prefix: Sets the Domain name prefix for the cluster.  The
     concatenation of the domain name and the regionalized DNS zone make up
     the fully qualified domain name associated with the public IP address.
    :type dns_name_prefix: str
    :param location: Location for VM resources.
    :type location: str
    :param master_count: The number of DC/OS masters for the cluster. Default
     value: "3" .
    :type master_count: str
    :param name: Resource name for the container service.
    :type name: str
    :param orchestrator_type: The type of orchestrator used to manage the
     applications on the cluster. Possible values include: 'dcos', 'swarm'.
     Default value: "dcos" .
    :type orchestrator_type: str or :class:`orchestratorType
     <Default.models.orchestratorType>`
    :param ssh_key_value: Configure all linux machines with the SSH RSA
     public key string.  Your key should include three parts, for example
     'ssh-rsa AAAAB...snip...UcyupgH azureuser@linuxvm
    :type ssh_key_value: str
    :param tags: Tags object.
    :type tags: object
    :ivar mode: Gets or sets the deployment mode. Default value:
     "Incremental" .
    :vartype mode: str
    """

    _validation = {
        'uri': {'required': True, 'constant': True},
        'dns_name_prefix': {'required': True},
        'name': {'required': True},
        'ssh_key_value': {'required': True},
        'mode': {'required': True, 'constant': True},
    }

    _attribute_map = {
        'uri': {'key': 'properties.templateLink.uri', 'type': 'str'},
        'content_version': {'key': 'properties.templateLink.contentVersion', 'type': 'str'},
        'admin_username': {'key': 'properties.parameters.adminUsername.value', 'type': 'str'},
        'agent_count': {'key': 'properties.parameters.agentCount.value', 'type': 'str'},
        'agent_vm_size': {'key': 'properties.parameters.agentVMSize.value', 'type': 'str'},
        'dns_name_prefix': {'key': 'properties.parameters.dnsNamePrefix.value', 'type': 'str'},
        'location': {'key': 'properties.parameters.location.value', 'type': 'str'},
        'master_count': {'key': 'properties.parameters.masterCount.value', 'type': 'str'},
        'name': {'key': 'properties.parameters.name.value', 'type': 'str'},
        'orchestrator_type': {'key': 'properties.parameters.orchestratorType.value', 'type': 'orchestratorType'},
        'ssh_key_value': {'key': 'properties.parameters.sshKeyValue.value', 'type': 'str'},
        'tags': {'key': 'properties.parameters.tags.value', 'type': 'object'},
        'mode': {'key': 'properties.mode', 'type': 'str'},
    }

    uri = "https://azuresdkci.blob.core.windows.net/templatehost/CreateAcs_2016-10-18/azuredeploy.json"

    mode = "Incremental"

    def __init__(self, dns_name_prefix, name, ssh_key_value, content_version=None, admin_username="azureuser", agent_count="3", agent_vm_size="Standard_D2_v2", location=None, master_count="3", orchestrator_type="dcos", tags=None):
        self.content_version = content_version
        self.admin_username = admin_username
        self.agent_count = agent_count
        self.agent_vm_size = agent_vm_size
        self.dns_name_prefix = dns_name_prefix
        self.location = location
        self.master_count = master_count
        self.name = name
        self.orchestrator_type = orchestrator_type
        self.ssh_key_value = ssh_key_value
        self.tags = tags
