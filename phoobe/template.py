import os
from pdb import set_trace as bp
import yaml
import pyaml

from openstack.orchestration.v1 import stack

_skeleton_template = '''
heat_template_version: '2013-05-23'
description: Phoobe generated heat template
parameters:
resources:
outputs:
'''

class ExternalNetworkNotFoundException(Exception):
    pass

class ProvisionerNotDefinedException(Exception):
    pass

class Resource(object):

    def __init__(self, name, type, properties=None):
        self._name = name
        self._type = type
        self._properties = properties or {}

    def add_property(self):
        self._properties

    @property
    def data(self):
        return {
            self._name: {
                'type': self._type,
                'properties': self._properties
            }
        }


class Template(object):

    def __init__(self, environment, connection=None, standalone=True, use_softwareconfig=False):
        self._environment = environment
        self._connection = connection
        self._standalone = standalone
        self._use_softwareconfig = use_softwareconfig
        self._template = yaml.load(_skeleton_template)
        self._template['resources'] = {}
        self._template['parameters'] = {}
        self._template['outputs'] = {}
        self._initialize()

    def _add_parameter(self, name, type, description):
        self._template['parameters'][name] = {
            'type': type,
            'description': description
        }

    def _add_output(self, name, value, description):
        self._template['outputs'][name] = {
            'value': value, 
            'description': description
        }

    def _add_resource(self, resource):
        self._template['resources'].update(resource.data)

    @property
    def dictionary(self):
        return self._template

    def _initialize(self):

        environment_name = self._environment.name

        # ssh keypair
        keypair_name = 'keypair'
        keypair_properties = {
            'name': '%s_%s' % (environment_name, keypair_name),
            'save_private_key': True
        }
        keypair = Resource(keypair_name, 'OS::Nova::KeyPair', keypair_properties)
        self._add_resource(keypair)
        self._add_output('private_ssh_key', '{ get_attr: [ %s, private_key ] }' % keypair_name, 'Private SSH key')

        # security groups
        security_group_name = 'security_group'
        security_group_properties = {
            'name': '%s_%s' % (environment_name, security_group_name),
            'description': 'Allow SSH and ICMP',
            'rules': [
                {'protocol': 'icmp'},
                {'protocol': 'tcp',
                 'port_range_min': 22,
                 'port_range_max': 22}
            ]
        }
        security_group = Resource(security_group_name, 'OS::Neutron::SecurityGroup', security_group_properties)
        self._add_resource(security_group)

        # networks
        external_network = None
        router_name = 'router'

        for network_name in self._environment.networks:
            data = self._environment.networks[network_name]
            net_name = 'net_' + network_name
            net_properties = {
                'name': '%s_%s' % (environment_name, network_name)
            }
            net = Resource(net_name, 'OS::Neutron::Net', net_properties)
            self._add_resource(net)

            subnet_name = 'subnet_' + network_name
            # check if this is a valid CIDR
            subnet_properties = {
                'name': '%s_%s' % (environment_name, subnet_name),
                'cidr': data['cidr'],
                'network_id': '{ get_resource: %s }' % net_name
            }
            subnet = Resource(subnet_name, 'OS::Neutron::Subnet', subnet_properties)
            self._add_resource(subnet)

            if data.get('external', None) or data.get('router', False):
                # NOTE: at the moment only one external network is possible
                external_network = data['external']
                router_interface_name = 'router_interface_' + subnet_name
                router_interface_properties = {
                    'router_id': '{ get_resource: %s }' % router_name,
                    'subnet_id': '{ get_resource: %s }' % subnet_name
                }
                router_interface = Resource(router_interface_name, 'OS::Neutron::RouterInterface', router_interface_properties)
                self._add_resource(router_interface)

        router_properties = {
            'name': '%s_%s' % (environment_name, router_name)
        }
        if external_network:
            if self._standalone:
                external_network_id = self._connection.network.find_network(external_network)
                if not external_network_id:
                    raise ExternalNetworkNotFoundException(external_network)
                else:
                    router_properties['external_gateway_info'] = {'network': external_network_id['id']}
            else:
                router_properties['external_gateway_info'] = {'network': '{ get_param: external_network }'}

        router = Resource(router_name, 'OS::Neutron::Router', router_properties)
        self._add_resource(router)

        # provisioner
        for provisioner_name in self._environment.provisioners:
            provisioner = self._environment.provisioners[provisioner_name]
            if provisioner['type'] == 'shell' and self._use_softwareconfig:
                config = ''
                if 'path' in provisioner:
                    script_path = os.path.join(os.path.dirname(self._environment.filename), provisioner['path'])
                    with open(script_path) as fp:
                        config = fp.read()
                software_config_name = 'software_config_' + provisioner_name
                software_config_properties = {
#                    'name': '%s_%s' % (environment_name, software_config_name),
                    'group': 'script',
                    'config': config
                }
                software_config = Resource(software_config_name, 'OS::Heat::SoftwareConfig', software_config_properties)
                self._add_resource(software_config)

        # instances
        for instance_name in self._environment.instances:
            data = self._environment.instances[instance_name]
            instance_properties = {
                'name': '%s_%s' % (environment_name, instance_name),
                'flavor': data['flavor'],
                'key_name': '{ get_resource: keypair }',
                'networks': []
            }

            if data.get('volume'):
                volume_name = 'volume_' + instance_name
                volume_properties = {
                    'name': '%s_%s' % (environment_name, volume_name),
                    'image': data['image'],
                    'size': data['volume']
                }
                volume = Resource(volume_name, 'OS::Cinder::Volume', volume_properties)
                self._add_resource(volume)
                block_device_mapping = [{
                    'device_name': 'vda',
                    'delete_on_termination': True,
                    'volume_id': '{ get_resource: %s }' % volume_name
                }]
                instance_properties['block_device_mapping'] = block_device_mapping
            else:
                instance_properties['image'] = data['image']

            for network in data.get('networks', [data['network']]):
                if isinstance(network, str):
                    network_name = network
                    address = None
                elif isinstance(network, dict):
                    network_name = network.iterkeys().next()
                    address = network[network_name]
                port_name = 'port_' + instance_name + '_' + network_name
                port_properties = {
                    'name': '%s_%s' % (environment_name, port_name),
                    'network_id': '{ get_resource: net_%s }' % network_name,
                    'security_groups': ['default', '{ get_resource: security_group }']
                }

                fixed_ips = {
                    'subnet_id': '{ get_resource: subnet_%s }' % network_name
                }
                if address:
                    # check if this is a valid ip address for this subnet
                    fixed_ips['ip_address'] = address

                port_properties['fixed_ips'] = [fixed_ips]
                port = Resource(port_name, 'OS::Neutron::Port', port_properties)
                self._add_resource(port)
                instance_properties['networks'].append({'port': '{ get_resource: %s }' % port_name})

            if not external_network and data.get('external', False):
                external_network = data.get('external')

            if external_network:
                floatingip_name = 'floatingip_' + instance_name
                floatingip_properties = {
                    'port_id': '{ get_resource: port_%s_%s}' % (instance_name, data['network'])
                }
                if self._standalone:
                    external_network_id = self._connection.network.find_network(external_network)
                    if not external_network_id:
                        raise ExternalNetworkNotFoundException(external_network)
                    else:
                        floatingip_properties['floating_network_id'] = external_network_id['id']
                else:
                    self._add_parameter('external_network', 'string', 'UUID of the external network')
                    floatingip_properties['floating_network_id'] = '{ get_param: external_network }'
                floatingip = Resource(floatingip_name, 'OS::Neutron::FloatingIP', floatingip_properties)
                self._add_resource(floatingip)
                self._add_output(
                    'floatingip_' + instance_name,
                    '{ get_attr: [ %s, floating_ip_address ] }' % floatingip_name,
                    'Floating IP address of instance %s' % instance_name
                )

            # provisoners
            for provisioner_name in data.get('provisioners', []):
                if not provisioner_name in self._environment.provisioners:
                    raise(ProvisionerNotDefinedException(provisioner_name))
                provisioner = self._environment.provisioners[provisioner_name]
                if provisioner['type'] == 'shell' and self._use_softwareconfig:
                    software_deployment_name = 'software_deployment_%s_%s' % (provisioner_name, instance_name)
                    software_deployment_properties = {
#                        'name': '%s_%s' % (environment_name, software_deployment_name),
                        'config': '{ get_resource: software_config_%s }' % provisioner_name,
                        'server': '{ get_resource: %s }' % instance_name
                    }
                    software_deployment = Resource(software_deployment_name, 'OS::Heat::SoftwareDeployment', software_deployment_properties)
                    self._add_resource(software_deployment)
                    instance_properties['user_data_format'] = 'SOFTWARE_CONFIG'

            instance = Resource(instance_name, 'OS::Nova::Server', instance_properties)
            self._add_resource(instance)

    @property
    def content(self):
        result = pyaml.dump(self._template)
        result = result.replace("'{", "{").replace("}'", "}")
        return result
