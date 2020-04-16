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
from quartet_integrations.gs1ushc.mixins import ConversionMixin
from quartet_masterdata.models import Company
from quartet_masterdata.db import DBProxy
from quartet_output.models import EPCISOutputCriteria
from quartet_output.parsing import BusinessOutputParser
from quartet_tracelink.parsing.epcpyyes import get_default_environment

logger = logging.getLogger(__name__)


class TraceLinkEPCISParser(ConversionMixin, BusinessOutputParser):

    def __init__(self, stream, epcis_output_criteria: EPCISOutputCriteria,
                 event_cache_size: int = 1024,
                 recursive_decommission: bool = True, skip_parsing=False,
                 object_event_template=None):
        super().__init__(stream, epcis_output_criteria, event_cache_size,
                         recursive_decommission, skip_parsing)
        self.receiver_gln = None
        self.have_checked_company = False
        self.info_func = None
        self.proxy = DBProxy()
        self.object_event_template = object_event_template or 'quartet_tracelink/disposition_assigned.xml'

    def get_epcpyyes_object_event(self):
        return template_events.ObjectEvent(
            epc_list=[], quantity_list=[],
            env=get_default_environment(),
            template=self.object_event_template
        )

    def info(self, *args):
        if self.info_func:
            self.info_func(*args)


class TraceLinkEPCISCommonAttributesParser(TraceLinkEPCISParser):
    """
    Handles the insane tracelink garbage formats.
    """

    def __init__(self, stream, epcis_output_criteria: EPCISOutputCriteria,
                 event_cache_size: int = 1024,
                 recursive_decommission: bool = True, skip_parsing=False,
                 object_event_template=None):
        super().__init__(stream, epcis_output_criteria, event_cache_size,
                         recursive_decommission, skip_parsing,
                         object_event_template)
        self.lot = None
        self.expiry = None
        self.trade_items = {}
        self.uom_choices = {'Bdl': 'PK', 'Cs': 'CA', 'Ea': 'EA', 'Bx': 'EA'}
        self.packaging_line = None
        self.NDC_pattern = None
        self.object_event_template = object_event_template or 'quartet_tracelink/common_attributes.xml'

    def handle_object_event(self, epcis_event: yes_events.ObjectEvent):
        super().handle_object_event(epcis_event)
        if not self.lot:
            self.get_lot_expiry(epcis_event)
        self.get_common_attributes(epcis_event)
        if not self.have_checked_company:
            self.have_checked_company = True
            epc = epcis_event.epc_list[0]
            company_prefix = URNConverter(epc).company_prefix
            try:
                company = Company.objects.get(
                    gs1_company_prefix=company_prefix)
                self.receiver_gln = company.GLN13
            except Company.DoesNotExist:
                self.info('could not find a company for prefix %s',
                          company_prefix)
                logger.debug('Could not find the company for company prefix '
                             '%s ', company_prefix)

    def get_epcpyyes_object_event(self):
        return template_events.ObjectEvent(
            epc_list=[], quantity_list=[],
            env=get_default_environment(),
            template=self.object_event_template
        )

    def get_lot_expiry(self, epcis_event: yes_events.ObjectEvent):
        """
        Gets the lot and epiry from the ilmd in the Object Event (if present)
        and assigns those values to fields of the event for rendering in a
        template
        :param epcis_event: An EPCPyYes object event.
        :return: None
        """
        if self.lot:
            epcis_event.lot = self.lot
            epcis_event.expiry = self.expiry
        elif len(epcis_event.ilmd) > 0:
            for ilmd in epcis_event.ilmd:
                if 'lot' in ilmd.name:
                    self.lot = ilmd.value
                    epcis_event.lot = ilmd.value
                    self.info('Using lot %s', self.lot)
                if 'expir' in ilmd.name.lower():
                    self.expiry = ilmd.value
                    epcis_event.expiry = ilmd.value
                    self.info('Using expiry %s', self.expiry)

    def get_trade_item(self, urn):
        """
        Returns a trade item from the local cache or the database.
        :param urn: The urn to use to find the trade item
        :return: A TradeItem model instance.
        """
        trade_item = self.trade_items.get(
            urn[:urn.rindex('.')]) or self.proxy.get_trade_item_by_urn(urn)

    def get_common_attributes(self, epcis_event: yes_events.ObjectEvent):
        """
        If an object event with a GTIN this will look up trade item information
        and assign to fields on the epcis_event.
        :param epcis_event: The ObjectEvent
        :return: None
        """
        urn = epcis_event.epc_list[0]
        self.get_packaging_line(epcis_event)
        if 'gtin' in urn:
            trade_item = self.proxy.get_trade_item_by_urn(urn)
            if not trade_item:
                raise self.TradeItemNotFoundError(
                    'Could not find a corresponding trade item for URN %s' %
                    urn
                )
            epcis_event.is_gtin = True
            if trade_item:
                epcis_event.packaging_uom = self.get_uom(
                    trade_item.package_uom)
                epcis_event.NDC = trade_item.NDC
                epcis_event.NDC_pattern = self.get_ndc_string(
                    trade_item.NDC_pattern)
        if 'sscc' in urn:
            epcis_event.company_prefix = URNConverter(urn).company_prefix
            epcis_event.packaging_uom = 'PL'
            epcis_event.is_gtin = False
            epcis_event.NDC_pattern = self.NDC_pattern

    def get_uom(self, uom: str):
        ret = self.uom_choices.get(uom)
        if not ret: raise self.UOMNotFoundError('Could not find a UOM mapping '
                                                'for %s', uom)
        return ret

    def get_ndc_string(self, ndc_pattern: str):
        if not self.NDC_pattern:
            self.NDC_pattern = 'US_NDC%s' % ndc_pattern.replace('-', '')
        return self.NDC_pattern

    def get_packaging_line(self, epcis_event: yes_events.ObjectEvent):
        """
        Uses the serial portion of the SGLN to create the line name.
        :param epcis_event: The event
        :return: The formatted line name.
        """
        if not self.packaging_line:
            urn = epcis_event.read_point
            self.packaging_line = "Line%s" % urn[urn.rindex('.')+1:]
        return self.packaging_line

    class UOMNotFoundError(Exception):
        pass

    class TradeItemNotFoundError(Exception):
        pass

