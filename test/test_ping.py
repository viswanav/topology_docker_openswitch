# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2016 Hewlett Packard Enterprise Development LP
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

"""
OpenSwitch Test for simple ping between nodes.
"""

from __future__ import unicode_literals, absolute_import
from __future__ import print_function, division

from time import sleep

from .helpers import wait_until_interface_up


TOPOLOGY = """
# +-------+                                 +-------+
# |       |     +-------+     +-------+     |       |
# |  hs1  <----->  sw1  <----->  sw2  <----->  hs2  |
# |       |     +-------+     +-------+     |       |
# +-------+                                 +-------+

# Nodes
[type=openswitch name="Switch 1"] sw1
[type=openswitch name="Switch 2"] sw2
[type=host name="Host 1"] hs1
[type=host name="Host 2"] hs2

# Links
hs1:1 -- sw1:3
sw1:4 -- sw2:3
sw2:4 -- hs2:1
"""


def test_ping(topology):
    """
    Set network addresses and static routes between nodes and ping h2 from h1.
    """
    sw1 = topology.get('sw1')
    sw2 = topology.get('sw2')
    hs1 = topology.get('hs1')
    hs2 = topology.get('hs2')

    assert sw1 is not None
    assert sw2 is not None
    assert hs1 is not None
    assert hs2 is not None

    # Configure IP and bring UP host 1 interfaces
    hs1.libs.ip.interface('1', addr='10.0.10.1/24', up=True)

    # Configure IP and bring UP host 2 interfaces
    hs2.libs.ip.interface('1', addr='10.0.30.1/24', up=True)

    # Configure IP and bring UP switch 1 interfaces
    with sw1.libs.vtysh.ConfigInterface('3') as ctx:
        ctx.ip_address('10.0.10.2/24')
        ctx.no_shutdown()

    with sw1.libs.vtysh.ConfigInterface('4') as ctx:
        ctx.ip_address('10.0.20.1/24')
        ctx.no_shutdown()

    # Configure IP and bring UP switch 2 interfaces
    with sw2.libs.vtysh.ConfigInterface('3') as ctx:
        ctx.ip_address('10.0.20.2/24')
        ctx.no_shutdown()

    with sw2.libs.vtysh.ConfigInterface('4') as ctx:
        ctx.ip_address('10.0.30.2/24')
        ctx.no_shutdown()

    # Wait until interfaces are up
    for switch, portlbl in [(sw1, '3'), (sw1, '4'), (sw2, '3'), (sw2, '4')]:
        wait_until_interface_up(switch, portlbl)

    # Set static routes in switches
    sw1.libs.ip.add_route('10.0.30.0/24', '10.0.20.2', shell='bash_swns')
    sw2.libs.ip.add_route('10.0.10.0/24', '10.0.20.1', shell='bash_swns')

    # Set gateway in hosts
    hs1.libs.ip.add_route('default', '10.0.10.2')
    hs2.libs.ip.add_route('default', '10.0.30.2')

    sleep(1)
    ping = hs1.libs.ping.ping(1, '10.0.30.1')
    assert ping['transmitted'] == ping['received'] == 1
