# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------

import codecs
import glob
import json
import os
import re
import socket
import sys
import threading
import webbrowser
from subprocess import PIPE, CalledProcessError, Popen, check_output
from time import sleep

import requests
from sshtunnel import SSHTunnelForwarder
import azure.cli.command_modules.project.references as references
import azure.cli.command_modules.project.settings as Settings
import azure.cli.command_modules.project.utils as utils
import azure.cli.core.azlogging as azlogging  # pylint: disable=invalid-name
from azure.cli.command_modules.acs._params import _get_default_install_location
from azure.cli.command_modules.acs.custom import (acs_create,
                                                  k8s_get_credentials,
                                                  k8s_install_cli)
from azure.cli.command_modules.project.jenkins import Jenkins
from azure.cli.command_modules.project.sshconnect import SSHConnect
from azure.cli.command_modules.resource.custom import _deploy_arm_template_core
from azure.cli.command_modules.storage._factory import storage_client_factory
from azure.cli.core._config import az_config
from azure.cli.core._environment import get_config_dir
from azure.cli.core._profile import Profile
from azure.cli.core._util import CLIError
from azure.cli.core.commands.client_factory import get_mgmt_service_client
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.containerregistry import ContainerRegistryManagementClient
from azure.mgmt.containerregistry.models import Sku as AcrSku
from azure.mgmt.containerregistry.models import (RegistryCreateParameters,
                                                 StorageAccountParameters)
from azure.mgmt.resource.resources import ResourceManagementClient
from azure.mgmt.resource.resources.models.resource_group import ResourceGroup
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.storage.models import Kind, Sku, StorageAccountCreateParameters
from azure.storage.file import FileService

from six.moves.urllib.error import URLError  # pylint: disable=import-error
from six.moves.urllib.request import urlopen  # pylint: disable=import-error

logger = azlogging.get_az_logger(__name__)  # pylint: disable=invalid-name
project_settings = Settings.Project()  # pylint: disable=invalid-name
mindaro_settings = Settings.Mindaro()
random_name = utils.get_random_project_name()  # pylint: disable=invalid-name
default_acs_agent_count = "3"  # pylint: disable=invalid-name
default_acs_master_count = "1"  # pylint: disable=invalid-name

# TODO: Remove and switch to SSH once templates are updated
admin_password = 'Mindaro@Pass1!'  # pylint: disable=invalid-name
# TODO: Default Environment/Namspace for now
# Will update it with azp environment value
default_env_name = "default"  # pylint: disable=invalid-name
default_share_name = "mindaro"  # pylint: disable=invalid-name

# pylint: disable=too-few-public-methods,too-many-arguments
# pylint: disable=no-self-use,too-many-locals,line-too-long,broad-except


def browse_pipeline():
    """
    Creates an SSH tunnel to Jenkins host and opens
    the pipeline in the browser
    """
    # TODO: Read the pipeline name from the project file and open
    # the URL to localhost:PORT/job/[pipelinename]
    jenkins_hostname = project_settings.jenkins_hostname
    admin_username = project_settings.admin_username

    if not jenkins_hostname:
        raise CLIError(
            'Jenkins host name does not exist in projectSettings.json')

    local_port = utils.get_available_local_port()
    local_address = 'http://127.0.0.1:{}/blue'.format(local_port)
    utils.writeline('Jenkins Dashboard available at: {}'.format(local_address))
    utils.writeline('Press CTRL+C to close the tunnel')
    _wait_then_open_async(local_address)
    with SSHTunnelForwarder((jenkins_hostname, 22),
                            ssh_username=admin_username,
                            ssh_password=admin_password,
                            remote_bind_address=('127.0.0.1', 8080),
                            local_bind_address=('0.0.0.0', local_port)):
        try:
            while True:
                sleep(1)
        except KeyboardInterrupt:
            pass


