# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2018 Lenovo
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# The command module for redfish systems.  Provides https-only support
# for redfish compliant endpoints

import json
import os
import pyghmi.exceptions as exc
import pyghmi.constants as const
import pyghmi.util.webclient as webclient
import time

powerstates = {
    'on': 'On',
    'off': 'ForceOff',
    'softoff': 'GracefulShutdown',
    'shutdown': 'GracefulShutdown',
    'reset': 'ForceRestart',
    'boot': None,
}

class Command(object):

    def __init__(self, bmc, userid, password, verifycallback, sysurl=None):
        self.wc = webclient.SecureHTTPConnection(
            bmc, 443, verifycallback=verifycallback)
        self.wc.set_basic_credentials(userid, password)
        self.wc.set_header('Content-Type', 'application/json')
        overview = self.wc.grab_json_response('/redfish/v1/')
        systems = overview['Systems']['@odata.id']
        members = self.wc.grab_json_response(systems)
        systems = members['Members']
        if sysurl:
            for system in systems:
                if system['@odata.id'] == sysurl:
                    self.sysurl = sysurl
                    break
            else:
                raise exc.PyghmiException(
                    'Specified sysurl not found: '.format(sysurl))
        else:
            if len(systems) != 1:
                raise pygexc.PyghmiException(
                    'Multi system manager, sysurl is required parameter')
            self.sysurl = systems[0]['@odata.id']
        sysinf = self.wc.grab_json_response(self.sysurl)
        self.powerurl = sysinf.get('Actions', {}).get(
            '#ComputerSystem.Reset', {}).get('target', None)

    def get_power(self):
        sysinfo = self.wc.grab_json_response(self.sysurl)
        return {'powerstate': str(sysinfo['PowerState'].lower())}

    def set_power(self, powerstate, wait=False):
        if powerstate == 'boot':
            oldpowerstate = self.get_power()['powerstate']
            powerstate = 'on' if oldpowerstate == 'off' else 'reset'
        reqpowerstate = powerstate
        if powerstate not in powerstates:
            raise exc.InvalidParameterValue(
                "Unknown power state %s requested" % powerstate)
        powerstate = powerstates[powerstate]
        result = self.wc.grab_json_response_with_status(
            self.powerurl, {'ResetType': powerstate})
        if result[1] < 200 or result[1] >= 300:
            raise exc.PyghmiException(result[0])
        if wait and reqpowerstate in ('on', 'off', 'softoff', 'shutdown'):
            if reqpowerstate in ('softoff', 'shutdown'):
                reqpowerstate = 'off'
            timeout = os.times()[4] + 300
            while (self.get_power()['powerstate'] != reqpowerstate and
                   os.times()[4] < timeout):
                time.sleep(0.1)
            if self.get_power()['powerstate'] != reqpowerstate:
                raise exc.PyghmiException(
                    "System did not accomplish power state change")
            return {'powerstate': reqpowerstate}
        return {'pendingpowerstate': reqpowerstate}


if __name__ == '__main__':
    import os
    import sys
    print(repr(
        Command(sys.argv[1], os.environ['BMCUSER'], os.environ['BMCPASS'],
                verifycallback=lambda x: True).get_power()))
