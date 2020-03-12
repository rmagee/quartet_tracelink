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

from EPCPyYes.core.v1_2 import template_events, events as yes_events
from gs123.conversion import URNConverter
from quartet_output.models import EPCISOutputCriteria
from quartet_output.parsing import BusinessOutputParser
from quartet_masterdata.models import Company

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
        self.have_checked_company = False
        self.info_func = None

    def get_epcpyyes_object_event(self):
        return template_events.ObjectEvent(
            epc_list=[], quantity_list=[],
            env=get_default_environment(),
            template='quartet_tracelink/disposition_assigned.xml'
        )

    def handle_object_event(self, epcis_event: yes_events.ObjectEvent):
        super().handle_object_event(epcis_event)
        if not self.have_checked_company:
            self.have_checked_company = True
            epc = epcis_event.epc_list[0]
            company_prefix = URNConverter(epc).company_prefix
            try:
                company = Company.objects.get(gs1_company_prefix=company_prefix)
                self.receiver_gln = company.GLN13
            except Company.DoesNotExist:
                self.info('could not find a company for prefix %s', company_prefix)
                logger.debug('Could not find the company for company prefix '
                             '%s ', company_prefix)

    # def parse_unexpected_obj_element(self, oevent, child: etree.Element):
    #     if "transferredToId" in child.tag:
    #         logger.debug('Found a sender GLN')
    #         self.receiver_gln = child.text.strip()

    def info(self, *args):
        if self.info_func:
            self.info_func(*args)
