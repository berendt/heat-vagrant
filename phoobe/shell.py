# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import logging
import os
import shelve
import sys
import warnings
import yaml

import appdirs
from cliff import app
from cliff import command
from cliff import commandmanager
from heatclient.client import Client
from openstack import connection
from openstack.auth import service_filter
import os_client_config

from phoobe import environment
from phoobe import utils

# based on https://github.com/openstack/python-openstackclient/blob/master/openstackclient/shell.py

class PhoobeShell(app.App):

    connection = None
    environment = None

    log = logging.getLogger(__name__)

    def __init__(self):
        super(PhoobeShell, self).__init__(
            description='phoobe',
            version='0.1',
            command_manager=commandmanager.CommandManager('phoobe.shell'),
            )

    def configure_logging(self):
        super(PhoobeShell, self).configure_logging()
        root_logger = logging.getLogger('')
        if self.options.verbose_level == 0:
            # --quiet
            root_logger.setLevel(logging.ERROR)
            warnings.simplefilter("ignore")
        elif self.options.verbose_level == 1:
            # This is the default case, no --debug, --verbose or --quiet
            root_logger.setLevel(logging.WARNING)
            warnings.simplefilter("ignore")
        elif self.options.verbose_level == 2:
            # One --verbose
            root_logger.setLevel(logging.INFO)
            warnings.simplefilter("once")
        elif self.options.verbose_level >= 3:
            # Two or more --verbose
            root_logger.setLevel(logging.DEBUG)

    def build_option_parser(self, description, version):
        parser = super(PhoobeShell, self).build_option_parser(
            description,
            version)
        parser.add_argument(
            '--os-cloud-config-name',
            metavar='<cloud-config-name>',
            dest='cloud_config_name',
            default='phoobe',
            #default=utils.env('PHOOBE_CLOUD_CONFIG_NAME'),
            help='Cloud name in clouds.yaml (Env: PHOOBE_CLOUD_CONFIG_NAME)',
        )
        parser.add_argument(
            '--configuration-file',
            metavar='<configuration-file>',
            dest='configuration_file',
            default='phoobe.yaml',
            #default=utils.env('PHOOBE_CONFIGURATION_FILE'),
            help='Environment file (Env: PHOOBE_CONFIGURATION_FILE)',
        )
        parser.add_argument(
            '--environment-file',
            metavar='<environment-file>',
            dest='environment_file',
            default='environment.yaml',
            #default=utils.env('PHOOBE_ENVIRONMENT_FILE'),
            help='Environment file (Env: PHOOE_ENVIRONMENT_FILE)',
        )
        parser.add_argument(
            '--environment-name',
            metavar='<environment-name>',
            dest='environment_name',
            default='phoobe',
            #default=utils.env('PHOOBE_ENVIRONMENT_NAME'),
            help='Environment name (Env: PHOOBE_ENVIRONMENT_NAME)',
        )
        return parser

    def initialize_app(self, argv):
        self.log.debug('initialize_app')
        shelve_file = os.path.join(appdirs.user_data_dir('phoobe'), 'phoobe.shelve')
        self.log.debug("initializing shelve file %s" % shelve_file)
        if not os.path.exists(appdirs.user_data_dir('phoobe')):
            os.makedirs(appdirs.user_data_dir('phoobe'))
        self.cache = shelve.open(os.path.join(appdirs.user_data_dir('phoobe'), 'phoobe.shelve'))

        if os.path.exists(self.options.configuration_file):
            configuration = yaml.load(open(self.options.configuration_file))
            if 'cloud_config_name' in configuration:
                self.options.cloud_config_name = configuration['cloud_config_name']

            if 'environment_name' in configuration:
                self.options.environment_name = configuration['environment_name']

            if 'environment_file' in configuration:
                self.options.environment_file = configuration['environment_file']

            if 'use_softwareconfig' in configuration:
                self.options.use_software_config = configuration['use_softwareconfig']

    def prepare_to_run_command(self, cmd):
        self.log.debug('prepare_to_run_command %s', cmd.__class__.__name__)

        if cmd.connection_required or cmd.connection_heat_required:
            osc = os_client_config.OpenStackConfig()
            self.cloud = osc.get_one_cloud(self.options.cloud_config_name, argparse=self.options)
            self.connection = connection.Connection(**self.cloud.config['auth'])

        if cmd.environment_required:
            self.environment = environment.Environment(self.options.environment_file, self.options.environment_name)

        if cmd.connection_heat_required:
            token = self.connection.session.authenticator.auth_plugin.authorize(self.connection.transport)
            heat_service = service_filter.ServiceFilter('orchestration', version='v1')
            self.connection_heat = Client('1', endpoint=token.service_catalog.get_url(heat_service), token=token.auth_token)


    def clean_up(self, cmd, result, err):
        self.log.debug('clean_up %s', cmd.__class__.__name__)
        self.cache.close()
        if err:
            self.log.debug('got an error: %s', err)


def main(argv=sys.argv[1:]):
    return PhoobeShell().run(argv)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
