#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_quartet_tracelink
------------

Tests for `quartet_tracelink` models module.
"""

from unittest import TestCase

import uuid

from EPCPyYes.core.v1_2.CBV.business_steps import BusinessSteps
from EPCPyYes.core.v1_2.CBV.business_transactions import \
    BusinessTransactionType
# from EPCPyYes.core.v1_2.template_events
from EPCPyYes.core.v1_2.CBV.dispositions import Disposition
from EPCPyYes.core.v1_2.CBV.instance_lot_master_data import \
    InstanceLotMasterDataAttribute, \
    LotLevelAttributeName, ItemLevelAttributeName
from EPCPyYes.core.v1_2.CBV.source_destination import SourceDestinationTypes
from EPCPyYes.core.v1_2.events import BusinessTransaction, \
    Source, Destination, \
    Action
from EPCPyYes.core.v1_2.helpers import gtin_urn_generator, \
    get_current_utc_time_and_offset, gln13_data_to_sgln_urn
from quartet_tracelink.parsing.epcpyyes import ObjectEvent
from quartet_tracelink.parsing.epcpyyes import get_default_environment


class TestQuartet_tr4c3l1nk(TestCase):

    def setUp(self):
        pass

    def test_something(self):
        import EPCPyYes
        from jinja2.loaders import FileSystemLoader
        loader = FileSystemLoader(EPCPyYes.TEMPLATES_PATH)

    def create_epcs(self, start=1000, end=1002):
        # create a range for the number generation
        # (we can use SerialBox as well)
        nums = range(start, end)
        # generate some URNS
        epcs = gtin_urn_generator('305555', '1', '555555', nums)
        return list(epcs)

    def create_business_transaction_list(self):
        business_transaction_list = [
            BusinessTransaction('urn:epcglobal:cbv:bt:0555555555555.DE45_111',
                                BusinessTransactionType.Despatch_Advice),
            BusinessTransaction('urn:epcglobal:cbv:bt:0555555555555.00001',
                                BusinessTransactionType.Bill_Of_Lading)
        ]
        return business_transaction_list

    def create_source_list(self):
        # send in the GLN info
        biz_location = gln13_data_to_sgln_urn(company_prefix='305555',
                                              location_reference='123456')
        read_point = gln13_data_to_sgln_urn(company_prefix='305555',
                                            location_reference='123456',
                                            extension='12')
        # create a source list
        source_list = [
            Source(SourceDestinationTypes.possessing_party.value,
                   biz_location),
            Source(SourceDestinationTypes.location.value, read_point)
        ]
        return biz_location, read_point, source_list

    def create_destination_list(self):
        # create a destination and a destination list
        destination_party = gln13_data_to_sgln_urn(company_prefix='0614141',
                                                   location_reference='00001')
        destination_location = gln13_data_to_sgln_urn(company_prefix='0614141',
                                                      location_reference='00001',
                                                      extension='23')
        destination_list = [
            Destination(SourceDestinationTypes.owning_party.value,
                        destination_party),
            Destination(SourceDestinationTypes.location.value,
                        destination_location)
        ]
        return destination_list

    def create_object_event(self, biz_location, business_transaction_list,
                            destination_list, epcs, now, read_point,
                            source_list, tzoffset, action=None, ilmd=None,
                            biz_step=BusinessSteps.commissioning.value,
                            additional_context={},
                            template='quartet_tracelink/disposition_assigned.xml'):
        env = get_default_environment()
        # create the event
        event_id = str(uuid.uuid4())
        oe = ObjectEvent(now, tzoffset,
                         record_time=now,
                         action=action,
                         epc_list=epcs,
                         biz_step=biz_step,
                         disposition=Disposition.encoded.value,
                         business_transaction_list=business_transaction_list,
                         biz_location=biz_location,
                         read_point=read_point,
                         source_list=source_list,
                         destination_list=destination_list,
                         ilmd=ilmd,
                         event_id=event_id,
                         env=env,
                         template=template)
        if len(additional_context) > 0:
            oe._context = {**oe._context, **additional_context}
        return oe

    def create_object_event_template(self,
                                     biz_step=BusinessSteps.commissioning.value,
                                     template='quartet_tracelink/disposition_assigned.xml'
                                     ):
        epcs = self.create_epcs()
        # get the current time and tz
        now, tzoffset = get_current_utc_time_and_offset()
        business_transaction_list = self.create_business_transaction_list()
        biz_location, read_point, source_list = self.create_source_list()
        destination_list = self.create_destination_list()
        ilmd = [
            InstanceLotMasterDataAttribute(
                name=LotLevelAttributeName.itemExpirationDate.value,
                value='2015-12-31'),
            InstanceLotMasterDataAttribute(
                name=ItemLevelAttributeName.lotNumber.value,
                value='DL232')
        ]
        oe = self.create_object_event(biz_location, business_transaction_list,
                                      destination_list, epcs, now, read_point,
                                      source_list, tzoffset,
                                      action=Action.add.value,
                                      ilmd=ilmd, biz_step=biz_step,
                                      template=template)
        oe.clean()
        return oe

    def test_object_event_template(self):
        oe = self.create_object_event_template()
        # render the event using it's default template
        data = oe.render()
        print(oe.render_json())
        print(oe.render_pretty_json())
        print(data)
        # make sure the data we want is there
        self.assertTrue('+00:00' in data)
        self.assertIn('<epc>urn:epc:id:sgtin:305555.1555555.1000</epc>', data,
                      'URN for start SGTIN not present.')
        self.assertIn('<epc>urn:epc:id:sgtin:305555.1555555.1001</epc>', data,
                      'URN for start SGTIN not present.')
        self.assertIn('<action>ADD</action>', data,
                      'EPCIS action not present.')
        self.assertIn(BusinessSteps.commissioning.value, data,
                      'Business step not present')
        self.assertIn(Disposition.encoded.value, data,
                      'Disposition not present')

    def test_object_event_template_common_attributes(self):
        oe = self.create_object_event_template(
            template='quartet_tracelink/common_attributes.xml'
        )
        oe.lot = 'DL232'
        oe.expiry = '2015-12-31'
        oe.packaging_uom = 'EA'
        oe.NDC = '55555-594-15'
        oe.NDC_pattern = 'US_NDC532'
        oe.is_gtin = True
        oe.packaging_line = 'Line1'
        # render the event using it's default template
        data = oe.render()
        print(oe.render_json())
        print(oe.render_pretty_json())
        print(data)
        # make sure the data we want is there
        self.assertTrue("""<tl:productionLineId>Line1</tl:productionLineId>
