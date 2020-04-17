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
# Copyright 2020 SerialLab Corp.  All rights reserved.

from EPCPyYes.core.v1_2 import template_events
from gs123.conversion import URNConverter
from quartet_capture import models
from quartet_capture.rules import RuleContext
from quartet_masterdata.db import DBProxy
from quartet_masterdata.models import Company
from quartet_output.steps import ContextKeys
from quartet_tracelink.steps import TracelinkOutputStep
from quartet_epcis.models import Entry

class TraceLinkCommonAttributesOutputStep(TracelinkOutputStep):

    def __init__(self, db_task: models.Task, **kwargs):
        super().__init__(db_task, **kwargs)
        self.proxy = DBProxy()
        self.lot = None
        self.expiry = None
        self.trade_items = {}
        self.uom_choices = {'Bdl': 'PK', 'Cs': 'CA', 'Ea': 'EA', 'Bx': 'EA',
                            'EA': 'EA'}
        self.packaging_line = None
        self.NDC_pattern = None
        self.object_event_template = 'quartet_tracelink/common_attributes.xml'
        self.have_checked_company = False
        self.last_trade_item = None

    def pre_execute(self, rule_context: RuleContext):
        # get the filtered events
        events = rule_context.context.get(ContextKeys.OBJECT_EVENTS_KEY.value,
                                          [])
        # object_event: template_events.ObjectEvent
        for object_event in events:
            self.get_receiver_gln(object_event, rule_context)
            self.get_sender_gln(rule_context)
            object_event.template = self.object_event_template
            self.get_lot_expiry(object_event)
            self.get_common_attributes(object_event)

    def get_lot_expiry(self, epcis_event: template_events.ObjectEvent):
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
        trade_item_urn = urn[:urn.rindex('.')]
        trade_item = self.trade_items.get(urn)
        if not trade_item:
            trade_item = self.proxy.get_trade_item_by_urn(urn)
            if trade_item:
                self.trade_items[trade_item_urn] = trade_item
        return trade_item

    def get_common_attributes(self, epcis_event: template_events.ObjectEvent):
        """
        If an object event with a GTIN this will look up trade item information
        and assign to fields on the epcis_event.
        :param epcis_event: The ObjectEvent
        :return: None
        """
        urn = epcis_event.epc_list[0]
        epcis_event.packaging_line = self.get_packaging_line(epcis_event)
        if 'gtin' in urn:
            trade_item = self.get_trade_item(urn)
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
                self.last_trade_item = trade_item
        if 'sscc' in urn:
            entry = Entry.objects.get(identifier=urn)
            epcis_event.company_prefix = URNConverter(urn).company_prefix
            if not entry.parent_id:
                # if there is an sscc and there is no parent it is a pallet
                epcis_event.packaging_uom = 'PL'
            elif 'sscc' in entry.parent_id.identifier and not entry.parent_id.parent_id:
                # if there is an sscc and the parent has no parent it is a case
                epcis_event.packaging_uom = 'CA'
            else:
                # if there is an sscc and the parent has a parent it is a pack
                epcis_event.packaging_uom = 'PK'
            if self.last_trade_item:
                epcis_event.NDC_pattern = self.NDC_pattern
                epcis_event.NDC = self.last_trade_item.NDC
            epcis_event.is_gtin = False if not entry.parent_id else True

    def get_uom(self, uom: str):
        ret = self.uom_choices.get(uom)
        if not ret: raise self.UOMNotFoundError('Could not find a UOM mapping '
                                                'for %s', uom)
        return ret

    def get_ndc_string(self, ndc_pattern: str):
        if not self.NDC_pattern:
            self.NDC_pattern = 'US_NDC%s' % ndc_pattern.replace('-', '')
        return self.NDC_pattern

    def get_packaging_line(self, epcis_event: template_events.ObjectEvent):
        """
        Uses the serial portion of the SGLN to create the line name.
        :param epcis_event: The event
        :return: The formatted line name.
        """
        if not self.packaging_line:
            urn = epcis_event.read_point
            self.packaging_line = "Line%s" % urn[urn.rindex('.') + 1:]
        return self.packaging_line

    def get_receiver_gln(self, epcis_event: template_events.ObjectEvent,
                         rule_context: RuleContext):
        if not self.have_checked_company:
            self.have_checked_company = True
            epc = epcis_event.epc_list[0]
            company_prefix = URNConverter(epc).company_prefix
            try:
                company = Company.objects.get(
                    gs1_company_prefix=company_prefix)
                rule_context.context['RECEIVER_GLN'] = company.GLN13
            except Company.DoesNotExist:
                raise self.CompanyNotFoundError(
                    'could not find a company for prefix %s',
                    company_prefix)

    def get_sender_gln(self, rule_context):
        rule_context.context['SENDER_GLN'] = self.get_parameter(
            'Sender GLN',
            raise_exception=True
        )



    class UOMNotFoundError(Exception):
        pass

    class TradeItemNotFoundError(Exception):
        pass

    class CompanyNotFoundError(Exception):
        pass
