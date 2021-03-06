# Copyright 2008 Google Inc. All Rights Reserved.
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

"""Unittest for iptables rendering module."""

import datetime
import re
import unittest

from lib import aclgenerator
from lib import iptables
from lib import nacaddr
from lib import naming
from lib import policy
import mox

GOOD_HEADER_1 = """
header {
  comment:: "this is a test acl"
  target:: iptables INPUT ACCEPT
}
"""

GOOD_HEADER_2 = """
header {
  comment:: "this is a test acl"
  target:: iptables OUTPUT DROP
}
"""

GOOD_HEADER_3 = """
header {
  comment:: "this is a test acl with abbreviation"
  target:: iptables INPUT ACCEPT abbreviateterms
}
"""

GOOD_HEADER_4 = """
header {
  comment:: "this is a test acl with truncation"
  target:: iptables INPUT ACCEPT truncateterms
}
"""

GOOD_HEADER_5 = """
header {
  comment:: "this is a test acl with no default target"
  target:: iptables INPUT
}
"""

GOOD_HEADER_6 = """
header {
  comment:: "this is a test acl with a custom chain and no default target"
  target:: iptables foo
}
"""

IPV6_HEADER_1 = """
header {
  comment:: "test header for inet6 terms"
  target:: iptables INPUT DROP inet6
}
"""

NON_STANDARD_CHAIN = """
header {
  comment:: "this is a test acl with non-standard chain"
  target:: iptables foo ACCEPT
}
"""

NOSTATE_HEADER = """
header {
  comment:: "iptables filter without stateful"
  target:: iptables INPUT ACCEPT nostate
}
"""

CHAIN_HEADER_1 = """
header {
  comment:: "this is a test acl"
  target:: iptables foobar_chain nostate
}
"""

BAD_HEADER_2 = """
header {
  target:: juniper
}
"""

BAD_HEADER_3 = """
header {
  target:: iptables INPUT MAYBE
}
"""

GOOD_TERM_1 = """
term good-term-1 {
  protocol:: icmp
  action:: accept
}
"""

GOOD_TERM_2 = """
term good-term-2 {
  source-address:: INTERNAL
  source-exclude:: OOB_NET
  protocol:: tcp
  source-port:: HTTP
  action:: accept
}
"""

GOOD_TERM_3 = """
term good-term-3 {
  source-port:: HTTP
  protocol:: tcp
  option:: rst fin tcp-established established
  action:: accept
}
"""

GOOD_TERM_4 = """
term good-term-4 {
  protocol:: tcp udp esp ah gre icmp 50
  action:: accept
}
"""

GOOD_TERM_5 = """
term good-term-5 {
  verbatim:: iptables "mary had a little lamb"
  verbatim:: cisco "mary had second lamb"
  verbatim:: juniper "mary had third lamb"
}
"""

GOOD_TERM_6 = """
term good-term-6 {
  comment:: "Some text describing what this block does,
             possibly including newines, blank lines,
             and extra-long comments (over 255 characters)
             %(long_line)s

             All these cause problems if passed verbatim to iptables.
             "
  comment:: ""
  protocol:: tcp
  action:: accept

}
""" % {'long_line': '-' * 260}


GOOD_TERM_7 = """
term drop-short-initial-fragments {
  option:: first-fragment
  packet-length:: 1-119
  action:: deny
}

term drop-header-overwrite {
  fragment-offset:: 1-119
  action:: deny
}
"""

GOOD_TERM_8 = """
term block-some-icmp {
  protocol:: icmp
  icmp-type:: router-solicitation information-request unreachable echo-reply
  action:: deny
}
"""

GOOD_TERM_9 = """
term good-term-9 {
  source-address:: SOME_SOURCE
  destination-address:: SOME_DEST
  protocol:: tcp
  source-port:: HTTP
  action:: accept
}
"""

GOOD_TERM_10 = """
term good-term-10 {
  owner:: foo@google.com
  action:: accept
}
"""

IPV6_TERM_1 = """
term inet6-icmp {
  protocol:: icmpv6
  icmp-type:: destination-unreachable time-exceeded echo-reply
  action:: deny
}
"""

IPV6_HEADERS = """
term ipv6-header-1 {
  protocol:: hop-by-hop
  action:: deny
}

term ipv6-header-2 {
  protocol:: fragment
  action:: deny
}
"""

ICMPV6_TERM_1 = """
term inet6-icmp {
  source-address:: IPV6_INTERNAL
  protocol:: icmpv6
  icmp-type:: destination-unreachable
  action:: deny
}
"""

LOGGING_TERM_1 = """
term foo {
  protocol:: tcp
  logging:: syslog
  action:: accept
}
"""

UDP_STATE_TERM = """
term test-conntrack-udp {
  protocol:: udp
  option:: established
  action:: accept
}
"""

TCP_STATE_TERM = """
term tcp-established-only {
  protocol:: tcp
  option:: established
  action:: accept
}
"""

