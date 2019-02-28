# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function, unicode_literals

"""
Copyright (C) 2019, Zato Source s.r.o. https://zato.io

Licensed under LGPLv3, see LICENSE.txt for terms and conditions.
"""

# stdlib
import logging
from logging import DEBUG
from http.client import BAD_REQUEST, FORBIDDEN, INTERNAL_SERVER_ERROR, NOT_ACCEPTABLE, OK, responses, SERVICE_UNAVAILABLE
from time import sleep
from traceback import format_exc

# Bunch
from bunch import Bunch, bunchify

# Zato
from zato.common.util.json_ import dumps
from zato.server.connection.jms_wmq.jms import WebSphereMQException, NoMessageAvailableException
from zato.server.connection.jms_wmq.jms.connection import WebSphereMQConnection
from zato.server.connection.jms_wmq.jms.core import TextMessage
from zato.server.connection.connector.subprocess_.base import BaseConnectionContainer, Response

# ################################################################################################################################

# 1 MB = 8,000 kilobits
mb_to_kbit = 8000

# ################################################################################################################################
# ################################################################################################################################

class SFTPConnection(object):

    def __init__(self, logger, **config):
        self.logger = logger
        self.config = bunchify(config)     # type: Bunch

        print(self.config)

        self.id = self.config.id                # type: int
        self.name = self.config.name            # type: str
        self.is_active = self.config.is_active  # type: str

        self.host = self.config.host or ''      # type: str
        self.port = self.config.port or None     # type: int

        self.username = self.config.username       # type: str
        self.password = self.config.password or '' # type: str
        self.secret = self.config.secret or ''     # type: str

        self.sftp_command = self.config.sftp_command # type: str
        self.ping_command = self.config.ping_command # type: str

        self.identity_file = self.config.identity_file or ''     # type: str
        self.ssh_config_file = self.config.ssh_config_file or '' # type: str

        self.log_level = int(self.config.log_level)  # type: int
        self.should_flush = self.config.should_flush # type: bool
        self.buffer_size = self.config.buffer_size   # type: int

        self.ssh_options = self.config.ssh_options or ''     # type: str
        self.force_ip_type = self.config.force_ip_type or '' # type: str

        self.should_preserve_meta = self.config.should_preserve_meta     # type: bool
        self.is_compression_enabled = self.config.is_compression_enabled # type: bool

        # SFTP expects kilobits instead of megabytes
        self.bandwidth_limit = float(self.config.bandwidth_limit) * mb_to_kbit # type: float

        # Added for API completeness
        self.is_connected = True

# ################################################################################################################################

    def execute(self, data):
        """ Executes a single or multiple SFTP commands from the input 'data' string.
        """

# ################################################################################################################################

    def connect(self):
        # We do not maintain long-running connections but we may still want to ping the remote end
        # to make sure we are actually able to connect to it.
        return self.ping()

# ################################################################################################################################

    def close(self):
        # Added for API completeness
        pass

# ################################################################################################################################

    def ping(self):
        self.logger.warn('QQQ %s', self.config)

# ################################################################################################################################
# ################################################################################################################################

class SFTPConnectionContainer(BaseConnectionContainer):

    connection_class = SFTPConnection
    ipc_name = conn_type = logging_file_name = 'sftp'

    remove_id_from_def_msg = False
    remove_name_from_def_msg = False

# ################################################################################################################################

    def _on_OUTGOING_SFTP_PING(self, msg):
        return super(SFTPConnectionContainer, self).on_definition_ping(msg)

# ################################################################################################################################

    def _on_OUTGOING_SFTP_DELETE(self, msg):
        return super(SFTPConnectionContainer, self).on_definition_delete(msg)

    _on_GENERIC_CONNECTION_EDIT = _on_OUTGOING_SFTP_DELETE

# ################################################################################################################################

    def _on_OUTGOING_SFTP_CREATE(self, msg):
        return super(SFTPConnectionContainer, self).on_definition_create(msg)

# ################################################################################################################################

    def _on_OUTGOING_SFTP_EDIT(self, msg):
        return super(SFTPConnectionContainer, self).on_definition_edit(msg)

    _on_GENERIC_CONNECTION_EDIT = _on_OUTGOING_SFTP_EDIT

