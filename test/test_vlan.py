# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Hewlett Packard Enterprise Development LP
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
OpenSwitch Test for vlan related configurations.
"""

from __future__ import unicode_literals, absolute_import
from __future__ import print_function, division

from re import search


TOPOLOGY = """
# +-------+                    +-------+
# |       |     +--------+     |       |
# |  hs1  <----->  ops1  <----->  hs2  |
# |       |     +--------+     |       |
# +-------+                    +-------+

# Nodes
[type=openswitch name="OpenSwitch 1"] ops1
[type=host name="Host 1"] hs1
[type=host name="Host 2"] hs2

# Links
hs1:1 -- ops1:7
ops1:8 -- hs2:1
"""


def test_vlan(topology):
    """
    Test that a vlan configuration is functional with a OpenSwitch switch.

    Build a topology of one switch and two hosts and connect the hosts to the
    switch. Setup a VLAN for the ports connected to the hosts and ping from
    host 1 to host 2.
    """
    ops1 = topology.get('ops1')
    hs1 = topology.get('hs1')
    hs2 = topology.get('hs2')

    assert ops1 is not None
    assert hs1 is not None
    assert hs2 is not None

    p8 = ops1.ports['8']
    p7 = ops1.ports['7']

    # Mark interfaces as enabled
    iface_enabled = ops1(
        'set interface {p7} user_config:admin=up'.format(**locals()),
        shell='vsctl'
    )
    assert not iface_enabled

    iface_enabled = ops1(
        'set interface {p8} user_config:admin=up'.format(**locals()),
        shell='vsctl'
    )
    assert not iface_enabled

    # Configure interfaces
    with ops1.libs.vtysh.ConfigInterface('7') as ctx:
        ctx.no_routing()
        ctx.no_shutdown()

    with ops1.libs.vtysh.ConfigInterface('8') as ctx:
        ctx.no_routing()
        ctx.no_shutdown()

    # Configure vlan and switch interfaces
    with ops1.libs.vtysh.ConfigVlan('8') as ctx:
        ctx.no_shutdown()

    with ops1.libs.vtysh.ConfigInterface('7') as ctx:
        ctx.vlan_access(8)

    with ops1.libs.vtysh.ConfigInterface('8') as ctx:
        ctx.vlan_access(8)

    # FIXME: Use library
    ops1('show interface {p7}'.format(**locals()))
    ops1('show interface {p8}'.format(**locals()))

    # FIXME: Use library
    vlan_result = ops1('show vlan 8')

    assert search(
        r'8\s+(vlan|VLAN)8\s+up\s+ok\s+({p8}|{p7}),\s*({p7}|{p8})'.format(
            **locals()
        ),
        vlan_result
    )

    # Configure host interfaces
    hs1.libs.ip.interface('1', addr='10.0.10.1/24', up=True)
    hs2.libs.ip.interface('1', addr='10.0.10.2/24', up=True)

    # Test ping
    ping = hs1.libs.ping.ping(1, '10.0.10.2')

    # Show if interface ever brought up
    ops1('show interface {p7}'.format(**locals()))
    ops1('show interface {p8}'.format(**locals()))

    assert ping['transmitted'] == ping['received'] == 1
