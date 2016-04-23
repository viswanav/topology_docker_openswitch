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
Custom Topology Docker Node for OpenSwitch.

    http://openswitch.net/
"""

from __future__ import unicode_literals, absolute_import
from __future__ import print_function, division

from shutil import copy
from json import loads, dumps
from logging import getLogger
from subprocess import Popen, PIPE
from os.path import dirname, normpath, abspath, join

from topology_docker.node import DockerNode
from topology_docker.shell import DockerShell, DockerBashShell


log = getLogger(__name__)


class OpenSwitchNode(DockerNode):
    """
    Custom OpenSwitch node for the Topology Docker platform engine.

    This custom node loads an OpenSwitch image and has vtysh as default
    shell (in addition to bash).

    See :class:`topology_docker.node.DockerNode`.

    :param bool skip_boot_checks: Skip checks to determine if the image is
     ready to be tested.

     .. warning::

        Disabling this checks can cause commands to fail and race conditions
        to crawl your tests. You have been warned.

    :param int boot_checks_timeout: Timeout for a check to be ready in seconds.
    """

    def __init__(
            self, identifier,
            image='topology/ops:latest', binds=None,
            skip_boot_checks=False, boot_checks_timeout=30,
            **kwargs):

        # Add binded directories
        container_binds = [
            '/dev/log:/dev/log',
            '/sys/fs/cgroup:/sys/fs/cgroup:ro'
        ]
        if binds is not None:
            container_binds.append(binds)

        super(OpenSwitchNode, self).__init__(
            identifier, image=image, command='/sbin/init',
            binds=';'.join(container_binds), hostname='switch',
            **kwargs
        )

        # Save other parameters
        self._skip_boot_checks = skip_boot_checks
        self._boot_checks_timeout = boot_checks_timeout

        # Add vtysh (default) shell
        # FIXME: Create a subclass to handle better the particularities of
        # vtysh, like prompt setup etc.
        self._shells['vtysh'] = DockerShell(
            self.container_id, 'vtysh',
            '(^|\n)switch(\([\-a-zA-Z0-9]*\))?#'
        )

        # Add bash shells
        initial_prompt = '(^|\n).*[#$] '

        self._shells['bash'] = DockerBashShell(
            self.container_id, 'bash',
            initial_prompt=initial_prompt
        )
        self._shells['bash_swns'] = DockerBashShell(
            self.container_id, 'ip netns exec swns bash',
            initial_prompt=initial_prompt
        )
        self._shells['vsctl'] = DockerBashShell(
            self.container_id, 'bash',
            initial_prompt=initial_prompt,
            prefix='ovs-vsctl ', timeout=60
        )

    def notify_post_build(self):
        """
        Get notified that the post build stage of the topology build was
        reached.

        See :meth:`DockerNode.notify_post_build` for more information.
        """
        super(OpenSwitchNode, self).notify_post_build()
        self._setup_system()

    def _setup_system(self):
        """
        Setup OpenSwitch image.
        """
        ports_file = join(self.shared_dir, 'ports.json')

        # Write boot script input data
        with open(ports_file, 'w') as fd:
            fd.write(dumps(self.ports))

        # Write boot script
        root = dirname(normpath(abspath(__file__)))
        source = join(root, 'system_setup')
        destination = join(self.shared_dir, 'system_setup')
        copy(source, destination)

        # Execute boot script
        cmd = [
            'docker', 'exec', self.container_id,
            'python', '/tmp/system_setup',
            '--available', '/tmp/ports.json'
        ]

        if self._skip_boot_checks:
            cmd.append('--skip-boot-checks')

        # log.info('Booting OpenSwitch image {}. Please wait...'.format())
        setup = Popen(cmd, stdin=PIPE, stdout=PIPE)
        stdout, stderr = setup.communicate()
        if stdout:
            log.info(stdout)
        if setup.returncode != 0:
            log.fatal(stderr)
            raise Exception(
                'Boot script failed for node {}'.format(
                    self.identifier
                )
            )
        if stderr:
            log.warning(
                'Boot script registered stderr output without '
                'failing on node {}'.format(
                    self.identifier
                )
            )
            log.debug(stderr)

        # Read back port mapping
        with open(ports_file, 'r') as fd:
            self.ports.update(loads(fd.read()))

    def set_port_state(self, portlbl, state):
        """
        Set the given port label to the given state.

        See :meth:`DockerNode.set_port_state` for more information.
        """
        iface = self.ports[portlbl]
        state = 'up' if state else 'down'

        not_in_netns = self._docker_exec('ls /sys/class/net/').split()
        prefix = '' if iface in not_in_netns else 'ip netns exec swns'

        command = '{prefix} ip link set dev {iface} {state}'.format(**locals())
        self._docker_exec(command)


__all__ = ['OpenSwitchNode']