def create_project(ssh_private_key, resource_group=random_name, name=random_name, location='southcentralus', force_create=False, quiet=False):
    """
    Creates a new project which consists of a new resource group,
    ACS Kubernetes cluster and Azure Container Registry
    """
    default_user_name = 'azureuser'
    longprocess = None
    current_process = None
    try:
        if not quiet:
            utils.write('Creating Project ')
        # Validate if mindaro project already exists
        if (not force_create) and project_settings.project_name:
            if not quiet:
                utils.write('{} ...'.format(project_settings.project_name))
            logger.info('\nProject already exists.')

            # Configuring Cluster (if not configured)
            longprocess = utils.Process(quiet)
            current_process = longprocess
            _configure_cluster()
            if longprocess:
                longprocess.process_stop()
            current_process = None
            if not quiet:
                utils.write('Complete.\n')
            return
        elif force_create:
            project_settings.settings = {}
        if not quiet:
            utils.write('{} ...'.format(name))

        # 0. Validate ssh private key path
        if not os.path.exists(ssh_private_key):
            raise CLIError(
                "ssh key does not exist: {}, please run 'ssh-keygen -b 1024' to generate it or pass the correct ssh key.".format(ssh_private_key))

        longprocess = utils.Process(quiet)
        current_process = longprocess
        # 1. Create a resource group: resource_group, location
        logger.info('\nCreating resource group ... ')
        res_client = _get_resource_client_factory()
        resource_group_parameters = ResourceGroup(
            location=location)
        res_client.resource_groups.create_or_update(
            resource_group, resource_group_parameters)
        logger.info('\nResource group "{}" created.'.format(resource_group))

        # 2. Create a storage account (for ACR)
        logger.info('\nCreating storage account ... ')
        storage_account_sku = Sku('Standard_LRS')
        storage_client = _get_storage_service_client()
        storage_account_parameters = StorageAccountCreateParameters(
            sku=storage_account_sku, kind=Kind.storage.value, location=location)
        storage_account_deployment = storage_client.storage_accounts.create(
            resource_group, utils.get_random_string(), parameters=storage_account_parameters)
        storage_account_deployment.wait()
        storage_account_result = storage_account_deployment.result()
        storage_account_name = storage_account_result.name
        storage_account_keys = storage_client.storage_accounts.list_keys(
            resource_group, storage_account_name).keys
        storage_account_key = storage_account_keys[0]
        logger.info('\nStorage account "{}" created.'.format(
            storage_account_name))

        # 3. Create ACR (resource_group, location)
        logger.info('\nCreating Azure container registry ... ')
        res_client.providers.register(
            resource_provider_namespace='Microsoft.ContainerRegistry')
        acr_client = _get_acr_service_client()
        acr_name = 'acr' + utils.get_random_registry_name()
        acr_client.registries.create(resource_group,
                                     acr_name,
                                     RegistryCreateParameters(
                                         location=location,
                                         sku=AcrSku('Basic'),
                                         storage_account=StorageAccountParameters(
                                             storage_account_name, storage_account_key))).wait()
        registry = acr_client.registries.get(resource_group, acr_name)
        logger.info('\nAzure container registry "{}" created.'.format(acr_name))

        # 4. Create Kubernetes cluster
        logger.info('\nCreating Kubernetes cluster ... ')
        kube_deployment_name = 'kube-' + utils.get_random_string()
        kube_cluster_name = 'kube-acs-' + utils.get_random_string()
        acs_deployment = acs_create(resource_group_name=resource_group,
                                    deployment_name=kube_deployment_name,
                                    name=kube_cluster_name,
                                    ssh_key_value=utils.get_public_ssh_key_contents(
                                        ssh_private_key + '.pub'),
                                    dns_name_prefix=kube_cluster_name,
                                    admin_username=default_user_name,
                                    agent_count=default_acs_agent_count,
                                    location=location,
                                    master_count=default_acs_master_count,
                                    orchestrator_type='kubernetes')
        acs_deployment.wait()
        logger.info('\nKubernetes cluster "{}" created.'.format(
            kube_cluster_name))

        # 5. Install kubectl
        logger.info('\nInstalling kubectl ... ')
        kubectl_install_path = _get_default_install_location('kubectl')
        if not os.path.exists(kubectl_install_path):
            k8s_install_cli(
                install_location=kubectl_install_path)
            logger.info('\nKubernetes installed.')

        # 6. Set Kubernetes config
        logger.info('\nSetting Kubernetes config ... ')
        k8s_get_credentials(name=kube_cluster_name,
                            resource_group_name=resource_group,
                            ssh_key_file=ssh_private_key)
        logger.info('\nKubernetes config "{}" created.'.format(
            kube_cluster_name))

        # 7. Store the settings in projectSettings.json
        # TODO: We should create service principal and pass it to the
        # acs_create when creating the Kubernetes cluster
        client_id, client_secret = _get_service_principal()
        project_settings.client_id = client_id
        project_settings.client_secret = client_secret
        project_settings.resource_group = resource_group
        project_settings.cluster_name = kube_cluster_name
        project_settings.cluster_resource_group = resource_group
        project_settings.admin_username = default_user_name
        project_settings.container_registry_url = 'https://' + \
            registry.login_server  # pylint: disable=no-member
        project_settings.location = location
        project_settings.project_name = name
        project_settings.ssh_private_key = ssh_private_key
        logger.info('\nProject "{}" created.'.format(name))

        if longprocess:
            longprocess.process_stop()
        current_process = None

        # 8. Configure the Kubernetes cluster
        # Initializes a workspace definition that automates connection to a Kubernetes cluster
        # in an Azure container service for deploying services.
        longprocess = utils.Process(quiet)
        current_process = longprocess
        _configure_cluster()
        if longprocess:
            longprocess.process_stop()
        current_process = None
        if not quiet:
            utils.write(' Complete.\n')
    except KeyboardInterrupt:
        utils.writeline('Killing process ...')
    finally:
        if current_process:
            current_process.process_stop()
        if quiet:
            return project_settings


def delete_project(wait=False):
    """
    Deletes the Azure resource group containing project's artifacts and the projectResource.json file.
    """
    _verify_project_resource_exists()
    resource_group = project_settings.resource_group
    if resource_group is None:
        logger.info('Resource group information missing from file {project_resource_file}'.format(
            project_resource_file=project_settings.settings_file))
    else:
        res_client = _get_resource_client_factory()
        logger.info('Deleting resource group {resource_group}.'.format(
            resource_group=resource_group))
        res = res_client.resource_groups.delete(
            resource_group_name=resource_group, raw=not wait)
        if wait:
            logger.info('Waiting for delete resource group {resource_group} operation to complete.'.format(
                resource_group=resource_group))
            res.wait()
            if res.done():
                logger.info('Resource group {resource_group} deleted.'.format(
                    resource_group=resource_group))
    logger.info('Deleting file {project_resource_file}'.format(
        project_resource_file=project_settings.settings_file))
    project_settings.delete()
    logger.info('Deleting file {mindaro_settings_file}'.format(
        mindaro_settings_file=mindaro_settings.settings_file))
    mindaro_settings.delete()
    logger.info('Project deleted.')


def create_deployment_pipeline(remote_access_token):  # pylint: disable=unused-argument
    """
    Provisions Jenkins and configures CI and CD pipelines, kicks off initial build-deploy
    and saves the CI/CD information to a local project file.
    """
    longprocess = None
    current_process = None
    service_name = _get_service_name()
    try:
        utils.write('Creating build and deployment pipelines for {} ...'.format(
            service_name))

        # Check if we already have a pipeline for this repo and service
        if not project_settings.jenkins_hostname:
            git_repo = _get_git_remote_url()
            resource_group = project_settings.resource_group
            client_id = project_settings.client_id
            client_secret = project_settings.client_secret
            admin_username = project_settings.admin_username
            container_registry_url = project_settings.container_registry_url
            location = project_settings.location
            project_name = project_settings.project_name

            jenkins_dns_prefix = 'jenkins-' + utils.get_random_string()
            jenkins_resource = Jenkins(
                resource_group, admin_username,
                admin_password, client_id, client_secret,
                git_repo, jenkins_dns_prefix, location,
                container_registry_url, service_name, project_name,
                _get_pipeline_name())

            longprocess = utils.Process()
            current_process = longprocess

            jenkins_resource.deploy().wait()

            jenkins_hostname = utils.get_remote_host(
                jenkins_resource.dns_prefix, jenkins_resource.location)
            project_settings.jenkins_hostname = jenkins_hostname
            project_settings.set_ci_pipeline_name(
                jenkins_resource._get_ci_job_name(), _get_git_remote_url(), _get_service_folder())
            project_settings.set_cd_pipeline_name(
                jenkins_resource._get_cd_job_name(), _get_git_remote_url(), _get_service_folder())

            utils.write('Created')
            if longprocess:
                longprocess.process_stop()
            current_process = None
        else:
            # Check if the pipelines are already created
            if _deployment_pipelines_exist():
                sleep(5)
                utils.write('Created')
            else:
                git_repo = _get_git_remote_url()
                resource_group = project_settings.resource_group
                client_id = project_settings.client_id
                client_secret = project_settings.client_secret
                admin_username = project_settings.admin_username
                container_registry_url = project_settings.container_registry_url
                location = project_settings.location
                project_name = project_settings.project_name

                existing_jenkins_prefix = project_settings.jenkins_hostname.split('.')[
                    0]
                jenkins_resource = Jenkins(
                    resource_group, admin_username,
                    admin_password, client_id, client_secret,
                    git_repo, existing_jenkins_prefix, location,
                    container_registry_url, service_name, project_name,
                    _get_pipeline_name())

                longprocess = utils.Process()
                current_process = longprocess

                jenkins_resource.create_pipelines()
                project_settings.set_ci_pipeline_name(
                    jenkins_resource._get_ci_job_name(),
                    _get_git_remote_url(),
                    _get_service_folder())
                project_settings.set_cd_pipeline_name(
                    jenkins_resource._get_cd_job_name(),
                    _get_git_remote_url(),
                    _get_service_folder())
                utils.write('Created')

                if longprocess:
                    longprocess.process_stop()
                current_process = None

        utils.writeline('Git push to {} to trigger the pipeline'.format(
            _get_git_remote_url()))
        utils.writeline(
            "Run 'azp deployment-pipeline browse' to view pipeline status")
    except KeyboardInterrupt:
        utils.writeline('Killing process ...')
    finally:
        if current_process:
            current_process.process_stop()


