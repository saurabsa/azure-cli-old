# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------

import os
import random
import socket
import string
import sys
import threading
from subprocess import PIPE, CalledProcessError, Popen, check_output
from time import sleep

import azure.cli.command_modules.project.naming as naming
import azure.cli.command_modules.project.settings as settings
import azure.cli.core.azlogging as azlogging  # pylint: disable=invalid-name
from azure.cli.core._util import CLIError


logger = azlogging.get_az_logger(__name__)  # pylint: disable=invalid-name


def get_random_registry_name():
    """
    Gets a random name for the Azure
    Container Registry
    """
    return get_random_string(only_letters=True)


def get_random_string(length=6, only_letters=False):
    """
    Gets a random lowercase string made
    from ascii letters and digits
    """
    random_string = ''
    if only_letters:
        random_string = ''.join(random.choice(string.ascii_lowercase)
                                for _ in range(length))
    else:
        random_string = ''.join(random.choice(string.ascii_lowercase + string.digits)
                                for _ in range(length))
    return random_string


def get_random_project_name():
    """
    Gets a random project name
    """
    return naming.get_random_name()


def writeline(message):
    """
    Writes a message to stdout on a newline
    """
    sys.stdout.write(message + '\n')


def write(message='.'):
    """
    Writes a message to stdout
    """
    sys.stdout.write(message)
    sys.stdout.flush()


def get_public_ssh_key_contents(
        file_name=os.path.join(os.path.expanduser('~'), '.ssh', 'id_rsa.pub')):
    """
    Gets the public SSH key file contents
    """
    contents = None
    with open(file_name) as ssh_file:
        contents = ssh_file.read()
    return contents


def get_remote_host(dns_prefix, location):
    """
    Provides a remote host according to the passed dns_prefix and location.
    """
    return '{}.{}.cloudapp.azure.com'.format(dns_prefix, location)


def get_command_output(command, tries=1):
    """
    Executes a command and provides the output.
    """
    retry = 0
    output = None
    ERROR_CODE = 1
    while retry < tries:
        try:
            output = check_output(command, shell=True,
                                  stderr=PIPE).strip().decode('utf-8')
            if output:
                break
        except CalledProcessError:
            pass
        finally:
            sleep(2)
            retry = retry + 1
    if not output:
        raise CLIError(CalledProcessError(ERROR_CODE, command))

    return output


def execute_command(command, throw=False, tries=1):
    """
    Executes a shell command on a local machine
    """
    return_code = 1
    retry = 0
    while retry < tries:
        with Popen(command, shell=True, stdout=PIPE, stderr=PIPE, bufsize=1, universal_newlines=True) as process:
            for line in process.stdout:
                logger.info('\n' + line)
            for err in process.stderr:
                logger.debug(err)
            # Wait for the process to finish to get the return code
            return_code = process.wait()
        if return_code == 0:
            break

        sleep(2)
        retry = retry + 1

    if throw and return_code != 0:
        raise CLIError(CalledProcessError(
            return_code, command))

    return return_code


def _get_random_port():
    """
    Gets a random, available local port
    """
    socket_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    socket_client.bind(('', 0))
    socket_client.listen(1)
    port = socket_client.getsockname()[1]
    socket_client.close()
    return port


def get_available_local_port():
    """
    Gets a random, available local port that's
    not taken by any service yet
    """
    mindaro_settings = settings.Mindaro()
    port = _get_random_port()
    retries = 5
    retry = 0

    while mindaro_settings.is_port_taken(port) and retry < retries:
        logger.debug('Port {} is taken. Picking another port.'.format(port))
        sleep(1)
        port = _get_random_port()
        retry = retry + 1
    return port


def is_port_available(port):
    """
    Checks if the port is available
    """
    if not port:
        return True

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # if result is 0, port is taken
    result = sock.connect_ex(('127.0.0.1', port))
    return result != 0


class Process(object):
    """
    Process object runs a thread in the backgroud to print the
    status of an execution for which the output is not displayed to stdout.
    It prints '.' to stdout till the process is runnin.
    """

    __process_stop = False  # To stop the thread
    wait_time_sec = 15

    def __init__(self, quiet=False):
        self._quiet = quiet
        self.__long_process_start()

    def __process_output(self, message='.'):
        while not self.__process_stop:
            if not self._quiet:
                write(message)
            sleep(self.wait_time_sec)

    def __long_process_start(self):
        self.__process_stop = False
        thread = threading.Thread(
            target=self.__process_output, args=(), kwargs={})
        thread.start()

    def process_stop(self):
        self.__process_stop = True