<tl:itemDetail>
    <tl:lot>DL232</tl:lot>
    <tl:expiry>2015-12-31</tl:expiry>
    <tl:countryDrugCode type="US_NDC532">55555-594-15</tl:countryDrugCode>
</tl:itemDetail>
</tl:commonAttributes>""" in data)
        self.assertIn('<epc>urn:epc:id:sgtin:305555.1555555.1000</epc>',
                      data,
                      'URN for start SGTIN not present.')
        self.assertIn('<epc>urn:epc:id:sgtin:305555.1555555.1001</epc>',
                      data,
                      'URN for start SGTIN not present.')
        self.assertIn('<action>ADD</action>', data,
                      'EPCIS action not present.')
        self.assertIn(BusinessSteps.commissioning.value, data,
                      'Business step not present')
        self.assertIn(Disposition.encoded.value, data,
                      'Disposition not present')

    def test_shipping_event_template(self):
        oe = self.create_object_event_template(
            biz_step=BusinessSteps.shipping.value)
        # render the event using it's default template
        data = oe.render()
        print(oe.render_json())
        print(oe.render_pretty_json())
        print(data)
        # make sure the data we want is there
        self.assertTrue('+00:00' in data)
        self.assertIn('<epc>urn:epc:id:sgtin:305555.1555555.1000</epc>', data,
                      'URN for start SGTIN not present.')
        self.assertIn('<epc>urn:epc:id:sgtin:305555.1555555.1001</epc>', data,
                      'URN for start SGTIN not present.')
        self.assertIn('<action>ADD</action>', data,
                      'EPCIS action not present.')
        self.assertIn(BusinessSteps.shipping.value, data,
                      'Business step not present')
        self.assertIn(Disposition.encoded.value, data,
                      'Disposition not present')

    def tearDown(self):
        pass