def add_environment(environment_name):
    """
    Adds an environment/namespace to your cluster
    :param environment_name: Environment Name
    :type environment_name: String
    """
    _run_innerloop_command('environment add --env {}'.format(environment_name))
    utils.execute_command(
        'kubectl create namespace {}'.format(environment_name))


def delete_environment(environment_name):
    """
    Deletes environment/namespace from your cluster
    :param environment_name: Environment Name
    :type environment_name: String
    """
    _run_innerloop_command('environment delete --env {}'.format(environment_name))
    utils.execute_command(
        'kubectl delete namespace {}'.format(environment_name))


def list_environment():
    """
    Lists all the environments/namespaces from your cluster
    """
    _run_innerloop_command('environment list')


def get_current_environment():
    """
    Gets the current environments/namespaces from your cluster
    """
    utils.writeline("* " + _get_current_environment())


def set_current_environment(environment_name):
    """
    Sets the current environments/namespaces in your cluster
    """
    _run_innerloop_command(
        'environment current set --env {}'.format(environment_name))

def add_reference_mongo(target_group, target_name, reference_name='mongo', env_variables=None):
    add_reference(target_group, target_name, reference_name, env_variables, 'mongo')

def add_reference_sql(target_group, target_name, reference_name='sql', env_variables=None):
    add_reference(target_group, target_name, reference_name, env_variables, 'sql')

def add_reference_servicebus(target_group, target_name, reference_name='servicebus', env_variables=None):
    add_reference(target_group, target_name, reference_name, env_variables, 'servicebus')

def add_reference_custom(reference_name, env_variables):
    add_reference(None, None, reference_name, env_variables, 'custom')

def add_reference(target_group, target_name, reference_name, env_variables, reference_type):
    """
    Adds a reference to an Azure resource
    :param target_group: Azure resource group name that contains the Azure resource
    :type target_group: String
    :param target_name: Azure resource name
    :type target_name: String
    :param reference_name: Name of the reference
    :type reference_name: String
    """
    service_name = _get_service_name()
    _validate_reference_name(reference_name)

    current_environment = _get_current_environment()

    if references.reference_exists(service_name, reference_name, current_environment):
        raise CLIError("Reference '{}' for service '{}' already exists".format(
            service_name, reference_name))

    env_variables, instance_type = references.add_reference(
        service_name, target_group, target_name, reference_name,
        env_variables, current_environment, reference_type)

    utils.writeline("Added reference '{}'".format(reference_name))
    utils.writeline('Environment variables:\n{}'.format(
        '\n'.join(env_variables)))
    _service_add_reference(reference_name, instance_type, service_name)


def remove_reference(reference_name):
    """
    Removes reference name
    :param reference_name: Name of the reference
    :type reference_name: String
    """
    _validate_reference_name(reference_name)
    service_name = _get_service_name()
    references.remove_reference(service_name, reference_name)
    utils.writeline("Removed reference '{}'".format(reference_name))
    _service_remove_reference(reference_name)


def _validate_reference_name(reference_name):
    """
    Validates the reference name and throws an exception
    if reference name is invalid. A valid reference name
    must consist of alphanumeric characters, or '_'
    """
    result = re.match('[_a-zA-Z0-9]+', reference_name)
    if result.group() != reference_name:
        raise CLIError(
            "{} is not a valid reference Name. A reference name must consist of alphanumeric characters, or '_'".format(reference_name))


def _deployment_pipelines_exist():
    """
    Checks if the deployment pipeline already
    exists for this repo and service folder.
    """
    service_folder = _get_service_folder()
    git_remote_url = _get_git_remote_url()

    return project_settings.get_ci_pipeline_name(git_remote_url, service_folder) or\
        project_settings.get_cd_pipeline_name(git_remote_url, service_folder)


def _wait_then_open(url):
    """
    Waits for a bit then opens a URL. Useful for
    waiting for a proxy to come up, and then open the URL.
    """
    for _ in range(1, 10):
        try:
            urlopen(url)
        except URLError:
            sleep(1)
        break
    webbrowser.open_new_tab(url)


def _wait_then_open_async(url):
    """
    Tries to open the URL in the background thread.
    """
    thread = threading.Thread(target=_wait_then_open, args=({url}))
    thread.daemon = True
    thread.start()


def _get_service_principal():
    """
    Gets the service principal and secret tuple
    from the acsServicePrincipal.json for currently logged in user
    """
    subscription_id = _get_subscription_id()
    config_file = os.path.join(get_config_dir(), 'acsServicePrincipal.json')
    file_descriptor = os.open(config_file, os.O_RDONLY)
    with os.fdopen(file_descriptor) as file_object:
        config_file_contents = json.loads(file_object.read())
    client_id = config_file_contents[subscription_id]['service_principal']
    client_secret = config_file_contents[subscription_id]['client_secret']
    return client_id, client_secret