STATEFUL_ONLY_TERM = """
term stateful-only {
  option:: established
  action:: accept
}
"""

BAD_LONG_TERM_NAME = """
term this-term-name-is-really-far-too-long {
  protocol:: tcp
  action:: accept
}
"""

GOOD_LONG_TERM_NAME = """
term google-experiment-abbreviations {
  protocol:: tcp
  action:: accept
}
"""

GOOD_MULTIPORT = """
term multiport {
  source-port:: FOURTEEN_PORTS
  protocol:: tcp
  action:: accept
}
"""

MULTIPORT_SWAP = """
term multiport {
  source-port:: HTTP HTTPS
  destination-port:: SSH
  protocol:: tcp
  action:: accept
}
"""

EXPIRED_TERM = """
term is_expired {
    expiration:: 2001-01-01
    action:: accept
}
"""

EXPIRING_TERM = """
term is_expiring {
  expiration:: %s
  action:: accept
}
"""

GOOD_MULTIPORT_RANGE = """
term bad-mport-ranges {
  destination-port:: FIFTEEN_PORTS_WITH_RANGES
  protocol:: tcp
  action:: accept
}
"""

LARGE_MULTIPORT = """
term bad-multiport {
  destination-port:: LOTS_OF_PORTS
  protocol:: tcp
  action:: accept
}
"""

DUAL_LARGE_MULTIPORT = """
term bad-multiport {
  source-port:: LOTS_OF_SPORTS
  destination-port:: LOTS_OF_DPORTS
  protocol:: tcp
  action:: accept
}
"""

UNSUPPORTED_TERM = """
term ether-type-filter {
  ether-type:: arp
  action:: accept
}
"""

UNKNOWN_TERM_KEYWORD = """
term unknown-keyword {
  comment:: "imaginary new keyword added to the policy library."
  comment:: "i.e. ip-options-count:: 2-255"
  comment:: "must be added in tests due to checking in policy library."
  action:: deny
}
"""

UNSUPPORTED_EXCEPT = """
term block-non-standard {
  protocol-except:: tcp udp icmp
  action:: deny
}
"""

REJECT_TERM1 = """
term reject-term1 {
  action:: reject-with-tcp-rst
}
"""

REJECT_TERM2 = """
term reject-term2 {
  action:: reject
}
"""

NEXT_TERM1 = """
term next-term1 {
  action:: next
}
"""

BAD_PROTOCOL_MATCHES = """
term proto-accept-and-reject {
  protocol:: tcp udp icmp
  protocol-except:: gre
  action:: accept
}
"""

SOURCE_INTERFACE_TERM = """
term src-interface {
  protocol:: tcp
  source-interface:: eth0
  action:: accept
}
"""

DESTINATION_INTERFACE_TERM = """
term dst-interface {
  protocol:: tcp
  destination-interface:: eth0
  action:: accept
}
"""

# Print a info message when a term is set to expire in that many weeks.
# This is normally passed from command line.
EXP_INFO = 2


class FakeTerm(object):
  name = ''
  protocol = ['tcp']


class AclCheckTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()
    self.naming = self.mox.CreateMock(naming.Naming)

  def tearDown(self):
    self.mox.VerifyAll()
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testChainFilter(self):
    self.mox.StubOutWithMock(iptables.logging, 'warn')
    filter_name = 'foobar_chain'
    # create mock to ensure we warn about non-standard chain
    iptables.logging.warn('Filter is generating a non-standard chain that will '
                          'not apply to traffic unless linked from INPUT, '
                          'OUTPUT or FORWARD filters. New chain name is: %s',
                          filter_name)
    self.mox.ReplayAll()
    pol = policy.ParsePolicy(CHAIN_HEADER_1 + GOOD_TERM_1, self.naming)
    acl = iptables.Iptables(pol, EXP_INFO)
    result = str(acl)
    # is the chain right?
    self.failUnless('-A foobar_chain -j f_good-term-1' in result)
    # is the term named appropriately?
    self.failUnless('-N f_good-term-1' in result)

  def testUnsupportedTargetOption(self):
    self.mox.ReplayAll()
    pol = policy.ParsePolicy(BAD_HEADER_3 + GOOD_TERM_1, self.naming)
    self.assertRaises(iptables.UnsupportedTargetOption,
                      iptables.Iptables, pol, EXP_INFO)

  def testGoodPolicy(self):
    self.mox.ReplayAll()
    acl = iptables.Iptables(policy.ParsePolicy(GOOD_HEADER_2 + GOOD_TERM_1,
                                               self.naming), EXP_INFO)
    result = str(acl)
    self.failUnless('-P OUTPUT DROP' in result,
                    'output default policy of drop not set.')
    self.failUnless('-N O_good-term-1' in result,
                    'did not find new chain for good-term-1.')
    self.failUnless('-A O_good-term-1 -p icmp -m state '
                    '--state NEW,ESTABLISHED,RELATED -j ACCEPT' in result,
                    'did not find append for good-term-1.')

  def testCustomChain(self):
    self.mox.ReplayAll()
    acl = iptables.Iptables(policy.ParsePolicy(NON_STANDARD_CHAIN + GOOD_TERM_1,
                                               self.naming), EXP_INFO)
    result = str(acl).split('\n')
    self.failUnless('-N foo' in result, 'did not find new chain for foo.')
    self.failIf('-P foo' in result, 'chain foo may not have a policy set.')

  def testChainNoTarget(self):
    self.mox.ReplayAll()
    acl = iptables.Iptables(policy.ParsePolicy(GOOD_HEADER_5 + GOOD_TERM_1,
                                               self.naming), EXP_INFO)
    result = str(acl).split('\n')
    for line in result:
      self.failIf(line.startswith(':INPUT'),
                  'chain may not have a policy set.')
      self.failIf(line.startswith('-P INPUT'),
                  'chain may not have a policy set.')
      self.failIf(line.startswith('-N INPUT'),
                  'attempting to create a built-in chain.')

  def testCustomChainNoTarget(self):
    self.mox.ReplayAll()
    acl = iptables.Iptables(policy.ParsePolicy(GOOD_HEADER_6 + GOOD_TERM_1,
                                               self.naming), EXP_INFO)
    result = str(acl).split('\n')
    self.failUnless('-N foo' in result, 'did not find a new chain for foo.')
    for line in result:
      self.failIf(line.startswith(':foo'),
                  'chain may not have a policy set.')
      self.failIf(line.startswith('-P foo'),
                  'chain may not have a policy set.')

  def testExcludeReturnsPolicy(self):
    #
    # In this test, we should get fewer lines of output by performing
    # early return jumps on excluded addresses.
    #
    self.naming.GetNetAddr('INTERNAL').InAnyOrder().AndReturn(
        [nacaddr.IPv4('10.0.0.0/8')])
    self.naming.GetNetAddr('OOB_NET').InAnyOrder().AndReturn(
        [nacaddr.IPv4('10.0.0.0/24')])
    self.naming.GetServiceByProto('HTTP', 'tcp').AndReturn(['80'])
    self.mox.ReplayAll()
    acl = iptables.Iptables(policy.ParsePolicy(GOOD_HEADER_1 + GOOD_TERM_2,
                                               self.naming), EXP_INFO)
    result = str(acl)
    self.failUnless('-P INPUT ACCEPT' in result, 'no default policy found.')
    self.failUnless('-p tcp' in result, 'no protocol specification found.')
    self.failUnless('-s ' in result, 'no source address found.')
    self.failUnless('-s 10.0.0.0/24 -j RETURN' in result,
                    'expected address 10.0.0.0/24 not jumping to RETURN.')
    self.failUnless('--sport 80 -s 10.0.0.0/8' in result,
                    'expected source address 10.0.0.0/8 not accepted.')

  def testExcludeAddressesPolicy(self):
    #
    # In this test, we should get fewer lines of output from excluding
    # addresses from the specified destination.
    #
    self.naming.GetNetAddr('INTERNAL').InAnyOrder().AndReturn(
        [nacaddr.IPv4('10.0.0.0/8')])
    self.naming.GetNetAddr('OOB_NET').InAnyOrder().AndReturn(
        [nacaddr.IPv4('10.128.0.0/9'), nacaddr.IPv4('10.64.0.0/10')])
    self.naming.GetServiceByProto('HTTP', 'tcp').AndReturn(['80'])
    self.mox.ReplayAll()
    acl = iptables.Iptables(policy.ParsePolicy(GOOD_HEADER_1 + GOOD_TERM_2,
                                               self.naming), EXP_INFO)
    result = str(acl)
    self.failUnless('--sport 80 -s 10.0.0.0/10' in result,
                    'expected source address 10.0.0.0/10 not accepted.')

  def testAddExcludeSourceForLengthPolicy(self):
    #
    # In this test, we should generate fewer lines of output by
    # excluding the inverted the source and performing early returns on
    # the excluded range.
    #
    source_range = []
    for i in xrange(18):
      address = nacaddr.IPv4(10 * 256 * 256 * 256 + i * 256 * 256)
      source_range.append(address.supernet(15))  # Grow to /17

    dest_range = []
    for i in xrange(40):
      address = nacaddr.IPv4(10 * 256 * 256 * 256 + i * 256)
      dest_range.append(address.supernet(7))  # Grow to /25

    self.naming.GetNetAddr('SOME_SOURCE').InAnyOrder().AndReturn(source_range)
    self.naming.GetNetAddr('SOME_DEST').InAnyOrder().AndReturn(dest_range)
    self.naming.GetServiceByProto('HTTP', 'tcp').AndReturn(['80'])
    self.mox.ReplayAll()
    acl = iptables.Iptables(policy.ParsePolicy(GOOD_HEADER_1 + GOOD_TERM_9,
                                               self.naming), EXP_INFO)
    result = str(acl)
    self.failUnless('-P INPUT ACCEPT' in result, 'no default policy found.')
    self.failUnless('-p tcp' in result, 'no protocol specification found.')
    self.assertTrue(result.count('\n') < len(source_range) * len(dest_range),
                    'expected less than %d rows, got %d' %
                    (len(source_range) * len(dest_range), result.count('\n')))
    self.failUnless(
        '-s 0.0.0.0/5 -j RETURN' in result,
        'expected address 0.0.0.0/5 to RETURN:\n' + result)
    self.failUnless(
        '-s 10.0.128.0/17 -j RETURN' in result,
        'expected address 10.0.128.0/17 not jumping to RETURN:\n' + result)
    self.failUnless(
        re.search('--sport 80 -d 10.0.1.0/25 [^\n]* -j ACCEPT', result),
        'expected destination addresss 10.0.1.0/25 accepted:\n' + result)

  def testAddExcludeDestForLengthPolicy(self):
    #
    # In this test, we should generate fewer lines of output by
    # excluding the inverted the source and performing early returns on
    # the excluded range.
    #
    source_range = []
    for i in xrange(40):
      address = nacaddr.IPv4(10 * 256 * 256 * 256 + i * 256)
      source_range.append(address.supernet(7))  # Grow to /25

    dest_range = []
    for i in xrange(18):
      address = nacaddr.IPv4(10 * 256 * 256 * 256 + i * 256 * 256)
      dest_range.append(address.supernet(15))  # Grow to /17

    self.naming.GetNetAddr('SOME_SOURCE').InAnyOrder().AndReturn(source_range)
    self.naming.GetNetAddr('SOME_DEST').InAnyOrder().AndReturn(dest_range)
    self.naming.GetServiceByProto('HTTP', 'tcp').AndReturn(['80'])
    self.mox.ReplayAll()
    acl = iptables.Iptables(policy.ParsePolicy(GOOD_HEADER_1 + GOOD_TERM_9,
                                               self.naming), EXP_INFO)
    result = str(acl)
    self.failUnless('-P INPUT ACCEPT' in result, 'no default policy found.')
    self.failUnless('-p tcp' in result, 'no protocol specification found.')
    self.assertTrue(result.count('\n') < len(source_range) * len(dest_range),
                    'expected less than %d rows, got %d' %
                    (len(source_range) * len(dest_range), result.count('\n')))
    self.failUnless(
        '-d 0.0.0.0/5 -j RETURN' in result,
        'expected address 0.0.0.0/5 to RETURN:\n' + result)
    self.failUnless(
        '-d 10.0.128.0/17 -j RETURN' in result,
        'expected address 10.0.128.0/17 not jumping to RETURN:\n' + result)
    self.failUnless(
        re.search('--sport 80 -s 10.0.1.0/25 [^\n]* -j ACCEPT', result),
        'expected destination addresss 10.0.1.0/25 accepted:\n' + result)

  def testOptions(self):
    self.naming.GetServiceByProto('HTTP', 'tcp').AndReturn(['80'])
    self.mox.ReplayAll()
    acl = iptables.Iptables(policy.ParsePolicy(GOOD_HEADER_1 + GOOD_TERM_3,
                                               self.naming), EXP_INFO)
    result = str(acl)
    self.failUnless('--tcp-flags FIN,RST FIN,RST' in result,
                    'tcp flags missing or incorrect.')
    self.failUnless('-dport 1024:65535' in result,
                    'destination port missing or incorrect.')
    self.failUnless(
        '-m state --state ESTABLISHED,RELATED' in result,
        'missing or incorrect state information.')

  def testRejectReset(self):
    acl = iptables.Iptables(policy.ParsePolicy(GOOD_HEADER_1 + REJECT_TERM1,
                                               self.naming), EXP_INFO)
    result = str(acl)
    self.failUnless('-j REJECT --reject-with tcp-reset' in result,
                    'missing or incorrect reject specification.')

  def testReject(self):
    pol = policy.ParsePolicy(GOOD_HEADER_1 + REJECT_TERM2, self.naming)
    acl = iptables.Iptables(pol, EXP_INFO)
    result = str(acl)
    self.failUnless('-j REJECT --reject-with icmp-host-prohibited' in result,
                    'missing or incorrect reject specification.')

  def testRejectIpv6(self):
    pol = policy.ParsePolicy(IPV6_HEADER_1 + REJECT_TERM2, self.naming)
    acl = iptables.Iptables(pol, EXP_INFO)
    result = str(acl)
    self.failIf('-p all' in result, 'protocol spec present')
    self.failUnless('-j REJECT --reject-with icmp6-adm-prohibited' in result,
                    'missing or incorrect reject specification.')

  def testIPv6Headers(self):
    pol = policy.ParsePolicy(IPV6_HEADER_1 + IPV6_HEADERS, self.naming)
    acl = iptables.Iptables(pol, EXP_INFO)
    result = str(acl)
    self.failUnless('-m u32 --u32 "0x3&0xff=0x0"' in result,
                    'match for hop-by-hop header is missing')
    self.failUnless('-m u32 --u32 "0x3&0xff=0x2c"' in result,
                    'match for fragment header is missing')

  def testNextTerm(self):
    acl = iptables.Iptables(policy.ParsePolicy(GOOD_HEADER_1 + NEXT_TERM1,
                                               self.naming), EXP_INFO)
    result = str(acl)
    self.failUnless('-j RETURN' in result,
                    'jump to RETURN not found.')

  def testProtocols(self):
    acl = iptables.Iptables(policy.ParsePolicy(GOOD_HEADER_1 + GOOD_TERM_4,
                                               self.naming), EXP_INFO)
    result = str(acl)
    self.failUnless('-p tcp' in result, 'protocol tcp not found.')
    self.failUnless('-p udp' in result, 'protocol udp not found.')
    self.failUnless('-p esp' in result, 'protocol esp not found.')
    self.failUnless('-p ah' in result, 'protocol ah not found.')
    self.failUnless('-p gre' in result, 'protocol gre not found.')
    self.failUnless('-p icmp' in result, 'protocol icmp not found.')
    self.failUnless('-p 50' in result, 'protocol 50 not found.')

  def testVerbatimTerm(self):
    acl = iptables.Iptables(policy.ParsePolicy(GOOD_HEADER_1 + GOOD_TERM_5,
                                               self.naming), EXP_INFO)
    result = str(acl)
    self.failUnless('mary had a little lamb' in result,
                    'first verbatim output is missing or incorrect.')
    # check if another platforms verbatim shows up
    self.failIf('mary had a second lamb' in result,
                'second vebatim output is missing or incorrect.')
    self.failIf('mary had a third lamb' in result,
                'third verbatim output is missing or incorrect.')

  def testCommentReflowing(self):
    acl = iptables.Iptables(policy.ParsePolicy(GOOD_HEADER_1 + GOOD_TERM_6,
                                               self.naming), EXP_INFO)
    result = str(acl)
    self.failIf('--comments ""' in result,
                'Iptables cannot handle empty comments')
    self.failIf(re.search('--comments "[^"]{256,}"', result),
                'Iptables comments must be under 255 characters.')
    self.failIf(re.search('--comments "[^"]*\n', result),
                'Iptables comments may not contain newline characters.')

  def testLongTermName(self):
    pol = policy.ParsePolicy(GOOD_HEADER_1 + BAD_LONG_TERM_NAME, self.naming)
    self.assertRaises(aclgenerator.TermNameTooLongError,
                      iptables.Iptables, pol, EXP_INFO)

  def testLongTermAbbreviation(self):
    pol = policy.ParsePolicy(GOOD_HEADER_3 + GOOD_LONG_TERM_NAME, self.naming)
    acl = iptables.Iptables(pol, EXP_INFO)
    result = str(acl)
    self.failUnless('-abbreviations' in result,
                    'Our strings disappeared during abbreviation.')

  def testLongTermTruncation(self):
    pol = policy.ParsePolicy(GOOD_HEADER_4 + GOOD_LONG_TERM_NAME, self.naming)
    acl = iptables.Iptables(pol, EXP_INFO)
    result = str(acl)
    self.failUnless('google-experiment-abbrev' in result,
                    'Our strings disappeared during truncation.')
    self.failIf('google-experiment-abbreviations' in result,
                'Term name was not truncated as expected.')

  def testFragmentOptions(self):
    pol = policy.ParsePolicy(GOOD_HEADER_3 + GOOD_TERM_7, self.naming)
    acl = iptables.Iptables(pol, EXP_INFO)
    result = str(acl)
    self.failUnless('--u32 4&0x3FFF=0x2000' in result,
                    'first-fragment rule is missing')
    self.failUnless('--length 1:119' in result,
                    'length match is missing')
    self.failUnless('--u32 4&0x1FFF=1:119' in result,
                    'fragment-offset rule is missing')

  def testIcmpMatching(self):
    pol = policy.ParsePolicy(GOOD_HEADER_1 + GOOD_TERM_8, self.naming)
    acl = iptables.Iptables(pol, EXP_INFO)
    result = str(acl)
    self.failUnless('--icmp-type 0' in result,
                    'icmp-type 0 (echo-reply) is missing')
    self.failUnless('--icmp-type 3' in result,
                    'icmp-type 3 (destination-unreachable) is missing')
    self.failUnless('--icmp-type 10' in result,
                    'icmp-type 10 (router-solicit) is missing')
    self.failUnless('--icmp-type 15' in result,
                    'icmp-type 15 (info-request) is missing')

  def testConntrackUDP(self):
    pol = policy.ParsePolicy(GOOD_HEADER_1 + UDP_STATE_TERM, self.naming)
    acl = iptables.Iptables(pol, EXP_INFO)
    result = str(acl)
    self.failUnless('-m state --state ESTABLISHED,RELATED' in result,
                    'udp connection tracking is missing state module')
    self.failUnless('-dport 1024:65535' in result,
                    'udp connection tracking is missing destination high-ports')
    self.failUnless('-p udp' in result,
                    'udp connection tracking is missing protocol specification')

  def testConntrackAll(self):
    pol = policy.ParsePolicy(GOOD_HEADER_1 + STATEFUL_ONLY_TERM, self.naming)
    acl = iptables.Iptables(pol, EXP_INFO)
    result = str(acl)
    self.failUnless('-m state --state ESTABLISHED,RELATED' in result,
                    'connection tracking is missing state module arguments')
    self.failIf('-dport 1024:65535' in result,
                'High-ports should not appear for non-TCP/UDP protocols')

  def testTcpEstablishedNostate(self):
    pol = policy.ParsePolicy(NOSTATE_HEADER + TCP_STATE_TERM, self.naming)
    acl = iptables.Iptables(pol, EXP_INFO)
    result = str(acl)
    self.failUnless(
        '-p tcp --tcp-flags ACK ACK --dport 1024:65535 -j ACCEPT' in result,
        'No rule matching TCP packets with ACK bit.\n' + result)
    self.failUnless('%s %s' % ('--tcp-flags ACK,FIN,RST,SYN RST',
                               '--dport 1024:65535 -j ACCEPT') in result,
                    'No rule matching packets with RST bit only.\n' + result)
    self.failIf('--state' in result,
                'Nostate header should not use nf_conntrack --state flag')

  def testUdpEstablishedNostate(self):
    pol = policy.ParsePolicy(NOSTATE_HEADER + UDP_STATE_TERM, self.naming)
    acl = iptables.Iptables(pol, EXP_INFO)
    result = str(acl)
    self.failUnless('-p udp --dport 1024:65535 -j ACCEPT' in result,
                    'No rule matching TCP packets with ACK bit.\n' + result)
    self.failIf('--state' in result,
                'Nostate header should not use nf_conntrack --state flag')

  def testEstablishedNostate(self):
    # when using "nostate" filter and a term with "option:: established"
    # have any protocol other than TCP and/or UDP should raise error.
    pol = policy.ParsePolicy(NOSTATE_HEADER + STATEFUL_ONLY_TERM, self.naming)
    self.assertRaises(aclgenerator.EstablishedError,
                      iptables.Iptables, pol, EXP_INFO)

  def testUnsupportedFilter(self):
    pol = policy.ParsePolicy(GOOD_HEADER_1 + UNSUPPORTED_TERM, self.naming)
    self.assertRaises(aclgenerator.UnsupportedFilterError, iptables.Iptables,
                      pol, EXP_INFO)

  def testUnknownTermKeyword(self):
    pol = policy.ParsePolicy(GOOD_HEADER_1 + UNKNOWN_TERM_KEYWORD, self.naming)
    # Adding a (fake) new property, e.g. if policy.py is updated.
    pol.filters[0][1][0].ip_options_count = '2-255'
    self.assertRaises(aclgenerator.UnsupportedFilterError, iptables.Iptables,
                      pol, EXP_INFO)

  def testProtocolExceptUnsupported(self):
    pol = policy.ParsePolicy(GOOD_HEADER_1 + UNSUPPORTED_EXCEPT, self.naming)
    self.assertRaises(aclgenerator.UnsupportedFilterError, iptables.Iptables,
                      pol, EXP_INFO)

  def testTermNameConflict(self):
    self.mox.ReplayAll()
    pol = policy.ParsePolicy(GOOD_HEADER_2 + GOOD_TERM_1 +
                             GOOD_TERM_1 + GOOD_TERM_1, self.naming)
    self.assertRaises(aclgenerator.DuplicateTermError,
                      iptables.Iptables, pol, EXP_INFO)

  def testMultiPort(self):
    ports = [str(x) for x in range(1, 29, 2)]
    self.naming.GetServiceByProto('FOURTEEN_PORTS', 'tcp').AndReturn(ports)
    self.mox.ReplayAll()
    acl = iptables.Iptables(policy.ParsePolicy(GOOD_HEADER_1 + GOOD_MULTIPORT,
                                               self.naming), EXP_INFO)
    self.failUnless('-m multiport --sports %s' % ','.join(ports) in str(acl),
                    'multiport module not used as expected.')
    # b/10626420
    self.failIf('-m multiport --dports  -d' in str(acl),
                'invalid multiport syntax produced.')

  def testMultiPortWithRanges(self):
    ports = [str(x) for x in 1, 3, 5, 7, 9, 11, 13, 15, 17, '19-21', '23-25',
             '27-29']
    self.naming.GetServiceByProto('FIFTEEN_PORTS_WITH_RANGES',
                                  'tcp').AndReturn(ports)
    self.mox.ReplayAll()
    acl = iptables.Iptables(policy.ParsePolicy(
        GOOD_HEADER_1 + GOOD_MULTIPORT_RANGE, self.naming), EXP_INFO)
    expected = '-m multiport --dports %s' % ','.join(ports).replace('-', ':')
    self.failUnless(expected in str(acl),
                    'multiport module not used as expected.')

  def testMultiportSwap(self):
    self.naming.GetServiceByProto('HTTP', 'tcp').InAnyOrder().AndReturn(['80'])
    self.naming.GetServiceByProto('HTTPS', 'tcp').InAnyOrder(
        ).AndReturn(['443'])
    self.naming.GetServiceByProto('SSH', 'tcp').InAnyOrder().AndReturn(['22'])

    self.mox.ReplayAll()
    acl = iptables.Iptables(policy.ParsePolicy(GOOD_HEADER_1 + MULTIPORT_SWAP,
                                               self.naming), EXP_INFO)
    expected = '--dport 22 -m multiport --sports 80,443'
    self.failUnless(expected in str(acl),
                    'failing to move single port before multiport values.')

  def testMultiportLargePortCount(self):
    ports = [str(x) for x in range(1, 71, 2)]
    self.naming.GetServiceByProto('LOTS_OF_PORTS', 'tcp').AndReturn(ports)
    self.mox.ReplayAll()
    acl = iptables.Iptables(policy.ParsePolicy(
        GOOD_HEADER_1 + LARGE_MULTIPORT, self.naming), EXP_INFO)
    self.failUnless('-m multiport --dports 1,3,5,7,9' in str(acl))
    self.failUnless('-m multiport --dports 29,31,33,35,37' in str(acl))
    self.failUnless('-m multiport --dports 57,59,61,63,65,67,69' in str(acl))

  def testMultiportDualLargePortCount(self):
    ports = [str(x) for x in range(1, 71, 2)]
    self.naming.GetServiceByProto('LOTS_OF_SPORTS', 'tcp').InAnyOrder(
        ).AndReturn(ports)
    self.naming.GetServiceByProto('LOTS_OF_DPORTS', 'tcp').InAnyOrder(
        ).AndReturn(ports)
    self.mox.ReplayAll()
    acl = iptables.Iptables(policy.ParsePolicy(
        GOOD_HEADER_1 + DUAL_LARGE_MULTIPORT, self.naming), EXP_INFO)
    self.failUnless('-m multiport --sports 1,3,5' in str(acl))
    self.failUnless('-m multiport --sports 29,31,33' in str(acl))
    self.failUnless('-m multiport --sports 57,59,61' in str(acl))
    self.failUnless('23,25,27 -m multiport --dports 1,3,5' in str(acl))
    self.failUnless('23,25,27 -m multiport --dports 29,31,33' in str(acl))
    self.failUnless('23,25,27 -m multiport --dports 57,59,61' in str(acl))
    self.failUnless('51,53,55 -m multiport --dports 1,3,5' in str(acl))
    self.failUnless('51,53,55 -m multiport --dports 29,31,33' in str(acl))
    self.failUnless('51,53,55 -m multiport --dports 57,59,61' in str(acl))
    self.failUnless('65,67,69 -m multiport --dports 1,3,5' in str(acl))
    self.failUnless('65,67,69 -m multiport --dports 29,31,33' in str(acl))
    self.failUnless('65,67,69 -m multiport --dports 57,59,61' in str(acl))

  def testGeneratePortBadArguments(self):
    term = iptables.Term(FakeTerm(), 'test', True, 'test')
    # Both source and dest are true
    self.assertRaises(iptables.BadPortsError,
                      term._GeneratePortStatement,
                      [(1, 1), (2, 2)], source=True, dest=True)

  def testGeneratePortNotImplemented(self):
    term = iptables.Term(FakeTerm(), 'test', True, 'test')
    # Both source and dest are false
    self.assertRaises(NotImplementedError,
                      term._GeneratePortStatement,
                      [(1, 1), (2, 2)], source=False, dest=False)

  def testLogging(self):
    pol = policy.ParsePolicy(GOOD_HEADER_1 + LOGGING_TERM_1, self.naming)
    acl = iptables.Iptables(pol, EXP_INFO)
    result = str(acl)
    self.failUnless('-j LOG --log-prefix foo' in result,
                    'logging jump does not appear in output.')
    self.failUnless('-j ACCEPT' in result,
                    'action jump does not appear in output.')

  def testSourceInterface(self):
    pol = policy.ParsePolicy(GOOD_HEADER_1 + SOURCE_INTERFACE_TERM, self.naming)
    acl = iptables.Iptables(pol, EXP_INFO)
    result = str(acl)
    self.failUnless('-i eth0' in result,
                    'source interface specification not in output.')

  def testDestinationInterface(self):
    pol = policy.ParsePolicy(GOOD_HEADER_1 + DESTINATION_INTERFACE_TERM,
                             self.naming)
    acl = iptables.Iptables(pol, EXP_INFO)
    result = str(acl)
    self.failUnless('-o eth0' in result,
                    'destination interface specification not in output.')

  def testExpired(self):
    self.mox.StubOutWithMock(iptables.logging, 'warn')
    # create mock to ensure we warn about expired terms being skipped
    iptables.logging.warn('WARNING: Term %s in policy %s is expired'
                          ' and will not be rendered.', 'is_expired', 'INPUT')
    self.mox.ReplayAll()
    _ = iptables.Iptables(policy.ParsePolicy(GOOD_HEADER_1 + EXPIRED_TERM,
                                             self.naming), EXP_INFO)

  def testExpiringTerm(self):
    self.mox.StubOutWithMock(iptables.logging, 'info')
    # create mock to ensure we inform about expiring terms
    iptables.logging.info('INFO: Term %s in policy %s expires in '
                          'less than two weeks.', 'is_expiring', 'INPUT')
    self.mox.ReplayAll()
    exp_date = datetime.date.today() + datetime.timedelta(weeks=EXP_INFO)
    _ = iptables.Iptables(policy.ParsePolicy(GOOD_HEADER_1 + EXPIRING_TERM %
                                             exp_date.strftime('%Y-%m-%d'),
                                             self.naming), EXP_INFO)

  def testIPv6Icmp(self):
    pol = policy.ParsePolicy(IPV6_HEADER_1 + IPV6_TERM_1, self.naming)
    acl = iptables.Iptables(pol, EXP_INFO)
    result = str(acl)
    self.failUnless('--icmpv6-type 1' in result,
                    'icmpv6-type 1 (echo-reply) is missing')
    self.failUnless('--icmpv6-type 3' in result,
                    'icmpv6-type 3 (destination-unreachable) is missing')
    self.failUnless('--icmpv6-type 129' in result,
                    'icmpv6-type 129 (router-solicit) is missing')

  def testIPv6IcmpOrder(self):
    self.naming.GetNetAddr('IPV6_INTERNAL').InAnyOrder().AndReturn(
        [nacaddr.IPv6('fd87:6044:ac54:3558::/64')])
    self.mox.ReplayAll()
    pol = policy.ParsePolicy(IPV6_HEADER_1 + ICMPV6_TERM_1, self.naming)
    acl = iptables.Iptables(pol, EXP_INFO)
    result = str(acl)
    self.failUnless('-s fd87:6044:ac54:3558::/64 -p ipv6-icmp -m icmp6'
                    ' --icmpv6-type 1' in result,
                    'incorrect order of ICMPv6 match elements')

  def testIcmpv6InetMismatch(self):
    self.mox.StubOutWithMock(iptables.logging, 'debug')
    iptables.logging.debug('Term inet6-icmp will not be rendered,'
                           ' as it has [\'icmpv6\'] match specified but '
                           'the ACL is of inet address family.')
    self.mox.ReplayAll()
    acl = iptables.Iptables(policy.ParsePolicy(GOOD_HEADER_1 + IPV6_TERM_1,
                                               self.naming), EXP_INFO)
    # output happens in __str_
    str(acl)

  def testIcmpInet6Mismatch(self):
    self.mox.StubOutWithMock(iptables.logging, 'debug')
    iptables.logging.debug('Term good-term-1 will not be rendered,'
                           ' as it has [\'icmp\'] match specified but '
                           'the ACL is of inet6 address family.')
    self.mox.ReplayAll()
    acl = iptables.Iptables(policy.ParsePolicy(IPV6_HEADER_1 +
                                               GOOD_TERM_1,
                                               self.naming), EXP_INFO)
    # output happens in __str_
    str(acl)

  def testOwner(self):
    pol = policy.ParsePolicy(GOOD_HEADER_1 + GOOD_TERM_10, self.naming)
    acl = iptables.Iptables(pol, EXP_INFO)
    result = str(acl).split('\n')
    self.failUnless('-A I_good-term-10 -m comment --comment "Owner: '
                    'foo@google.com"' in result,
                    'missing or incorrect comment specification.')

  def testSetTarget(self):
    pol = policy.ParsePolicy(GOOD_HEADER_1 + GOOD_TERM_1, self.naming)
    acl = iptables.Iptables(pol, EXP_INFO)
    acl.SetTarget('OUTPUT', 'DROP')
    result = str(acl).split('\n')
    self.failUnless('-P OUTPUT DROP' in result,
                    'output default policy of drop not set.')

  def testSetCustomTarget(self):
    pol = policy.ParsePolicy(GOOD_HEADER_1 + GOOD_TERM_1, self.naming)
    acl = iptables.Iptables(pol, EXP_INFO)
    acl.SetTarget('foobar')
    result = str(acl).split('\n')
    self.failUnless('-N foobar' in result,
                    'did not find a new chain for foobar.')

if __name__ == '__main__':
  unittest.main()
