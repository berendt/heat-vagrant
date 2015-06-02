import logging
import os
import yaml

import networkx as nx

from phoobe import defaults

class Environment(object):

    log = logging.getLogger(__name__)

    def __init__(self, filename='environment.yaml', name='phoobe'):
        self._name = name
        self._filename = filename
        self._networks = {}
        self._instances = {}
        self._provisioners = {}
        self._object_tree = nx.DiGraph()

        self._load_configuration_from_file()
        self._load_networks()
        self._load_instances()
        self._load_provisioners()

    def _load_configuration_from_file(self):
        self._data = yaml.load(open(self._filename, 'r'))
        self._defaults = self._data.get('defaults', {})

    def _apply_defaults(self, resource_type, resource):
        global_defaults = defaults.get_defaults(resource_type).copy()
        environment_defaults = self._defaults.get(resource_type, {})
        global_defaults.update(environment_defaults)
        global_defaults.update(resource)
        return global_defaults

    def _load_provisioners(self):
        for provisioner_name in self._data.get('provisioners', {}):
            provisioner = self._data['provisioners'][provisioner_name]
            self._provisioners[provisioner_name] = provisioner

    def _load_instances(self):
        for instance_name in self._data.get('instances', {}):
            instance = self._data['instances'][instance_name]
            instance = self._apply_defaults('instance', instance)
            if not 'name' in instance:
                instance['name'] = instance_name
            self.log.debug("loaded instance '%s': %s" % (instance_name, instance))

            for network_name in instance.get('networks', [instance['network']]):
                self.log.debug("adding instance '%s' to network '%s'" % (instance_name, network_name))

            self._instances[instance_name] = instance

    def _load_networks(self):
        for network_name in self._data.get('networks', {}):
            network = self._data['networks'][network_name]
            network = self._apply_defaults('network', network)
            self._networks[network_name] = network
            self.log.debug("loaded network '%s': %s" % (network_name, network))

    @property
    def networks(self):
        return self._networks

    @property
    def instances(self):
        return self._instances

    @property
    def provisioners(self):
        return self._provisioners

    @property
    def name(self):
        return self._name

    @property
    def filename(self):
        return self._filename