def _get_subscription_id():
    _, sub_id, _ = Profile().get_login_credentials(subscription_id=None)
    return sub_id


def _get_acs_info(name, resource_group_name):
    """
    Gets the ContainerService object from Azure REST API.

    :param name: ACS resource name
    :type name: String
    :param resource_group_name: Resource group name
    :type resource_group_name: String
    """
    mgmt_client = get_mgmt_service_client(ComputeManagementClient)
    return mgmt_client.container_services.get(resource_group_name, name)


def _get_acr_service_client():
    """
    Gets the ACR service client
    """
    return get_mgmt_service_client(ContainerRegistryManagementClient)


def _get_resource_client_factory():
    """
    Gets the service client for resource management
    """
    return get_mgmt_service_client(ResourceManagementClient)


def _get_storage_service_client():
    """
    Gets  the client for managing storage accounts.
    """
    return get_mgmt_service_client(StorageManagementClient)


def _get_git_root_folder_name():
    """
    Gets the git root folder name. E.g. if current folder is
    /myfolder/subfolder/test and the git repo root is /myfolder
    this method returns myfolder
    """
    try:
        full_path = check_output(['git', 'rev-parse', '--show-toplevel'])
    except CalledProcessError as exc:
        raise CLIError(
            'This command needs to be run inside the Git repository')
    return os.path.basename(full_path.decode().strip()).lower()


def _get_service_name():
    """
    Gets the name of the service using the Git
    repo root folder and subfolders or uses
    the folder name if we are not in the Git repo.
    """
    # Default to current folder if we are not in
    # the Git repository
    service_name = os.path.basename(os.getcwd().strip()).lower()
    if os.path.exists('.git'):
        service_name = _get_service_folder().replace('/', '-').lower()
    return service_name


def _get_service_folder():
    """
    Gets the service folder up from the Git root.
    E.g. with Git repo root in BikeRepository, the
    method returns BikeRepository/servicea/api if
    CLI is invoked in the /servicea/api subfolder of the repo.
    """
    git_root = _get_git_root_folder_name()
    current_folder = os.getcwd().lower()
    return ''.join(current_folder.partition(git_root)[1:]).lower()


def _get_pipeline_name():
    """
    Gets the name used for Jenkins pipelines by
    getting the current folder, partitioning it at base_repo_name
    taking the string on the right (subfolder) replacing '/' with '-'
    and combine the both strings. For example:
    if command is run in the root folder of BikeSharing of the
    repository Contoso/BikeSharing, this method returns 'Contoso/BikeSharing'.
    If command is run in a subfolder (e.g. BikeSharing/reservations/api), method
    returns Contoso/BikeSharing-reservations-api
    """
    remote_url = _get_git_remote_url()
    # Get owner|organization/repo e.g. BikeSharing/reservations
    # and replace '/' with '-' as '/' can't be used in the pipeline name
    # which becomes a part of the URL
    # TODO: Need to do this for VSTS repos as well.
    owner_repo = remote_url.partition(
        'github.com/')[2].replace('/', '-').replace('.git', '')

    base_repo_name = _get_git_root_folder_name()
    current_directory = os.getcwd()
    subfolders = current_directory.partition(
        base_repo_name)[2].strip('/').replace('/', '-')
    return '-'.join([owner_repo, subfolders]).strip('-').lower()


def _get_git_remote_url():
    """
    Tries to find a remote for the repo in the current folder.
    If only one remote is present return that remote,
    if more than one remote is present it looks for origin.
    """
    try:
        remotes = check_output(['git', 'remote']).strip().splitlines()
        remote_url = ''
        if len(remotes) == 1:
            remote_url = check_output(
                ['git', 'remote', 'get-url', remotes[0].decode()]).strip()
        else:
            remote_url = check_output(
                ['git', 'remote', 'get-url', 'origin']).strip()
    except ValueError as value_error:
        logger.debug(value_error)
        raise CLIError(
            "A default remote was not found for the current folder. \
            Please run this command in a git repository folder with \
            an 'origin' remote or specify a remote using '--remote-url'")
    except CalledProcessError as called_process_err:
        raise CLIError(
            'Please ensure git version 3.5.0 or greater is installed.\n' + called_process_err)
    return remote_url.decode()


