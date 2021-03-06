# Copyright 2016 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Unittest for windows_ipsec rendering module."""

import datetime
import unittest

from lib import aclgenerator
from lib import nacaddr
from lib import naming
from lib import policy
from lib import windows_ipsec
import mox


GOOD_HEADER = """
header {
  comment:: "this is a test acl"
  target:: windows_ipsec test-filter
}
"""

GOOD_TERM_ICMP = """
term good-term-icmp {
  protocol:: icmp
  action:: accept
}
"""

BAD_TERM_ICMP = """
term test-icmp {
  icmp-type:: echo-request echo-reply
  action:: accept
}
"""

GOOD_TERM_TCP = """
term good-term-tcp {
  comment:: "Test term 1"
  destination-address:: PROD_NET
  destination-port:: SMTP
  protocol:: tcp
  action:: accept
}
"""

EXPIRED_TERM = """
term expired_test {
  expiration:: 2000-1-1
  action:: deny
}
"""

EXPIRING_TERM = """
term is_expiring {
  expiration:: %s
  action:: accept
}
"""

MULTIPLE_PROTOCOLS_TERM = """
term multi-proto {
  protocol:: tcp udp icmp
  action:: accept
}
"""

# Print a info message when a term is set to expire in that many weeks.
# This is normally passed from command line.
EXP_INFO = 2


class WindowsIPSecTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()
    self.naming = self.mox.CreateMock(naming.Naming)

  def tearDown(self):
    self.mox.VerifyAll()
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  # pylint: disable=invalid-name
  def failUnless(self, strings, result, term):
    for string in strings:
      fullstring = 'netsh ipsec static add %s' % (string)
      super(WindowsIPSecTest, self).failUnless(
          fullstring in result,
          'did not find "%s" for %s' % (fullstring, term))

  def testPolicy(self):
    self.naming.GetNetAddr('PROD_NET').AndReturn([nacaddr.IP('10.0.0.0/8')])
    self.naming.GetServiceByProto('SMTP', 'tcp').AndReturn(['25'])
    self.mox.ReplayAll()
    acl = windows_ipsec.WindowsIPSec(policy.ParsePolicy(
        GOOD_HEADER + GOOD_TERM_TCP, self.naming), EXP_INFO)
    result = str(acl)
    self.failUnless(
        ['policy name=test-filter-policy assign=yes'],
        result,
        'header')

  def testTcp(self):
    self.naming.GetNetAddr('PROD_NET').AndReturn([nacaddr.IP('10.0.0.0/8')])
    self.naming.GetServiceByProto('SMTP', 'tcp').AndReturn(['25'])
    self.mox.ReplayAll()
    acl = windows_ipsec.WindowsIPSec(policy.ParsePolicy(
        GOOD_HEADER + GOOD_TERM_TCP, self.naming), EXP_INFO)
    result = str(acl)
    self.failUnless(
        ['filteraction name=t_good-term-tcp-action action=permit',
         'filter filterlist=t_good-term-tcp-list mirrored=yes srcaddr=any '
         ' dstaddr=10.0.0.0 dstmask=8 dstport=25',
         'rule name=t_good-term-tcp-rule policy=test-filter'
         ' filterlist=t_good-term-tcp-list'
         ' filteraction=t_good-term-tcp-action'],
        result,
        'good-term-tcp')

  def testIcmp(self):
    self.mox.ReplayAll()
    acl = windows_ipsec.WindowsIPSec(policy.ParsePolicy(
        GOOD_HEADER + GOOD_TERM_ICMP, self.naming), EXP_INFO)
    result = str(acl)
    self.failUnless(
        ['filterlist name=t_good-term-icmp-list',
         'filteraction name=t_good-term-icmp-action action=permit',
         'filter filterlist=t_good-term-icmp-list mirrored=yes srcaddr=any '
         ' dstaddr=any',
         'rule name=t_good-term-icmp-rule policy=test-filter'
         ' filterlist=t_good-term-icmp-list'
         ' filteraction=t_good-term-icmp-action'],
        result,
        'good-term-icmp')

  def testBadIcmp(self):
    self.mox.ReplayAll()
    acl = windows_ipsec.WindowsIPSec(policy.ParsePolicy(
        GOOD_HEADER + BAD_TERM_ICMP, self.naming), EXP_INFO)
    self.assertRaises(aclgenerator.UnsupportedFilterError, str, acl)

  def testExpiredTerm(self):
    self.mox.StubOutWithMock(windows_ipsec.logging, 'warn')
    # create mock to ensure we warn about expired terms being skipped
    windows_ipsec.logging.warn('WARNING: Term %s in policy %s is expired and '
                               'will not be rendered.', 'expired_test',
                               'test-filter')
    self.mox.ReplayAll()
    windows_ipsec.WindowsIPSec(policy.ParsePolicy(
        GOOD_HEADER + EXPIRED_TERM, self.naming), EXP_INFO)

  def testExpiringTerm(self):
    self.mox.StubOutWithMock(windows_ipsec.logging, 'info')
    # create mock to ensure we inform about expiring terms
    windows_ipsec.logging.info('INFO: Term %s in policy %s expires in '
                               'less than two weeks.', 'is_expiring',
                               'test-filter')
    self.mox.ReplayAll()
    exp_date = datetime.date.today() + datetime.timedelta(weeks=EXP_INFO)
    windows_ipsec.WindowsIPSec(policy.ParsePolicy(
        GOOD_HEADER + EXPIRING_TERM % exp_date.strftime('%Y-%m-%d'),
        self.naming), EXP_INFO)

  def testMultiprotocol(self):
    self.mox.ReplayAll()
    acl = windows_ipsec.WindowsIPSec(policy.ParsePolicy(
        GOOD_HEADER + MULTIPLE_PROTOCOLS_TERM, self.naming), EXP_INFO)
    result = str(acl)
    self.failUnless(
        ['filterlist name=t_multi-proto-list',
         'filteraction name=t_multi-proto-action action=permit',
         'filter filterlist=t_multi-proto-list mirrored=yes srcaddr=any '
         ' dstaddr=any  protocol=tcp',
         'filter filterlist=t_multi-proto-list mirrored=yes srcaddr=any '
         ' dstaddr=any  protocol=udp',
         'filter filterlist=t_multi-proto-list mirrored=yes srcaddr=any '
         ' dstaddr=any  protocol=icmp',
         'rule name=t_multi-proto-rule policy=test-filter'
         ' filterlist=t_multi-proto-list filteraction=t_multi-proto-action'],
        result,
        'multi-proto')


if __name__ == '__main__':
  unittest.main()
