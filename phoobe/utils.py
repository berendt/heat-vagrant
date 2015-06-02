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

import os

# source: https://github.com/openstack/oslo-incubator/blob/master/openstack/common/cliutils.py

def env(*args, **kwargs):
    """Returns the first environment variable set.
    If all are empty, defaults to '' or keyword arg `default`.
    """
    for arg in args:
        value = os.environ.get(arg)
        if value:
            return value
    return kwargs.get('default', '')


def get_item_properties(item, fields, connection=None, filters={}):
    """Return a tuple containing the item properties.

    :param item: a single item resource (e.g. Server, Project, etc)
    :param fields: tuple of strings with the desired field names
    :param filters: dictionary with fields to filter
    """

    for filter in filters.keys():
        name = filter.lower().replace(' ', '_')
        data = getattr(item, name, '')
        if data is not filters[filter]:
            return tuple()

    row = []

    for field in fields:
        name = field.lower().replace(' ', '_')

        if name == 'subnets' and connection:
            subnets = []
            for subnet in getattr(item, name, ''):
                subnets.append(connection.network.get_subnet(subnet).cidr)
            data = str.join(", ", subnets)
        else:
            data = getattr(item, name, '')

        row.append(data)
    return tuple(row)
