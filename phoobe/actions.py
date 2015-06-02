import logging
import os
import StringIO
from subprocess import call
import yaml

from attrdict import AttrDict
from cliff.command import Command
from cliff.lister import Lister
import paramiko

from phoobe import template
from phoobe import utils

class EnvironmentNotCreatedException(Exception):
    pass

class EnvironmentAlreadyCreatedException(Exception):
    pass

class GenerateTemplate(Command):

    connection_heat_required = False
    connection_required = False
    environment_required = True

    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(GenerateTemplate, self).get_parser(prog_name)
        parser.add_argument('--filename', default='environment.hot.yaml')
        parser.add_argument('--standalone', default=False, action='store_true')
        parser.add_argument('--use-softwareconfig', default=False, action='store_true')
        return parser

    def take_action(self, parsed_args):
        t = template.Template(self.app.environment, standalone=parsed_args.standalone, use_softwareconfig=parsed_args.use_softwareconfig)
        with open(parsed_args.filename, 'w+') as fp:
            fp.write(t.content)


class Up(Command):

    connection_heat_required = True
    connection_required = False
    environment_required = True

    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(Up, self).get_parser(prog_name)
        parser.add_argument('--use-softwareconfig', default=False, action='store_true')
        return parser

    def take_action(self, parsed_args):
        if self.app.environment.name in self.app.cache:
            self.log.error("environment '%s' already created" % self.app.environment.name)
            raise EnvironmentAlreadyCreatedException()

        try:
            t = template.Template(self.app.environment, self.app.connection, standalone=True, use_softwareconfig=parsed_args.use_softwareconfig)
            fields = {
                'stack_name': self.app.environment.name,
                'template': t.content,
            }
            result = self.app.connection_heat.stacks.create(**fields)
            self.app.cache[self.app.environment.name] = {
                'id': result['stack']['id'],
                'filename': self.app.environment.filename,
                'name': self.app.environment.name
            }
        except template.ExternalNetworkNotFoundException as e:
            self.log.error("external network '%s' not found" % e)
        except template.ProvisionerNotDefinedException as e:
            self.log.error("provisioner '%s' not defined" % e)


class EnableSsh(object):

    def prepare_ssh_connections(self):
        self.addresses = {}
        stack = self.app.connection_heat.stacks.get(self.app.environment.name)
        for output in stack.outputs:
            if output['output_key'].startswith('floatingip_'):
                self.addresses[output['output_key'][11:]] = output['output_value']
            if output['output_key'] == 'private_ssh_key':
                self.private_ssh_key = paramiko.RSAKey.from_private_key(StringIO.StringIO(output['output_value']))
                with open('.private_ssh_key', 'w+') as fp:
                    fp.write(output['output_value'])
                os.chmod('.private_ssh_key', 0600)


    def get_paramiko_connection(self, address, username):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(address, username=username, pkey=self.private_ssh_key)
        return ssh


class ListEnvironments(Lister):

    connection_heat_required = True
    connection_required = False
    environment_required = False

    log = logging.getLogger(__name__)

    def take_action(self, parsed_args):
        columns = (
            'id',
            'name',
            'filename',
        )

        return (columns,
                (utils.get_item_properties(AttrDict(s), columns)
                for s in self.app.cache.values() if len(s) > 0))


class Ssh(Command, EnableSsh):

    connection_heat_required = True
    connection_required = True
    environment_required = True

    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(Ssh, self).get_parser(prog_name)
        parser.add_argument('instance', nargs='?', default=None)
        return parser

    def take_action(self, parsed_args):
        if not self.app.environment.name in self.app.cache:
            self.log.error("environment '%s' not created" % self.app.environment.name)
            raise EnvironmentNotCreatedException()

        if not parsed_args.instance:
            instance_name = self.app.environment.instances.keys()[0]
            self.log.error("no instance specified, using instance '%s'" % instance_name)
        else:
            instance_name = parsed_args.instance

        if not instance_name in self.app.environment.instances:
            self.log.error("instance '%s' not found" % instance_name)
            return

        self.addresses = {}
        stack = self.app.connection_heat.stacks.get(self.app.environment.name)
        for output in stack.outputs:
            if output['output_key'].startswith('floatingip_'):
                self.addresses[output['output_key'][11:]] = output['output_value']
            if output['output_key'] == 'private_ssh_key':
                private_ssh_key = output['output_value']
                with open('.private_ssh_key', 'w+') as fp:
                    fp.write(private_ssh_key)
                os.chmod('.private_ssh_key', 0600)

        username = self.app.environment.instances[instance_name]['username']
        call("ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -i .private_ssh_key %s@%s" % (username, self.addresses[instance_name]), shell=True)


