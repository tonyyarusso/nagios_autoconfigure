#!/usr/bin/env python
# ======================================================================================================================
# Nagios automatic threshold configuration tool
#
# Copyright: 2013, TIES
# Author: Tony Yarusso <Yarusso@ties.k12.mn.us>
# License: BSD <http://opensource.org/licenses/BSD-3-Clause>
# Homepage: http://ties.k12.mn.us/
# Description: Automatically sets alerting thresholds in Nagios based on past check results
#	This works by analyzing the performance data component of past check results (stored by NDOUtils) to establish
#	the mean (average) values and standard deviations from those values over a defined interval, and reconfiguring
#	Nagios to set the warning and critical alerting thresholds as number of standard deviations away from the mean.
#
# Revision history is kept in Git at https://github.com/tonyyarusso/nagios_autoconfigure
#
# Usage: ./nagios_autoconfigure.py --TBD
# e.g. 
# e.g. 
#
# ----------------------------------------------------------------------------------------------------------------------
#
# Full license text:
#
# Copyright (c) 2013, TIES
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the
# following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this list of conditions and the following
#   disclaimer.
# * Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following
#   disclaimer in the documentation and/or other materials provided with the distribution.
# * Neither the name of TIES nor the names of its contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# ======================================================================================================================


data_db_server = 'localhost'
data_db_user = 'ndoutils'
data_db_pwd = 'n@gweb'
data_db_name = 'nagios'

import MySQLdb as mdb
import sys
import re
import datetime as dt
from numpy import array

def convert_bits(count, prefix):
	if prefix == 'K' or prefix == 'k':
		bits = count * 1024
	elif prefix == 'M' or prefix == 'm':
		bits = count * 1048576
	elif prefix == 'G' or prefix == 'g':
		bits = count * 1073741824
	elif prefix == 'T' or prefix == 't':
		bits = count * 1099511627776
	elif prefix == 'P' or prefix == 'p':
		bits = count * 1125899906842624
	elif prefix is None:
		bits = count
	else:
		print "Unsupported prefix"
		sys.exit(1)
	return int(bits)

now = dt.datetime.now()
lookback = now - dt.timedelta(weeks=4)
window = dt.timedelta(hours=1)
checks_list = []
# Match things in this format: 'in=575.159823Mb/s;800;950 out=22.757955Mb/s;15;25'
perfpattern = re.compile(r'^in=(\d*\.?\d+)(K|k|M|m|G|g|T|t|P|p|E|e)?b/s;(\d*);(\d*) out=(\d*\.?\d+)(K|k|M|m|G|g|T|t|P|p|E|e)?b/s;(\d*);(\d*)$')

conn = mdb.connect(data_db_server, data_db_user, data_db_pwd, data_db_name);

with conn:
	cur = conn.cursor()
	query = "SELECT perfdata FROM nagios_servicechecks \
	             LEFT JOIN nagios_services USING (service_object_id) \
	             LEFT JOIN nagios_hosts USING (host_object_id) \
	             WHERE nagios_services.display_name LIKE '% Bandwidth' \
	             AND nagios_hosts.display_name = 'College Hub 511' \
	             AND nagios_services.display_name = 'HE-Gustavus Bandwidth' \
	             AND state != 3 \
	             AND perfdata IS NOT NULL \
	             AND start_time > '" + lookback.strftime('%Y-%m-%d') + "' \
	             AND DATE_FORMAT(start_time, '%H:%i') > '" + (now).strftime('%H:%M') + "' \
	             AND DATE_FORMAT(start_time, '%H:%i') < '" + (now + window).strftime('%H:%M') + "' \
	             AND DATE_FORMAT(start_time, '%w') = '" + now.strftime('%w') + "' \
	             ORDER BY start_time;"
	cur.execute(query)
	rows = cur.fetchall()
	
	for row in rows:
		# Store perfdata in a tuple like this: ('575.159823', 'M', '800', '950', '22.757955', 'M', '15', '25')
		parsed_row = perfpattern.search(row[0]).groups()
		inbits = convert_bits(float(parsed_row[0]), parsed_row[1])
		inwarn = int(parsed_row[2])
		incrit = int(parsed_row[3])
		outbits = convert_bits(float(parsed_row[4]), parsed_row[5])
		outwarn = int(parsed_row[6])
		outcrit = int(parsed_row[7])
		check_result = ( inbits, inwarn, incrit, outbits, outwarn, outcrit )
		checks_list.append(check_result)
	
	print "Based on " + str(len(checks_list)) + " data points:"
	checks_array = array(checks_list)
	raw_means = list(checks_array.mean(axis=0))
	means = [ int(raw_means[0]), int(raw_means[1]), int(raw_means[2]), int(raw_means[3]), int(raw_means[4]), int(raw_means[5]) ]
	raw_stdvs = list(checks_array.std(axis=0))
	stdvs = [ int(raw_stdvs[0]), int(raw_stdvs[1]), int(raw_stdvs[2]), int(raw_stdvs[3]), int(raw_stdvs[4]), int(raw_stdvs[5]) ]
	print "Means are:"
	print means
	print "Standard deviations are:"
	print stdvs

	import bitconvert
	convertedmeans = []
	for value in means:
		convertedmeans.append(bitconvert.main(["-p", str(value)]))
	print "Converted means are:"
	print convertedmeans
	convertedstdvs = []
	for value in stdvs:
		convertedstdvs.append(bitconvert.main(["-p", str(value)]))
	print "Converted standard deviations are:"
	print convertedstdvs