def _configure_cluster():  # pylint: disable=too-many-statements
    """
    Configures the cluster to deploy tenx services which can be used by the user
    deployed services and initializes a workspace on the local machine to connection.
    """
    artifacts_path = None
    ssh_client = None
    try:
        # Setting the values
        dns_prefix = project_settings.cluster_name
        location = project_settings.location
        user_name = project_settings.admin_username
        acr_server = project_settings.container_registry_url.replace(
            "https://", "")
        ssh_private_key = project_settings.ssh_private_key

        # Validate kubectl context
        if not _validate_kubectl_context(dns_prefix):
            raise CLIError(
                "kubectl context not set to {}, please run 'az acs kubernetes get-credentials' to set it.".format(dns_prefix))

        if _cluster_configured(dns_prefix, user_name):
            logger.info('\nCluster already configured.')
            return
        else:
            logger.debug('Cluster not configured.')

        logger.info('\nConfiguring Kubernetes cluster ... ')

        innerloop_client_path = _get_innerloop_home_path()
        artifacts_path = os.path.join(
            innerloop_client_path, 'Artifacts')

        # Removing existing cluster from ~/.ssh/known_hosts
        known_hostname_command = 'ssh-keygen -R {}'.format(
            utils.get_remote_host(dns_prefix, location))
        utils.execute_command(known_hostname_command)

        # SSHClient connection
        ssh_client = SSHConnect(
            dns_prefix, location, user_name, ssh_private_key=ssh_private_key)

        # Get resource group
        creds = _get_creds_from_master(ssh_client)
        resource_group = creds['resourceGroup']
        client_id = creds['aadClientId']
        client_secret = creds['aadClientSecret']

        # Cluster Setup(deploying required artifacts in the kubectl nodes)
        logger.info('\nPreparing ARM configuration ... ')
        k8_parameters = _prepare_arm_k8(dns_prefix, artifacts_path)
        logger.info('\nARM configuration prepared.')

        logger.info('\nCreating Resources ... ')
        _deploy_arm_template_core(
            resource_group,
            template_file='{}/k8.deploy.json'.format(artifacts_path),
            deployment_name=dns_prefix,
            parameter_list=[k8_parameters])
        logger.info('\nARM template deployed.')

        logger.info('\nCreating tenx namespace ... ')
        namespace_command = "kubectl create namespace tenx"
        utils.execute_command(namespace_command, tries=10)

        logger.info('\nDeploying ACR credentials in Kubernetes ... ')
        workspace_storage_key = _deploy_secrets_share_k8(
            acr_server, resource_group, dns_prefix, client_id,
            client_secret, location, user_name, artifacts_path)
        logger.info('\nACR credentials deployed.')

        logger.info('\nEnumerating Kubernetes agents ... ')
        _enumerate_k8_agents(artifacts_path)

        logger.info('\nPreparing the cluster ... ')
        ssh_client.run_command(
            'mkdir ~/.azure')
        ssh_client.run_command(
            'mkdir ~/.ssh')
        ssh_client.run_command(
            'rm ~/hosts')
        ssh_client.put(
            '{}/hosts.tmp'.format(artifacts_path), '~/hosts')
        logger.info('\nCluster prepared.')

        logger.info('\nCopying configuration files into the cluster ... ')
        ssh_client.put(
            ssh_private_key, '~/.ssh/id_rsa')
        ssh_client.put(
            '{}/connectlocal.tmp.sh'.format(artifacts_path), '~/connectlocal.tmp.sh')
        ssh_client.put(
            '{}/configagents.sh'.format(artifacts_path), '~/configagents.sh')
        ssh_client.put(
            '{}/master-svc.sh'.format(artifacts_path), '~/master-svc.sh')

        ssh_client.run_command(
            'chmod 600 ~/.ssh/id_rsa')
        ssh_client.run_command(
            'chmod +x ./configagents.sh')
        ssh_client.run_command(
            'chmod +x ./master-svc.sh')
        logger.info('\nConfiguration files copied.')

        logger.info('\nConfiguring agents in the cluster ... ')
        ssh_client.run_command(
            'source ./configagents.sh', True)
        ssh_client.run_command(
            'source ./master-svc.sh </dev/null >./master-svc.log 2>&1 &', True)

        logger.info('\nCleaning existing TenX services in cluster ... ')
        utils.execute_command(
            "kubectl delete -f {}/tenx.tmp.yaml".format(artifacts_path))
        utils.execute_command(
            "kubectl delete -f {}/tenxPrivate.tmp.yaml".format(artifacts_path))
        utils.execute_command(
            "kubectl delete -f {}/tenxServices.yaml -n tenx".format(artifacts_path))
        utils.execute_command(
            "kubectl delete -f {}/tenxPrivateService.yaml -n tenx".format(artifacts_path))
        utils.execute_command(
            "kubectl delete -f {}/tenxConfigService.yaml -n tenx".format(artifacts_path))
        utils.execute_command(
            "kubectl delete -f {}/tenxBuildService.yaml -n tenx".format(artifacts_path))
        utils.execute_command(
            "kubectl delete -f {}/tenxExecService.yaml -n tenx".format(artifacts_path))
        utils.execute_command(
            "kubectl delete -f {}/tenxRsrcService.yaml -n tenx".format(artifacts_path))
        utils.execute_command(
            "kubectl delete -f {}/tenxPublicEndpoint.yaml -n tenx".format(artifacts_path))

        logger.info('\nDeploying TenX services to K8 cluster ... ')
        utils.execute_command(
            "kubectl create -f {}/tenx.tmp.yaml".format(artifacts_path))
        utils.execute_command(
            "kubectl create -f {}/tenxPrivate.tmp.yaml".format(artifacts_path))

        logger.info('\nExposing TenX services from cluster ... ')
        utils.execute_command(
            "kubectl create -f {}/tenxServices.yaml -n tenx".format(artifacts_path), throw=True, tries=3)
        utils.execute_command(
            "kubectl create -f {}/tenxPrivateService.yaml -n tenx".format(artifacts_path), throw=True, tries=3)
        utils.execute_command(
            "kubectl create -f {}/tenxConfigService.yaml -n tenx".format(artifacts_path), throw=True, tries=3)
        utils.execute_command(
            "kubectl create -f {}/tenxBuildService.yaml -n tenx".format(artifacts_path), throw=True, tries=3)
        utils.execute_command(
            "kubectl create -f {}/tenxExecService.yaml -n tenx".format(artifacts_path), throw=True, tries=3)
        utils.execute_command(
            "kubectl create -f {}/tenxRsrcService.yaml -n tenx".format(artifacts_path), throw=True, tries=3)
        utils.execute_command(
            "kubectl create -f {}/tenxPublicEndpoint.yaml -n tenx".format(artifacts_path), throw=True, tries=3)

        # Initialize Workspace
        logger.info('\nInitializing Workspace: {} ... '.format(dns_prefix))
        workspace_storage = dns_prefix.replace('-', '') + 'wks'
        sleep(5)
        _initialize_environment(
            dns_prefix, user_name, workspace_storage,
            workspace_storage_key, ssh_private_key, location=location)

    finally:
        # Removing temporary data files
        if artifacts_path:
            file_path = os.path.join(artifacts_path, '*.tmp.*')
            files = glob.glob(file_path)
            for single_file in files:
                os.remove(single_file)

        # Removing temporary creds file: azure.json
        azure_json_file = _get_creds_file()
        if os.path.exists(azure_json_file):
            os.remove(azure_json_file)

        # Close SSHClient
        if ssh_client:
            ssh_client.close()


def _validate_kubectl_context(dns_prefix):
    context_command = 'kubectl config current-context'
    current_context = utils.get_command_output(context_command)
    return current_context.strip() == dns_prefix.strip()


