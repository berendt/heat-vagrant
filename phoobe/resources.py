# based on https://github.com/stackforge/flame/blob/master/flameclient/flame.py

template_skeleton = '''
heat_template_version: 2013-05-23
description: Generated template
parameters:
resources:
'''

class Resource(object):
    """Describes an OpenStack resource."""

    def __init__(self, name, type, id=None, properties=None):
        self.name = name
        self.type = type
        self.id = id
        self.status = 'COMPLETE'
        self.properties = properties or {}
        self.parameters = {}

    def add_parameter(self, name, description, parameter_type='string',
                      constraints=None, default=None):
        data = {
            'type': parameter_type,
            'description': description,
        }

        # (arezmerita) disable cause heat bug #1314240
        # if constraints:
        #    data['constraints'] = constraints
        if default:
            data['default'] = default

        self.parameters[name] = data

    @property
    def template_resource(self):
        return {
            self.name: {
                'type': self.type,
                'properties': self.properties
            }
        }

    @property
    def template_parameter(self):
        return self.parameters

    @property
    def stack_resource(self):
        if self.id is None:
            return {}
        return {
            self.name: {
                'status': self.status,
                'name': self.name,
                'resource_data': {},
                'resource_id': self.id,
                'action': 'CREATE',
                'type': self.type,
                'metadata': {}
            }
        }
