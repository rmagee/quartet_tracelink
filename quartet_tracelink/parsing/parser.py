# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Copyright 2018 SerialLab Corp.  All rights reserved.
import logging

from EPCPyYes.core.v1_2 import template_events
from quartet_output.models import EPCISOutputCriteria
from quartet_output.parsing import BusinessOutputParser

from quartet_tracelink.parsing.epcpyyes import get_default_environment
from lxml import etree

logger = logging.getLogger(__name__)


class TraceLinkEPCISParser(BusinessOutputParser):

    def __init__(self, stream, epcis_output_criteria: EPCISOutputCriteria,
                 event_cache_size: int = 1024,
                 recursive_decommission: bool = True, skip_parsing=False):
        super().__init__(stream, epcis_output_criteria, event_cache_size,
                         recursive_decommission, skip_parsing)
        self.receiver_gln = None

    def get_epcpyyes_object_event(self):
        return template_events.ObjectEvent(
            epc_list=[], quantity_list=[],
            env=get_default_environment(),
            template='quartet_tracelink/disposition_assigned.xml'
        )

    def parse_unexpected_obj_element(self, oevent, child: etree.Element):
        if "transferredToId" in child.tag:
            logger.debug('Found a sender GLN')
            self.receiver_gln = child.text.strip()