def _cluster_configured(dns_prefix, user_name):  # pylint: disable=too-many-return-statements
    """
    Detects if the cluster exists and already configured i.e.
    all the required services are available and running.
    The check is done in 2 parts:
    1. Checks if the workspace is initialized (settings.json exists)
    2. Checks if all the services are running by pinging each URL.
    """

    logger.info('\nDetecting if the cluster is configured ... ')
    settings_json_file_path = _get_environment_settings_file()
    workspace_err_message = '  Workspace not defined.'
    if not os.path.exists(settings_json_file_path):
        logger.debug(workspace_err_message)
        return False
    cluster_settings = json.load(codecs.open(
        settings_json_file_path, 'r', 'utf-8-sig'))

    default_workspace_name = cluster_settings["DefaultWorkspace"]
    if not default_workspace_name:
        logger.debug(workspace_err_message)
        return False

    default_workspace = cluster_settings["Workspaces"][default_workspace_name]
    if not default_workspace:
        logger.debug(workspace_err_message)
        return False

    cluster = default_workspace["Cluster"]
    ssh_user = default_workspace["SSHUser"]

    if not(cluster == dns_prefix and ssh_user == user_name):
        return False

    try:
        url_sub_path = "api/ping"
        build_service_url = default_workspace["BuildServiceUrl"]
        logger.info('\n  Checking build service')
        if not _ping_url("{}/{}".format(build_service_url, url_sub_path)):
            return False

        exec_service_url = default_workspace["ExecServiceUrl"]
        logger.info('\n  Checking exec service')
        if not _ping_url("{}/{}".format(exec_service_url, url_sub_path)):
            return False

        rsrc_service_url = default_workspace["RsrcServiceUrl"]
        logger.info('\n  Checking rsrc service')
        if not _ping_url("{}/{}".format(rsrc_service_url, url_sub_path)):
            return False

        config_service_url = default_workspace["ConfigServiceUrl"]
        logger.info('\n  Checking config service')
        if not _ping_url("{}/{}".format(config_service_url, url_sub_path)):
            return False

        # All services running
        return True
    except Exception:
        return False


def _ping_url(url):
    """
    Pings passed URL and returns True if success.
    """
    req = requests.get(url)
    return req.status_code == 200


def _enumerate_k8_agents(artifacts_path):
    """
    Enumerate the Kubernetes nodes (agents) and
    write them in a file to be copied to the master host.
    """
    retry = 0
    tries = 24  # Timeout = 2 minutes
    command_output = utils.get_command_output(
        "kubectl get nodes -o jsonpath='{range .items[*]}{@.metadata.name}:{range @.status.conditions[3]}{@.type}={@.status};{end}{end}' | grep 'Ready=True'", 10)
    hosts_file_path = os.path.join(
        artifacts_path, 'hosts.tmp')
    hosts_file_content = ''
    while retry < tries:
        agents_count = 0
        try:
            for line in command_output.split(';'):
                if not(line or line.strip()):
                    break
                host_name = line.split(':')[0]
                if "agent" in host_name:
                    hosts_file_content = hosts_file_content + host_name + '\n'
                    logger.debug(host_name)
                    agents_count = agents_count + 1
        except FileNotFoundError as error:
            raise CLIError(error)

        if agents_count == int(default_acs_agent_count):
            break
        else:
            logger.debug("Retrying ...")
            sleep(5)
            hosts_file_content = ''
            retry = retry + 1

    if hosts_file_content:
        with open(hosts_file_path, "w") as hosts_file:
            hosts_file.write(hosts_file_content)


def _deploy_secrets_share_k8(acr_server, resource_group, dns_prefix, client_id,
                             client_secret, location, user_name, artifacts_path):
    """
    Install cluster/registry secrets and creates share on the file storage.
    """
    _install_k8_secret(acr_server, dns_prefix, client_id,
                       client_secret, location, user_name, artifacts_path)
    workspace_storage_key = _install_k8_shares(
        resource_group, dns_prefix, artifacts_path)
    return workspace_storage_key


def _install_k8_secret(acr, dns_prefix, client_id, client_secret,
                       location, cluster_user_name, artifacts_path):
    """
    Creates a registry secret in the cluster, used by the tenx services.
    Prepares the file to create resource in the Kubernetes cluster.
    """
    kubectl_create_delete_command = "kubectl delete secret tenxregkey -n tenx"
    try:
        utils.execute_command(kubectl_create_delete_command)
    except Exception:
        logger.debug("Command failed: %s\n", kubectl_create_delete_command)

    kubectl_create_secret_command = "kubectl create secret docker-registry tenxregkey \
    --docker-server={} --docker-username={} --docker-password={} --docker-email={}@{} \
    -n tenx".format(acr, client_id, client_secret, cluster_user_name,
                    utils.get_remote_host(dns_prefix, location))
    try:
        utils.execute_command(kubectl_create_secret_command)
    except Exception:
        logger.debug("Command failed: %s\n", kubectl_create_secret_command)

    config_storage = dns_prefix.replace('-', '') + "cfgsa"
    private_storage = dns_prefix.replace('-', '') + "private"

    try:
        tenx_yaml_path = os.path.join(
            artifacts_path, 'tenx.yaml')
        with open(tenx_yaml_path, "r") as tenx_yaml_file:
            tenx_yaml = tenx_yaml_file.read()

        substitutions = {
            '$TENX_PRIVATE_REGISTRY$' : acr,
            '$TENX_STORAGE_ACCOUNT$' : config_storage,
            '$TENXBUILDER_IMAGE$' : 'mindaro/tenx-build-service',
            '$TENXCONFIG_IMAGE$' : 'mindaro/tenx-config-service',
            '$TENXEXEC_IMAGE$' : 'mindaro/tenx-execute-service',
            '$TENXRSRC_IMAGE$' : 'mindaro/tenx-rsrc-service',
            '$TENX_NGINX_IMAGE$' : 'mindaro/tenx-nginx-gateway',
            '$TENXCLIENT_IMAGE$' : 'xinyan/tenxclient'
        }
        tmp_tenx_yaml = _map_contents(tenx_yaml, substitutions)

        tmp_tenx_yaml_path = os.path.join(
            artifacts_path, 'tenx.tmp.yaml')
        with open(tmp_tenx_yaml_path, "w") as tmp_tenx_yaml_file:
            tmp_tenx_yaml_file.write(tmp_tenx_yaml)

        tenx_private_yaml_path = os.path.join(
            artifacts_path, 'tenxPrivate.yaml')
        with open(tenx_private_yaml_path, "r") as tenx_private_yaml_file:
            tenx_private_yaml = tenx_private_yaml_file.read()

        substitutions = {
            '$TENX_STORAGE_ACCOUNT_PRIVATE$': private_storage,
            '$TENXCONFIG_IMAGE$' : 'mindaro/tenx-config-service'
        }
        tmp_tenx_private_yaml = _map_contents(tenx_private_yaml, substitutions)

        tmp_tenx_private_yaml_path = os.path.join(
            artifacts_path, 'tenxPrivate.tmp.yaml')
        with open(tmp_tenx_private_yaml_path, "w") as tmp_tenx_private_yaml_file:
            tmp_tenx_private_yaml_file.write(tmp_tenx_private_yaml)
    except FileNotFoundError as error:
        raise CLIError(error)

