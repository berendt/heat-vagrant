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

_defaults = {
    'instance': {
        'flavor': 'm1.tiny',
        'image': None,
        'volume': False,
        'username': 'root',
    },
    'network': {
        'cidr': None,
        'external': None,
    }
}


def get_defaults(resource_type):
    #return _defaults.get(resource_type, {}).copy()
    return _defaults.get(resource_type, {})