class Provision(Command, EnableSsh):

    connection_heat_required = True
    connection_required = False
    environment_required = True

    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
       parser = super(Provision, self).get_parser(prog_name)
       parser.add_argument('--use-softwareconfig', default=False, action='store_true')
       return parser

    def take_action(self, parsed_args):
        if not self.app.environment.name in self.app.cache:
            self.log.error("environment '%s' not created" % self.app.environment.name)
            raise EnvironmentNotCreatedException()

        self.prepare_ssh_connections()

        # check if there are provisioners assigned/available
        if not self.app.environment.provisioners:
            self.log.warn('no provisioners defined')
            return

        # check if environment is up and running

        # check if instances are accessible by SSH
        for instance_name in self.app.environment.instances:
            self.log.debug("checking SSH access to instances '%s'" % instance_name)
            username = self.app.environment.instances[instance_name]['username']
            ssh = self.get_paramiko_connection(self.addresses[instance_name], username)
            channel = ssh.invoke_shell()
            stdin, stdout, stderr = ssh.exec_command('hostname')
            ssh.close()

        # run provisioners
        for provisioner_name in self.app.environment.provisioners:
            provisioner = self.app.environment.provisioners[provisioner_name]
            self.log.info("running provisioner '%s' of type '%s'" % (provisioner_name, provisioner['type']))
            if provisioner['type'] == 'shell' and parsed_args.use_softwareconfig:
                self.log.warn("skipping provisioner '%s' of type 'shell', included in stack" % provisioner_name)
            elif provisioner['type'] == 'shell':
                for instance_name in self.app.environment.instances:
                    if not provisioner_name in self.app.environment.instances[instance_name]['provisioners']:
                        next
                    username = self.app.environment.instances[instance_name]['username']
                    environment_path = os.path.dirname(self.app.options.environment_file)
                    call("ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -i .private_ssh_key %s@%s 'bash -s' < %s" % (username, self.addresses[instance_name], os.path.join(environment_path, provisioner['path'])), shell=True)
                    #with open(provisioner['path']) as fp:
                    #    ssh = self.get_paramiko_connection(self.addresses[instance_name], username)
                    #    channel = ssh.invoke_shell()
                    #    stdin, stdout, stderr = ssh.exec_command(fp.read())
                    #    for line in stdout.readlines():
                    #        self.log.info('[%s, %s]: %s' % (instance_name, provisioner_name, line.strip()))
                    #    ssh.close()


class Destroy(Command):

    connection_heat_required = True
    connection_required = True
    environment_required = True

    log = logging.getLogger(__name__)

    def take_action(self, parsed_args):
        if not self.app.environment.name in self.app.cache:
            self.log.error("environment '%s' not created" % self.app.environment.name)
            raise EnvironmentNotCreatedException()
        stack_id = self.app.cache[self.app.environment.name]['id']
        self.app.connection_heat.stacks.delete(stack_id=stack_id)

        # check for deletion here...

        del self.app.cache[self.app.environment.name]



class Resources(Lister):

    connection_heat_required = True
    connection_required = True
    environment_required = True

    log = logging.getLogger(__name__)

    def take_action(self, parsed_args):
        if not self.app.environment.name in self.app.cache:
            self.log.error("environment '%s' not created" % self.app.environment.name)
            raise EnvironmentNotCreatedException()

        columns = (
            'resource_type',
            'resource',
            'status',
        )
        resources = self.app.connection_heat.resources.list(self.app.environment.name)
        result = {}
        for resource in resources:
            result[resource.resource_name] = {
                'resource': resource.resource_name,
                'resource_type': resource.resource_type,
                'status': resource.resource_status,
            }

        return (columns,
                (utils.get_item_properties(AttrDict(s), columns) for s in result.values()))


class Status(Lister):

    connection_heat_required = True
    connection_required = True
    environment_required = True

    log = logging.getLogger(__name__)

    def take_action(self, parsed_args):
        columns = (
            'instance',
            'status',
            'public_address',
        )
        stack = self.app.connection_heat.stacks.get(self.app.environment.name)
        resources = self.app.connection_heat.resources.list(self.app.environment.name)
        result = {}
        for resource in resources:
            if resource.resource_type == 'OS::Nova::Server':
                result[resource.resource_name] = {
                    'status': resource.resource_status,
                    'instance': resource.resource_name,
                    'public_address': '-'
                }
        if stack.stack_status == 'CREATE_COMPLETE':
            for output in stack.outputs:
                if output['output_key'].startswith('floatingip_'):
                    result[output['output_key'][11:]]['public_address'] = output['output_value']

        return (columns,
                (utils.get_item_properties(AttrDict(s), columns) for s in result.values()))


class ListFlavors(Lister):

    connection_heat_required = False
    connection_required = True
    environment_required = False

    log = logging.getLogger(__name__)

    def take_action(self, parsed_args):
        columns = (
            'ID',
            'Name',
            'vcpus',
            'ram',
            'disk',
        )

        data = self.app.connection.compute.flavors()
        return (columns,
                (utils.get_item_properties(s, columns) for s in data))


class ListImages(Lister):

    connection_heat_required = False
    connection_required = True
    environment_required = False

    log = logging.getLogger(__name__)

    def take_action(self, parsed_args):
        columns = (
            'ID',
            'Name',
        )

        data = self.app.connection.compute.images()
        return (columns,
                (utils.get_item_properties(s, columns)
                for s in data))


class ListExternalNetworks(Lister):

    connection_heat_required = False
    connection_required = True
    environment_required = False

    log = logging.getLogger(__name__)

    def take_action(self, parsed_args):
        columns = (
            'ID',
            'Name',
            'subnets',
        )

        return (columns,
                (v for s in self.app.connection.network.networks()
                 for v in (utils.get_item_properties(s, columns,
                 connection=self.app.connection,
                 filters={'router:external': True}),) if v))


class ListInternalNetworks(Lister):

    connection_heat_required = False
    connection_required = True
    environment_required = False

    log = logging.getLogger(__name__)

    def take_action(self, parsed_args):
        columns = (
            'ID',
            'Name',
            'subnets',
        )

        return (columns,
                (v for s in self.app.connection.network.networks() for v in (utils.get_item_properties(s, columns, connection=self.app.connection, filters={'router:external': False}),) if v))