def _map_contents(yaml, substitutions):
    """
    Returns a mapped string containing all the substitutions
    provided in the subsitutions object
    """
    for key in substitutions:
        yaml = yaml.replace(key, substitutions.get(key))
    return yaml


def _install_k8_shares(resource_group, dns_prefix, artifacts_path):
    """
    Creates/ensures the shares in the file storage.
    Prepares the connection file that runs on each agent
    and mounts the directory to a share in the file storage.
    """
    # Populate connectlocal.tmp.sh with private storage account key
    config_storage = dns_prefix.replace('-', '') + "cfgsa"
    workspace_storage = dns_prefix.replace('-', '') + "wks"
    scf = storage_client_factory()
    config_storage_key = _get_storage_key(
        resource_group, scf, config_storage, 10)
    workspace_storage_key = _get_storage_key(
        resource_group, scf, workspace_storage, 10)

    connect_template_path = os.path.join(
        artifacts_path, 'connectlocal.template.sh')
    with open(connect_template_path, "r") as connect_template_file:
        connect_template = connect_template_file.read()
    connect_template = connect_template.replace("$STORAGEACCOUNT_PRIVATE$", config_storage) \
        .replace("$STORAGE_ACCOUNT_PRIVATE_KEY$", config_storage_key) \
        .replace("$STORAGEACCOUNT$", workspace_storage) \
        .replace("$STORAGE_ACCOUNT_KEY$", workspace_storage_key) \
        .replace("$SHARE_NAME$", default_share_name)

    connect_output = os.path.join(
        artifacts_path, 'connectlocal.tmp.sh')
    with open(connect_output, "w") as connect_output_file:
        connect_output_file.write(connect_template)

    # Create 'cfgs' share in configStorage
    file_service = FileService(
        account_name=config_storage, account_key=config_storage_key)
    file_service.create_share(share_name='cfgs')

    # Create 'mindaro' share in configStorage
    file_service = FileService(
        account_name=workspace_storage, account_key=workspace_storage_key)
    file_service.create_share(share_name=default_share_name)
    file_service.create_directory(
        share_name=default_share_name, directory_name=default_env_name)

    return workspace_storage_key


def _get_storage_key(resource_group, scf, storage, tries):
    # Re-tries in case the config storage account is not ready yet
    retry = 0
    storage_key = None
    while retry < tries:
        try:
            keys_list_json = scf.storage_accounts.list_keys(
                resource_group, storage).keys  # pylint: disable=no-member
            storage_key = list(keys_list_json)[0].value
            if storage_key != None:
                break
        except Exception as error:
            logger.debug(error)
        finally:
            logger.debug(
                "Couldn't get storage account key for {}, Retrying ... ".format(storage))
            sleep(2)
            retry = retry + 1
    if storage_key is None:
        raise CLIError(
            "Can't get storage account key for {}".format(storage))
    return storage_key


def _get_creds_from_master(ssh_client):
    """
    Copies azure.json file from the master host on the Kubernetes cluster to local system.
    Provides the json data from the file.
    """
    tenx_dir = _get_azure_dir()
    if not os.path.exists(tenx_dir):
        os.mkdir(tenx_dir)

    azure_json_file = _get_creds_file()
    if os.path.exists(azure_json_file):
        os.remove(azure_json_file)

    ssh_client.get(
        '/etc/kubernetes/azure.json', azure_json_file)
    with open(azure_json_file, "r") as credentials_file:
        creds = json.load(credentials_file)
    return creds


def _get_azure_dir():
    """
    Provides the local path of .tenx dir.
    """
    tenx_dir = os.path.join(os.path.expanduser('~'), '.azure')
    return tenx_dir


def _get_creds_file():
    """
    Provides the local path of azure.json file, copied
    from the master host on the Kubernetes cluster.
    """
    azure_json_file = os.path.join(_get_azure_dir(), 'azure.json')
    return azure_json_file


def _get_environment_settings_file():
    """
    Provides settings.json file path.
    """
    environment_settings_file = os.path.join(_get_azure_dir(), 'settings.json')
    return environment_settings_file


def _prepare_arm_k8(dns_prefix, artifacts_path):
    """
    Prepares template file for configuring the Kubernetes cluster.
    """
    try:
        k8_parameters_file_path = os.path.join(
            artifacts_path, 'k8.deploy.parameters.json')
        with open(k8_parameters_file_path, "r") as k8_parameters_file:
            k8_parameters = k8_parameters_file.read()
        new_k8_parameters = k8_parameters.replace(
            "CLUSTER_NAME", dns_prefix.replace('-', ''))

        new_k8_parameters_file_path = os.path.join(
            artifacts_path, 'k8.deploy.parameters.tmp.json')
        with open(new_k8_parameters_file_path, "w") as new_k8_parameters_file:
            new_k8_parameters_file.write(new_k8_parameters)

        return new_k8_parameters
    except FileNotFoundError as error:
        raise CLIError(error)


def _initialize_environment(
        dns_prefix,
        user_name,
        storage_account_name,
        storage_account_key,
        ssh_private_key,
        location='westus',
        share_name=default_share_name):
    """
    Calls tenx initialize command on the current directory.
    Initialize creates settings.json file which contains all the
    credentials and links to connect to the cluster.
    """
    _run_innerloop_command('environment', 'initialize', '--cluster', dns_prefix, '--storage',
                           storage_account_name, '--storage-key', storage_account_key, '--share',
                           share_name, '--location', location, '--ssh', ssh_private_key,
                           '--quiet', '--k8')

    # Checking if the services are ready
    while not _cluster_configured(dns_prefix, user_name):
        logger.debug('\nServices are not ready yet. Waiting ... ')
        logger.info('\nRetrying ... ')
        sleep(5)
    logger.info('\nCluster configured successfully.')


def _get_current_environment():
    """
    Calls innerloop environment command on the current directory.
    Gets the current set environment from settings.json.
    It represents the namespace in the current kubectl config.
    All the services would start under the same namespace in the cluster.
    """
    return _get_innerloop_command_output('environment current get')


