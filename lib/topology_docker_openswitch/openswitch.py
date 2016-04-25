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
from collections import OrderedDict
from os.path import dirname, normpath, abspath, join

from topology_docker.node import DockerNode
from topology_docker.shell import DockerShell, DockerBashShell


log = getLogger(__name__)


class OpenSwitchImageException(Exception):
    """
    Custom typed exception thrown when the image failed to setup.
    """


class OpenSwitchNode(DockerNode):
    """
    Custom OpenSwitch node for the Topology Docker platform engine.

    This custom node loads an OpenSwitch image and has vtysh as default
    shell (in addition to bash).

    See :class:`topology_docker.node.DockerNode`.

    :param int boot_checks_timeout: Timeout (in seconds) for a check to pass.
    :param bool remove_on_boot_failure: If the image boot stage failed, remove
     the container or leave it for debugging.
    :param str skip_boot_checks: Coma-separated list of checks to skip.
     Use ``ALL`` to skip all boot checks. Boot checks determine if the image is
     ready to be tested. See the class attribute ``OpenSwitch.ALL_CHECKS``
     for a complete list of the boot checks available.

     .. warning::

        Disabling checks can cause commands to fail and race conditions errors.
        You have been warned.
    """

    ALL_CHECKS = OrderedDict((
        ('SWNS_NETNS_CREATED', 100),
        ('HWDESC_SYMLINK_CREATED', 110),
        ('OVSDB_SOCKET_CREATED', 200),
        ('SWITCHD_PID_FILE_CREATED', 210),
        ('SWITCH_HOSTNAME_SET', 220),
        ('CUR_CFG_SET', 230),
        ('SWITCHD_STATUS_ACTIVE', 240),
    ))
    """
    Boot check identifiers.
    """

    def __init__(
            self, identifier,
            image='topology/ops:latest', binds=None,
            remove_on_boot_failure=True,
            boot_checks_timeout=30,
            skip_boot_checks=None,
            **kwargs):

        # Add binded directories
        container_binds = [
            '/dev/log:/dev/log',
            '/lib/modules:/lib/modules',
            '/sys/fs/cgroup:/sys/fs/cgroup'
        ]
        if binds is not None:
            container_binds.append(binds)

        super(OpenSwitchNode, self).__init__(
            identifier, image=image, command='/sbin/init',
            binds=';'.join(container_binds), hostname='switch',
            **kwargs
        )

        # Private attributes
        self._boot_failed = False

        # Save other parameters
        self._boot_checks_timeout = boot_checks_timeout
        self._remove_on_boot_failure = remove_on_boot_failure
        self._skip_boot_checks = skip_boot_checks

        # Interpret and validate boot checks deactivations
        if skip_boot_checks is not None:

            skipped = skip_boot_checks.split(',')
            if 'ALL' in skipped:
                skipped = list(OpenSwitchNode.ALL_CHECKS.keys())
            else:
                for check in skipped:
                    if check not in OpenSwitchNode.ALL_CHECKS:
                        raise Exception(
                            'Unknown boot check "{}"'.format(check)
                        )

            self._skip_boot_checks = sorted(skipped)

            log.warning(
                (
                    'Some boot checks are disabled on node {}: (!!)\n{}'
                    'The omission of this checks can cause commands to fail '
                    'and race conditions will crawl and eat your kittens.\n'
                    'YOU HAVE BEEN WARNED!'
                ).format(','.join(self._skip_boot_checks), self.identifier)
            )

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
        # Read available ports
        ports_file = join(self.shared_dir, 'ports.json')

        # Write boot script input data
        with open(ports_file, 'w') as fd:
            fd.write(dumps(self.ports))

        # Write boot script
        root = dirname(normpath(abspath(__file__)))
        source = join(root, 'system_setup')
        destination = join(self.shared_dir, 'system_setup')
        copy(source, destination)

        # Determine call
        cmd = [
            'docker', 'exec', self.container_id,
            'python', '/tmp/system_setup',
            '--available', '/tmp/ports.json',
            '--checks-timeout', self._boot_checks_timeout
        ]

        if self._skip_boot_checks is not None:
            cmd.append('--skip-boot-checks')
            cmd.append(','.join(self._skip_boot_checks))

        # Determine logging level for system_setup script
        import logging
        levels = {
            logging.ERROR: 0,
            logging.WARNING: 1,
            logging.INFO: 2,
            logging.DEBUG: 3,
        }
        current_level = log.getEffectiveLevel()
        if current_level not in levels:
            log.warning(
                'Unhandled logging level {}. '
                'Assuming logging.DEBUG for system_setup call.'.format(
                    current_level
                )
            )

        target_level = levels.get(current_level, logging.DEBUG)
        if target_level > 0:
            cmd.append('-{}'.format('v' * target_level))

        log.info(
            'Booting OpenSwitch image {}. Please wait...'.format(self._image)
        )

        # Execute boot script
        # FIXME: Provide logging line by line
        setup = Popen(cmd, stdin=PIPE, stdout=PIPE)
        stdout, stderr = setup.communicate()
        if stdout:
            log.info('---- system_setup stdout::')
            log.info(stdout)
        if stderr:
            log.error('!!!! system_setup stderr::')
            log.error(stderr)

        # FIXME: Determine return code and show relevant message
        """
        if setup.returncode != 0:

            # Mark container as boot failed
            self._boot_failed = True

            if setup.returncode not in OpenSwitch.ALL_CHECKS.values():
                raise RuntimeException('Setup ')

            raise OpenSwitchImageException(
                'The OpenSwitch image {} failed to pass the boot check: {}.'
                ... you can disable it with ...
                ... your image may be broken and/or unusable ...
                'The given OpenSwitch image'.format(
                    self.identifier
                )
            )
        """

        # Read back port mapping
        with open(ports_file, 'r') as fd:
            new_mapping = loads(fd.read(), object_pairs_hook=OrderedDict)
            self.ports.clear()
            self.ports.update(new_mapping)

    def stop(self):
        """
        Request container to stop.

        See :meth:`DockerNode.stop` for more information.
        """
        if self._boot_failed and not self._remove_on_boot_failure:
            log.warning(
                '**NOT** removing container {} ({}) as it failed to boot '
                'and \'remove_on_boot_failure\' feature was set.'.format(
                    self.identifier, self.container_id
                )
            )
            return
        super(OpenSwitchNode, self).stop()

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
