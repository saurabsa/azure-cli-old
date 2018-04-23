# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------

from azure.cli.core.commands import cli_command

# pylint: disable=line-too-long

cli_command(__name__, 'project deployment-pipeline browse',
            'azure.cli.command_modules.project.custom#browse_pipeline')
cli_command(__name__, 'project deployment-pipeline create',
            'azure.cli.command_modules.project.custom#create_deployment_pipeline')
cli_command(__name__, 'project add existing mongo',
            'azure.cli.command_modules.project.custom#add_reference_mongo')
cli_command(__name__, 'project add existing sql',
            'azure.cli.command_modules.project.custom#add_reference_sql')
cli_command(__name__, 'project add existing servicebus',
            'azure.cli.command_modules.project.custom#add_reference_servicebus')
cli_command(__name__, 'project add existing custom',
            'azure.cli.command_modules.project.custom#add_reference_custom')
cli_command(__name__, 'project remove',
            'azure.cli.command_modules.project.custom#remove_reference')

# TODO: Add help for this command
cli_command(__name__, 'project create',
            'azure.cli.command_modules.project.custom#create_project')
cli_command(__name__, 'project delete',
            'azure.cli.command_modules.project.custom#delete_project')

# InnerLoop Commands
cli_command(__name__, 'project up',
            'azure.cli.command_modules.project.custom#service_up')
cli_command(__name__, 'project down',
            'azure.cli.command_modules.project.custom#service_down')
cli_command(__name__, 'project attach',
            'azure.cli.command_modules.project.custom#service_attach')
cli_command(__name__, 'project service list',
            'azure.cli.command_modules.project.custom#service_list')

# Environment Commands
cli_command(__name__, 'project environment add',
            'azure.cli.command_modules.project.custom#add_environment')
cli_command(__name__, 'project environment delete',
            'azure.cli.command_modules.project.custom#delete_environment')
cli_command(__name__, 'project environment list',
            'azure.cli.command_modules.project.custom#list_environment')
cli_command(__name__, 'project environment current get',
            'azure.cli.command_modules.project.custom#get_current_environment')
cli_command(__name__, 'project environment current set',
            'azure.cli.command_modules.project.custom#set_current_environment')