def _verify_project_resource_exists():
    if not os.path.exists(project_settings.settings_file):
        raise CLIError(
            "projectResource.json not found, please run 'az project create' to create resources.")


def service_up(project_path, public_start):
    """
    Automates building the project/service in a Docker image and
    pushing to an Azure container registry, and creates a release
    definition that automates deploying container images from a
    container registry to a Kubernetes cluster in an Azure container
    service. Then deploying the project as a service and running it.

    Run configures the cluster, if not already, then builds
    the service in the cluster and starts the service.

    :param project_path: Project/Service path to deploy on the
    Kubernetes cluster or current directory.
    :type project_path: String
    """

    curr_dir = None
    try:
        if not project_path == ".":
            curr_dir = os.getcwd()
            os.chdir(project_path)
            project_path = curr_dir
        elif not os.path.exists(project_path):
            raise CLIError(
                'Invalid path: {}'.format(project_path))

        # Validate if mindaro project exists
        _verify_project_resource_exists()

        # Configuring Cluster
        _configure_cluster()

        # Building and starting Service ...
        _service_run(public_start)

    except Exception as error:
        raise CLIError(error)
    finally:
        if curr_dir and curr_dir.strip():
            os.chdir(curr_dir)

def service_down(project_path):
    """
    Stops the service.

    :param project_path: Project/Service path to deploy on the
    Kubernetes cluster or current directory.
    :type project_path: String
    """
    curr_dir = None
    try:
        if not project_path == ".":
            curr_dir = os.getcwd()
            os.chdir(project_path)
            project_path = curr_dir
        elif not os.path.exists(project_path):
            raise CLIError(
                'Invalid path: {}'.format(project_path))

        # Validate if mindaro project exists
        _verify_project_resource_exists()

        # Stopping Service ...
        _service_stop()

    except Exception as error:
        raise CLIError(error)
    finally:
        if curr_dir and curr_dir.strip():
            os.chdir(curr_dir)


def service_attach(project_path):
    """
    Attachs to the service.

    :param project_path: Project/Service path to deploy on the
    Kubernetes cluster or current directory.
    :type project_path: String
    """
    curr_dir = None
    try:
        if not project_path == ".":
            curr_dir = os.getcwd()
            os.chdir(project_path)
            project_path = curr_dir
        elif not os.path.exists(project_path):
            raise CLIError(
                'Invalid path: {}'.format(project_path))

        # Validate if mindaro project exists
        _verify_project_resource_exists()

        # Attaching to the Service ...
        _service_attach()

    except Exception as error:
        raise CLIError(error)
    finally:
        if curr_dir and curr_dir.strip():
            os.chdir(curr_dir)


def _service_run(public_start):
    """
    Calls tenx run command on the current directory.
    Run implicitly builds the service in the cluster and starts the service.
    """
    run_command = 'up --port {}'.format(_get_local_port())

    if public_start:
        run_command = run_command + ' --public'

    _run_innerloop_command(run_command)


def _get_local_port():
    environment_name = _get_current_environment()
    service_name = _get_service_name()
    local_port = mindaro_settings.get_service_tunnel_port(
        service_name, environment_name)

    # We pick a new port in the following cases:
    # 1. Service doesn't have the port set yet (first run)
    # 2. Port is not available - i.e. there's something actively using the port
    # When new port is picked (get_available_local_port), we also make sure
    # we don't pick the port that's already taken by one of the services
    if not local_port or not utils.is_port_available(local_port):
        local_port = utils.get_available_local_port()
        mindaro_settings.set_service_tunnel_port(
            service_name, environment_name, local_port)
    
    return local_port


def _service_stop():
    """
    Calls tenx run command on the current directory.
    Stops the service.
    """
    _run_innerloop_command('down')


def _service_attach():
    """
    Calls tenx run command on the current directory.
    Attaches to the service.
    """
    _run_innerloop_command('attach --quiet --port {}'.format(_get_local_port()))


def service_list():
    """
    Lists all the running user services in the Kubernetes cluster.
    """
    try:
        # Listing Services ...
        _service_list()

    except Exception as error:
        raise CLIError(error)


def _service_list():
    """
    Calls tenx service list command on the current directory.
    """
    _run_innerloop_command('service list')


def _service_add_reference(reference_name, reference_type, service_name):
    """
    Calls tenx run command on the current directory.
    Adds reference to the projectInfo
    """
    _run_innerloop_command(
        'reference add -n {} -t {} -s {} -q'.format(reference_name, reference_type, service_name))


def _service_remove_reference(reference_name):
    """
    Calls tenx run command on the current directory.
    Removes reference from the projectInfo
    """
    _run_innerloop_command(
        'reference remove -n {} -q'.format(reference_name))


def _prep_innerloop_command(*args):
    """
    Prepares command for innerloop client
    """
    file_path = _get_innerloop_home_path()

    cmd = os.path.join(file_path, 'tenx')
    if not os.path.isfile(cmd):
        cmd = 'dotnet ' + os.path.join(file_path, 'tenx.dll')

    cmd = cmd + ' ' + ' '.join(args)
    return cmd


def _run_innerloop_command(*args):
    """
    Runs InnerLoop client with the passed parameters.
    """
    try:
        cmd = _prep_innerloop_command(*args)

        # Prints subprocess output while process is running
        with Popen(cmd, shell=True, stdout=PIPE, bufsize=1, universal_newlines=True) as process:
            for line in process.stdout:
                sys.stdout.write(line)

        if process.returncode != 0:
            raise CLIError(CalledProcessError(
                process.returncode, ' '.join(args)))
    except Exception as error:
        raise CLIError(error)


def _get_innerloop_command_output(*args):
    """
    Gets ouptut from InnerLoop client command execution.
    """
    cmd = _prep_innerloop_command(*args)
    return utils.get_command_output(cmd)


def _get_innerloop_home_path():
    """
    Gets the Mindaro-InnerLoop set HOME path.
    """
    try:
        home_path = az_config.get(
            'project', 'mindaro_home', None)  # AZURE_PROJECT_MINDARO_HOME
        if home_path is None:
            raise CLIError(
                'Please set the environment variable: AZURE_PROJECT_MINDARO_HOME to your inner loop source code directory.')
        else:
            return home_path
    except Exception as error:
        raise CLIError(error)
