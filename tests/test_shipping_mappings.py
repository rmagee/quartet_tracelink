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
# Copyright 2019 SerialLab Corp.  All rights reserved.

import os

from django.test import TransactionTestCase
from django.conf import settings

from quartet_capture.models import Rule, Step, StepParameter, Task
from quartet_capture.tasks import execute_rule, create_and_queue_task
from quartet_masterdata.models import Location, Company, OutboundMapping
from quartet_output.models import EPCISOutputCriteria, EndPoint
from quartet_templates.models import Template


class TestOutputMappings(TransactionTestCase):
    def __init__(self, methodName: str = ...) -> None:
        super().__init__(methodName)
        self.render_step = None

    def setUp(self) -> None:
        self.create_rule()
        self.create_criteria_rule()
        self.import_trading_partners()
        self.create_outbound_mapping()
        self.create_output_criteria()
        self.parse_test_lot()

    def create_rule(self):
        rule = Rule.objects.create(
            name='Trading Partner Import',
            description='unit test rule'
        )
        step = Step.objects.create(
            name='Parse data',
            step_class='quartet_integrations.oracle.steps.TradingPartnerImportStep',
            description='unit test step',
            order=1,
            rule=rule
        )

    def import_trading_partners(self):
        curpath = os.path.dirname(__file__)
        file_path = os.path.join(curpath, 'data/company_mappings.csv')

        with open(file_path, "rb") as f:
            create_and_queue_task(
                data=f.read(),
                rule_name="Trading Partner Import",
                run_immediately=True
            )
        self.assertEqual(
            Company.objects.all().count(), 40
        )
        self.assertEqual(
            Location.objects.all().count(), 42
        )

    def parse_test_lot(self):
        curpath = os.path.dirname(__file__)
        file_path = os.path.join(curpath, 'data/mapping_lot.xml')

        with open(file_path, "rb") as f:
            create_and_queue_task(
                data=f.read(),
                rule_name="test rule",
                run_immediately=True
            )

    def test_dynamic_template(self):
        StepParameter.objects.create(
            name='Template',
            value='unit test template',
            step=self.render_step
        )
        curpath = os.path.dirname(__file__)
        file_path = os.path.join(curpath, 'data/mapping_shipping.xml')

        with open(file_path, "rb") as f:
            rule = Rule.objects.get(name='test rule')
            db_task = Task.objects.create(
                rule=rule
            )
            context = execute_rule(f.read(), db_task)
            self.assertTrue('<tl:businessId type="GLN">0651991000000'
                            '</tl:businessId>' in
                            context.context['OUTBOUND_EPCIS_MESSAGE'])
            self.assertTrue('<tl:fromBusiness>' in
                            context.context['OUTBOUND_EPCIS_MESSAGE'])

    # def test_dynamic_template_2(self):
    #     StepParameter.objects.create(
    #         name='Template',
    #         value='unit test template 2',
    #         step=self.render_step
    #     )
    #     curpath = os.path.dirname(__file__)
    #     file_path = os.path.join(curpath, 'data/mapping_shipping.xml')
    #
    #     with open(file_path, "rb") as f:
    #         rule = Rule.objects.get(name='test rule')
    #         db_task = Task.objects.create(
    #             rule=rule
    #         )
    #         context = execute_rule(f.read(), db_task)
    #         self.assertTrue('<tl:businessId type="GLN">0651991000000'
    #                         '</tl:businessId>' in
    #                         context.context['OUTBOUND_EPCIS_MESSAGE'])
    #         self.assertTrue('<tl:fromBusiness>' in
    #                         context.context['OUTBOUND_EPCIS_MESSAGE'])

    def test_outbound_mapping(self):
        curpath = os.path.dirname(__file__)
        file_path = os.path.join(curpath, 'data/mapping_shipping.xml')

        with open(file_path, "rb") as f:
            rule = Rule.objects.get(name='test rule')
            db_task = Task.objects.create(
                rule=rule
            )
            context = execute_rule(f.read(), db_task)
            self.assertTrue('<tl:businessId type="GLN">0651991000000'
                            '</tl:businessId>' in
                            context.context['OUTBOUND_EPCIS_MESSAGE'])
            self.assertTrue('<tl:fromBusiness>' in
                            context.context['OUTBOUND_EPCIS_MESSAGE'])

    def create_outbound_mapping(self):
        company = Company.objects.get(
            gs1_company_prefix='0952696005'
        )
        ship_from_co = Company.objects.get(
            gs1_company_prefix='0651991'
        )
        ship_from_location = Location.objects.get(
            GLN13='0962056000006'
        )
        ship_to_co = Company.objects.get(
            gs1_company_prefix='0967914'
        )
        ship_to_location = Location.objects.get(
            GLN13='0967914000201'
        )
        OutboundMapping.objects.create(
            company=company,
            from_business=ship_from_co,
            ship_from=ship_from_location,
            to_business=ship_to_co,
            ship_to=ship_to_location
        )

    def create_output_criteria(self):
        test_endpoint = EndPoint.objects.create(
            urn=getattr(settings, 'TEST_SERVER', 'http://testhost'),
            name='test host'
        )
        output_criteria = EPCISOutputCriteria.objects.create(
            name='Test Criteria',
            biz_step='urn:epcglobal:cbv:bizstep:shipping',
            action='OBSERVE',
            event_type='Object',
            end_point=test_endpoint
        )

    def create_criteria_rule(self):
        rule = Rule.objects.create(
            name='test rule'
        )
        self.create_filter_step(rule)
        self.create_output_step(rule)
        self.create_template()
        self.create_template_2()

    def create_output_step(self, rule, criteria_name='Test Criteria'):
        step = Step()
        step.rule = rule
        step.order = 2
        step.name = 'Output Determination'
        step.step_class = 'quartet_tracelink.steps.TradingPartnerMappingOutputStep'
        step.description = 'unit test step'
        step.save()
        step_parameter = StepParameter()
        step_parameter.step = step
        step_parameter.name = 'EPCIS Output Criteria'
        step_parameter.value = criteria_name
        step_parameter.save()
        self.render_step = step
        return step

    def create_filter_step(self, rule, criteria_name='Test Criteria'):
        step = Step()
        step.rule = rule
        step.order = 1
        step.name = 'Output Determination'
        step.step_class = 'quartet_tracelink.steps.OutputParsingStep'
        step.description = 'unit test step'
        step.save()
        step_parameter = StepParameter()
        step_parameter.step = step
        step_parameter.name = 'EPCIS Output Criteria'
        step_parameter.value = criteria_name
        step_parameter.save()
        return step

    def create_template(self):
        curpath = os.path.dirname(__file__)
        data_path = os.path.join(curpath,
                                 '../quartet_tracelink/templates/quartet_tracelink/tracelink_epcis_events_document.xml')
        data = open(data_path).read()
        Template.objects.create(
            name="unit test template",
            content=data
        )

    def create_template_2(self):
        curpath = os.path.dirname(__file__)
        data_path = os.path.join(curpath,
                                 '../quartet_tracelink/templates/quartet_tracelink/tracelink_epcis_events_document_gln_header.xml')
        data = open(data_path).read()
        Template.objects.create(
            name="unit test template 2",
            content=data
        )