# ################################################################################################################################

    def _on_OUTGOING_SFTP_CHANGE_PASSWORD(self, msg):
        return super(SFTPConnectionContainer, self).on_definition_change_password(msg)

    _on_GENERIC_CONNECTION_CHANGE_PASSWORD = _on_OUTGOING_SFTP_CHANGE_PASSWORD

# ################################################################################################################################

    def _on_OUTGOING_SFTP_EXECUTE(self, msg, is_reconnect=False):
        pass

# ################################################################################################################################

if __name__ == '__main__':

    container = SFTPConnectionContainer()
    container.run()

# ################################################################################################################################

'''
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function, unicode_literals

"""
Copyright (C) 2019, Zato Source s.r.o. https://zato.io

Licensed under LGPLv3, see LICENSE.txt for terms and conditions.
"""

# stdlib
import logging
from datetime import datetime
from itertools import count
from tempfile import NamedTemporaryFile

# Bunch
from bunch import Bunch, bunchify

# sh
from sh import Command

# Zato
from zato.common import SFTP

# ################################################################################################################################

log_format = '%(asctime)s - %(levelname)s - %(process)d:%(threadName)s - %(name)s:%(lineno)d - %(message)s'
logging.basicConfig(level=logging.INFO, format=log_format)

# ################################################################################################################################

logger = logging.getLogger(__name__)

# ################################################################################################################################

# 1 MB = 8,000 kilobits
mb_to_kbit = 8000

# ################################################################################################################################

ip_type_map = {
    SFTP.IP_TYPE.IPV4.id: '-4',
    SFTP.IP_TYPE.IPV6.id: '-6',
}

log_level_map = {
    SFTP.LOG_LEVEL.LEVEL0.id: '',
    SFTP.LOG_LEVEL.LEVEL1.id: '-v',
    SFTP.LOG_LEVEL.LEVEL2.id: '-vv',
    SFTP.LOG_LEVEL.LEVEL3.id: '-vvv',
    SFTP.LOG_LEVEL.LEVEL4.id: '-vvvv',
}

# ################################################################################################################################
# ################################################################################################################################

class Output(object):
    """ Represents output resulting from execution of SFTP command(s).
    """
    __slots__ = 'cid', 'command', 'command_no', 'stdout', 'stderr'

    def __init__(self, cid, command_no, command, stdout, stderr):
        self.cid = cid               # type: str
        self.command_no = command_no # type: int
        self.command = command       # type: str
        self.stdout = stdout         # type: str
        self.stderr = stderr         # type: str

    def to_dict(self):
        return {
            'cid': self.cid,
            'command': self.command,
            'command_no': self.command_no,
            'stdout': self.stdout,
            'stderr': self.stderr,
        }

# ################################################################################################################################

class SFTPConnection(object):
    """ Wraps access to SFTP commands via command line.
    """
    command_counter = count(1)

    def __init__(self, logger, **config):
        self.logger = logger
        self.config = bunchify(config)     # type: Bunch

        # Reject unknown IP types
        if self.config.force_ip_type:
            if not SFTP.IP_TYPE().is_valid(self.config.force_ip_type):
                raise ValueError('Unknown IP type `{!r}`'.format(self.config.force_ip_type))

        # Reject unknown logging levels
        if self.config.log_level:
            if not SFTP.LOG_LEVEL().is_valid(self.config.log_level):
                raise ValueError('Unknown log level `{!r}`'.format(self.config.log_level))

        self.id = self.config.id                # type: int
        self.name = self.config.name            # type: str
        self.is_active = self.config.is_active  # type: str

        self.host = self.config.host or ''      # type: str
        self.port = self.config.port or None    # type: int

        self.username = self.config.username       # type: str
        self.password = self.config.password or '' # type: str
        self.secret = self.config.secret or ''     # type: str

        self.sftp_command = self.config.sftp_command # type: str
        self.ping_command = self.config.ping_command # type: str

        self.identity_file = self.config.identity_file or ''     # type: str
        self.ssh_config_file = self.config.ssh_config_file or '' # type: str

        self.log_level = self.config.log_level       # type: int
        self.should_flush = self.config.should_flush # type: bool
        self.buffer_size = self.config.buffer_size   # type: int

        self.ssh_options = self.config.ssh_options or []     # type: str
        self.force_ip_type = self.config.force_ip_type or '' # type: str

        self.should_preserve_meta = self.config.should_preserve_meta     # type: bool
        self.is_compression_enabled = self.config.is_compression_enabled # type: bool

        # SFTP expects kilobits instead of megabytes
        self.bandwidth_limit = int(float(self.config.bandwidth_limit) * mb_to_kbit) # type: int

        # Added for API completeness
        self.is_connected = True

        # Create the reusable command object
        self.command = self.get_command()

# ################################################################################################################################

    def get_command(self):
        """ Returns a reusable sh.Command object that can execute multiple different SFTP commands.
        """
        # A list of arguments that will be added to the base command
        args = []

        # Buffer size is always available
        args.append('-B')
        args.append(self.buffer_size)

        # Bandwidth limit is always available
        args.append('-l')
        args.append(self.bandwidth_limit)

        # Bandwidth limit is always available but may map to an empty string
        log_level = log_level_map[self.log_level]
        if log_level:
            args.append(log_level)

        # Preserving file and directory metadata is optional
        if self.should_preserve_meta:
            args.append('-p')

        # Immediate flushing is optional
        if self.should_flush:
            args.append('-f')

        # Compression is optional
        if self.is_compression_enabled:
            args.append('-C')

        # Forcing a particular IP version is optional
        if self.force_ip_type:
            args.append(ip_type_map[self.force_ip_type])

        # Port is optional
        if self.port:
            args.append('-P')
            args.append(self.port)

        # Identity file is optional
        if self.identity_file:
            args.append('-i')
            args.append(self.identity_file)

        # SSH config file is optional
        if self.ssh_config_file:
            args.append('-F')
            args.append(self.ssh_config_file)

        # Base command to build additional arguments into
        command = Command(self.sftp_command)
        command = command.bake(*args)

        return command

# ################################################################################################################################

    def execute(self, cid, data):
        """ Executes a single or multiple SFTP commands from the input 'data' string.
        """
        # Increment the command counter each time .execute is called
        command_no = next(self.command_counter) # type: int

        self.logger.info('Executing cid:`%s` (%s), data:`%s`', cid, command_no, data)

        # Additional command arguments
        args = []

        with NamedTemporaryFile(mode='w+', suffix='-zato-sftp.txt') as f:

            # Write command to the temporary file
            f.write(data)
            f.flush()

            # Append the file names to the list of arguments SFTP receives
            args.append('-b')
            args.append(f.name)

            # Both username and host are optional but if they are provided, they must be the last arguments in the command
            if self.host:
                if self.username:
                    args.append('{}@{}'.format(self.username, self.host))
                else:
                    args.append(self.host)

            # Finally, execute all the commands
            out = self.command(*args)
            return Output(cid, command_no, out.cmd, out.stdout, out.stderr)

# ################################################################################################################################

    def connect(self):
        # We do not maintain long-running connections but we may still want to ping the remote end
        # to make sure we are actually able to connect to it.
        self.ping()

# ################################################################################################################################

    def close(self):
        # Added for API completeness
        pass

# ################################################################################################################################

    def ping(self, _utcnow=datetime.utcnow):
        self.execute('ping-{}'.format(_utcnow().isoformat()), self.ping_command)

# ################################################################################################################################
# ################################################################################################################################

config = {
    'id': 123,
    'name': 'My SFTP connection',
    'is_active': True,

    'host': 'localhost',
    'port': 22,

    'username': None,
    'password': None,
    'secret': None,

    'sftp_command': 'sftp',
    'ping_command': 'ls .',

    'identity_file': None,
    'ssh_config_file': None,

    'log_level': '4',
    'should_flush': True,
    'buffer_size': 32678,

    'ssh_options': None,
    'force_ip_type': None,

    'should_preserve_meta': True,
    'is_compression_enabled': True,

    'bandwidth_limit': '10'
}

conn = SFTPConnection(logger, **config)
conn.connect()
command = 'pwd'
cid = 'abc'
result = conn.execute(cid, command)

print()
print()

print(111, result.to_dict())

print()
print()
'''
