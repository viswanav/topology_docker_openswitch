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
Test suite for system_setup.
"""

from __future__ import unicode_literals, absolute_import
from __future__ import print_function, division

from os import chdir
from os.path import dirname
from shutil import copy
from ipdb import set_trace

try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

from topology_docker_openswitch import openswitch


def test_check_swns(tmpdir):
    """
    Test the swns checker.
    """

    system_setup = '/system_setup'
    system_setup_path = ''.join(
        [dirname(openswitch.__file__), system_setup]
    )
    system_setup_py_path = ''.join([str(tmpdir), system_setup, '.py'])

    copy(system_setup_path, system_setup_py_path)

    chdir(str(tmpdir))

    __import__(system_setup[1:])

    set_trace()

    with patch('system_setup.var') as mock_var:
        mock_var
        set_trace()
        pass
