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
OpenSwitch Test for vlan related configurations.
"""

from __future__ import unicode_literals, absolute_import
from __future__ import print_function, division

from pytest import mark

from .helpers import wait_until_interface_up


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


@mark.skip(True, reason='The openswitch image does not work consistently.')
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

    p7 = ops1.ports['7']
    p8 = ops1.ports['8']

    # Mark interfaces as enabled
    # Note: It is possible that this test fails here with
    #       pexpect.exceptions.TIMEOUT. There not much we can do, OpenSwitch
    #       may have a race condition or something that makes this command to
    #       freeze or to take more than 60 seconds to complete.
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
        ctx.vlan_access('8')

    with ops1.libs.vtysh.ConfigInterface('8') as ctx:
        ctx.vlan_access('8')

    # Wait until interfaces are up
    for portlbl in ['7', '8']:
        wait_until_interface_up(ops1, portlbl)

    # Assert vlan status
    vlan_status = ops1.libs.vtysh.show_vlan('8').get('8')
    assert vlan_status is not None
    assert vlan_status['vlan_id'] == '8'
    assert vlan_status['status'] == 'up'
    assert vlan_status['reason'] == 'ok'
    assert sorted(vlan_status['ports']) == [p7, p8]

    # Configure host interfaces
    hs1.libs.ip.interface('1', addr='10.0.10.1/24', up=True)
    hs2.libs.ip.interface('1', addr='10.0.10.2/24', up=True)

    # Test ping
    ping = hs1.libs.ping.ping(1, '10.0.10.2')
    assert ping['transmitted'] == ping['received'] == 1
