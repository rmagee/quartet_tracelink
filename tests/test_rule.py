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
import os

from django.test import TestCase
from django.conf import settings
from EPCPyYes.core.v1_2.CBV.business_steps import BusinessSteps
from EPCPyYes.core.v1_2.CBV.dispositions import Disposition
from EPCPyYes.core.v1_2.events import EventType
from quartet_capture.models import Rule, Step, StepParameter, Task
from quartet_capture.tasks import execute_rule, execute_queued_task
from quartet_epcis.parsing.business_parser import BusinessEPCISParser
from quartet_masterdata.models import Company, Location
from quartet_output import models
from quartet_output.models import EPCISOutputCriteria
from quartet_output.steps import SimpleOutputParser, ContextKeys
from quartet_templates.models import Template


class TestRules(TestCase):

    def test_rule_with_agg_comm(self):
        self._create_good_ouput_criterion()
        db_rule = self._create_rule()
        self._create_step(db_rule)
        self._create_output_steps(db_rule)
        self._create_comm_step(db_rule)
        self._create_epcpyyes_step(db_rule)
        db_task = self._create_task(db_rule)
        curpath = os.path.dirname(__file__)
        # prepopulate the db
        self._parse_test_data('data/commission_one_event.xml')
        self._parse_test_data('data/nested_pack.xml')
        data_path = os.path.join(curpath, 'data/ship_pallet.xml')
        with open(data_path, 'r') as data_file:
            context = execute_rule(data_file.read().encode(), db_task)
            self.assertEqual(
                len(context.context[ContextKeys.AGGREGATION_EVENTS_KEY.value]),
                3,
                "There should be three filtered events."
            )
            for event in context.context[
                ContextKeys.AGGREGATION_EVENTS_KEY.value]:
                if event.parent_id in ['urn:epc:id:sgtin:305555.3555555.1',
                                       'urn:epc:id:sgtin:305555.3555555.2']:
                    self.assertEqual(len(event.child_epcs), 5)
                else:
                    self.assertEqual(len(event.child_epcs), 2)
            self.assertIsNotNone(
                context.context.get(
                    ContextKeys.EPCIS_OUTPUT_CRITERIA_KEY.value)
            )

    def test_delayed_shipment(self):
        self._create_company_from_sgln('urn:epc:id:sgln:309999.111111.0')
        self._create_company_from_sgln('urn:epc:id:sgln:305555.123456.0', type=Location)
        self._create_company_from_sgln('urn:epc:id:sgln:305555.123456.12')
        self._create_company_from_sgln('urn:epc:id:sgln:309999.111111.233', type=Location)
        self._create_shipping_ouput_criterion(event_type=EventType.Object.value)
        db_rule = self._create_rule()
        self._create_step(db_rule, criteria_name='Shipping Criteria')
        self._create_output_steps(db_rule)
        self._create_comm_step(db_rule)
        self._create_epcpyyes_step(db_rule)
        curpath = os.path.dirname(__file__)
        # prepopulate the db
        self._parse_test_data('data/commission_one_event.xml')
        self._parse_test_data('data/nested_pack.xml')
        data_path = os.path.join(curpath, 'data/no-commit-ship.xml')
        delay_rule = create_output_filter_rule(delay_rule=True)
        db_task2 = self._create_task(delay_rule)
        with open(data_path, 'r') as data_file:
            context = execute_rule(data_file.read().encode(), db_task2)
            self.assertEqual(
                len(context.context[ContextKeys.AGGREGATION_EVENTS_KEY.value]),
                3,
            )
            for event in context.context[
                ContextKeys.AGGREGATION_EVENTS_KEY.value]:
                if event.parent_id in ['urn:epc:id:sgtin:305555.3555555.1',
                                       'urn:epc:id:sgtin:305555.3555555.2']:
                    self.assertEqual(len(event.child_epcs), 5)
                else:
                    self.assertEqual(len(event.child_epcs), 2)
            self.assertIsNotNone(
                context.context.get(
                    ContextKeys.EPCIS_OUTPUT_CRITERIA_KEY.value)
            )


    def test_rule_with_agg_comm_output(self):
        self._create_good_ouput_criterion()
        db_rule = self._create_rule()
        self._create_step(db_rule)
        self._create_output_steps(db_rule)
        self._create_comm_step(db_rule)
        self._create_template()
        self._create_tracelink_epcpyyes_step(db_rule, use_template=True)
        self._create_task_step(db_rule)
        db_rule2 = self._create_transport_rule()
        self._create_transport_step(db_rule2)
        db_task = self._create_task(db_rule)
        curpath = os.path.dirname(__file__)
        # prepopulate the db
        self._parse_test_data('data/commission_one_event.xml')
        self._parse_test_data('data/nested_pack.xml')
        data_path = os.path.join(curpath, 'data/ship_pallet.xml')
        with open(data_path, 'r') as data_file:
            context = execute_rule(data_file.read().encode(), db_task)
            self.assertEqual(
                len(context.context[ContextKeys.AGGREGATION_EVENTS_KEY.value]),
                3,
                "There should be three filtered events."
            )
            for event in context.context[
                ContextKeys.AGGREGATION_EVENTS_KEY.value]:
                if event.parent_id in ['urn:epc:id:sgtin:305555.3555555.1',
                                       'urn:epc:id:sgtin:305555.3555555.2']:
                    self.assertEqual(len(event.child_epcs), 5)
                else:
                    self.assertEqual(len(event.child_epcs), 2)
            task_name = context.context[ContextKeys.CREATED_TASK_NAME_KEY]
            execute_queued_task(task_name=task_name)
            task = Task.objects.get(name=task_name)
            self.assertEqual(task.status, 'FINISHED')

    def test_rule_with_agg_comm_sftp_output(self):
        self._create_destination_criterion()
        db_rule = self._create_rule()
        self._create_step(db_rule)
        self._create_output_steps(db_rule)
        self._create_comm_step(db_rule)
        self._create_tracelink_epcpyyes_step(db_rule)
        self._create_task_step(db_rule)
        db_rule2 = self._create_transport_rule()
        self._create_transport_step(db_rule2)
        db_task = self._create_task(db_rule)
        curpath = os.path.dirname(__file__)
        # prepopulate the db
        self._parse_test_data('data/1-b.xml')
        data_path = os.path.join(curpath, 'data/2-b.xml')
        with open(data_path, 'r') as data_file:
            context = execute_rule(data_file.read().encode(), db_task)
            # self.assertEqual(
            #     len(context.context[ContextKeys.AGGREGATION_EVENTS_KEY.value]),
            #     78,
            #     "There should be 78 events."
            # )
            task_name = context.context[ContextKeys.CREATED_TASK_NAME_KEY]
            execute_queued_task(task_name=task_name)
            task = Task.objects.get(name=task_name)
            self.assertEqual(task.status, 'FINISHED')

    def test_rule_with_agg_comm_sftp_output_with_company_match(self):
        self.create_company_masterdata()
        self._create_bitter_waterfall_criterion()
        db_rule = self._create_rule()
        self._create_step(db_rule)
        self._create_output_steps(db_rule)
        self._create_comm_step(db_rule)
        self._create_tracelink_epcpyyes_step(db_rule)
        self._create_task_step(db_rule)
        db_rule2 = self._create_transport_rule()
        self._create_transport_step(db_rule2)
        db_task = self._create_task(db_rule)
        curpath = os.path.dirname(__file__)
        # prepopulate the db
        self._parse_test_data('data/bitter-waterfall.xml')
        data_path = os.path.join(curpath, 'data/bitter-waterfall-ship.xml')
        with open(data_path, 'r') as data_file:
            context = execute_rule(data_file.read().encode(), db_task)
            task_name = context.context[ContextKeys.CREATED_TASK_NAME_KEY]
            execute_queued_task(task_name=task_name)
            task = Task.objects.get(name=task_name)
            self.assertEqual(task.status, 'FINISHED')

    def _create_destination_criterion(self):
        endpoint = self._create_sftp_endpoint()
        auth = self._create_sftp_auth()
        eoc = EPCISOutputCriteria()
        eoc.name = "Test Criteria"
        eoc.action = "OBSERVE"
        eoc.disposition = Disposition.in_transit.value
        eoc.biz_step = BusinessSteps.shipping.value
        eoc.destination_id='urn:epc:id:sgln:030378.6.0'
        eoc.authentication_info = auth
        eoc.end_point = endpoint
        eoc.save()
        return eoc

    def _create_good_ouput_criterion(self, event_type=EventType.Transaction.value):
        endpoint = self._create_endpoint()
        auth = self._create_auth()
        eoc = EPCISOutputCriteria()
        eoc.name = "Test Criteria"
        eoc.event_type = event_type
        eoc.biz_step = BusinessSteps.shipping.value
        eoc.biz_location = 'urn:epc:id:sgln:305555.123456.0'
        eoc.read_point = 'urn:epc:id:sgln:305555.123456.12'
        eoc.source_type = 'urn:epcglobal:cbv:sdt:location'
        eoc.source_id = 'urn:epc:id:sgln:305555.123456.12'
        eoc.destination_type = 'urn:epcglobal:cbv:sdt:location'
        eoc.destination_id = 'urn:epc:id:sgln:309999.111111.233'
        eoc.authentication_info = auth
        eoc.end_point = endpoint
        eoc.save()
        return eoc

    def _create_shipping_ouput_criterion(self, event_type=EventType.Object.value):
        endpoint = self._create_endpoint()
        auth = self._create_auth()
        eoc = EPCISOutputCriteria()
        eoc.name = "Shipping Criteria"
        eoc.event_type = event_type
        eoc.biz_step = BusinessSteps.shipping.value
        eoc.authentication_info = auth
        eoc.end_point = endpoint
        eoc.save()
        return eoc

    def _create_good_header_criterion(self):
        endpoint = self._create_endpoint()
        auth = self._create_auth()
        eoc = EPCISOutputCriteria()
        eoc.name = "Test Criteria"
        eoc.receiver_identifier = 'urn:epc:id:sgln:039999.111111.0'
        eoc.authentication_info = auth
        eoc.end_point = endpoint
        eoc.save()
        return eoc

    def _create_template(self):
        template_data = """<ObjectEvent>
            {% include "epcis/event_times.xml" %}
            {% include "epcis/base_extension.xml" %}
            {% if event.epc_list %}
                <epcList>
                    {% for epc in event.epc_list %}
                        <epc>{{ epc }}</epc>
                    {% endfor %}
                </epcList>
            {% endif %}
            {% include "epcis/business_data.xml" %}
            {% include "epcis/extension.xml" %}
            {% if additional_context and event.biz_step and 'shipping' in event.biz_step %}
                {% include "quartet_tracelink/shipping_event_extension.xml" %}
            {% else %}
                {% include "quartet_tracelink/disposition_assigned_extension.xml" %}
            {% endif %}
        </ObjectEvent>
        """
        Template.objects.create(
            content=template_data,
            name='unit test template',
            description='template for unit tests.'
        )

    def _create_good_header_criterion(self):
        eoc = EPCISOutputCriteria()
        eoc.name = 'Test Criteria'
        eoc.receiver_identifier = 'urn:epc:id:sgln:039999.111111.0'
        eoc.end_point = self._create_endpoint()
        eoc.authentication_info = self._create_auth()
        eoc.save()
        return eoc

    def _create_bitter_waterfall_criterion(self):
        endpoint = self._create_sftp_endpoint()
        auth = self._create_sftp_auth()
        eoc = EPCISOutputCriteria()
        eoc.name = "Test Criteria"
        eoc.action = "OBSERVE"
        eoc.disposition = Disposition.in_transit.value
        eoc.biz_step = BusinessSteps.shipping.value
        eoc.destination_id = 'urn:epc:id:sgln:2014121.60010.0'
        eoc.authentication_info = auth
        eoc.end_point = endpoint
        eoc.save()
        return eoc

    def _create_endpoint(self):
        ep = models.EndPoint()
        ep.urn = getattr(settings, 'TEST_SERVER', 'http://testhost')
        ep.name = 'Test EndPoint'
        ep.save()
        return ep

    def _create_auth(self):
        auth = models.AuthenticationInfo()
        auth.description = 'Unit test auth.'
        auth.username = 'UnitTestUser'
        auth.password = 'UnitTestPassword'
        auth.save()
        return auth

    def _create_sftp_endpoint(self):
        ep = models.EndPoint()
        ep.urn = 'sftp://testsftphost:22/upload'
        ep.name = 'Test EndPoint'
        ep.save()
        return ep

    def _create_sftp_auth(self):
        auth = models.AuthenticationInfo()
        auth.description = 'Unit test auth.'
        auth.username = 'foo'
        auth.password = 'pass'
        auth.save()
        return auth

    def create_company_masterdata(self):
        company = Company()
        company.name = "Test Company"
        company.SGLN = 'urn:epc:id:sgln:2014121.60010.0'
        company.GLN13 = '2014121600101'
        company.company_prefix = '2014121'
        company.save()

    def _create_bad_criterion(self):
        eoc = EPCISOutputCriteria()
        eoc.name = "Test Criteria"
        eoc.action = "DELETE"
        eoc.event_type = EventType.Transaction.value
        endpoint = self._create_endpoint()
        auth = self._create_auth()
        eoc.end_point = endpoint
        eoc.authentication_info = auth
        eoc.save()
        return eoc

    def _parse_data(self, output_criteria):
        curpath = os.path.dirname(__file__)
        parser = SimpleOutputParser(
            os.path.join(curpath, 'data/epcis.xml'),
            output_criteria
        )
        parser.parse()
        parser.clear_cache()

    def _create_rule(self):
        rule = Rule()
        rule.name = 'TraceLink Output'
        rule.description = 'Inspect Inbound Message and Create TraceLink Output'
        rule.save()
        return rule

    def _create_transport_rule(self):
        rule = Rule()
        rule.name = 'Transport Rule'
        rule.description = 'Attempts to send data using transport step(s).'
        rule.save()
        return rule

    def _create_transport_step(self, rule, put_data='False'):
        step = Step()
        step.rule = rule
        step.order = 1
        step.name = 'Transport'
        step.step_class = 'quartet_output.steps.TransportStep'
        step.description = 'Sends test data.'
        step.save()
        step_parameter = StepParameter()
        step_parameter.step = step
        step_parameter.name = 'run-immediately'
        step_parameter.value = 'True'
        step_parameter.save()
        step_parameter = StepParameter()
        step_parameter.step = step
        step_parameter.name = 'put-data'
        step_parameter.value = put_data
        step_parameter.save()

    def _create_step(self, rule, criteria_name='Test Criteria'):
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

    def _create_output_steps(self, rule):
        step = Step()
        step.rule = rule
        step.order = 2
        step.name = 'UnpackHierarchies'
        step.step_class = 'quartet_output.steps.UnpackHierarchyStep'
        step.description = 'unit test unpacking step'
        step.save()

    def _create_comm_step(self, rule):
        step = Step()
        step.rule = rule
        step.order = 3
        step.name = 'CreateCommissioning'
        step.step_class = 'quartet_tracelink.steps.AddCommissioningDataStep'
        step.description = 'unit test commissioning step'
        step.save()

    def _create_epcpyyes_step(self, rule):
        step = Step()
        step.rule = rule
        step.order = 4
        step.name = 'Create EPCIS'
        step.step_class = 'quartet_output.steps.EPCPyYesOutputStep'
        step.description = 'Creates EPCIS XML or JSON and inserts into rule' \
                           'context.'
        step.save()

    def _create_tracelink_epcpyyes_step(self, rule, use_template=True):
        step = Step()
        step.rule = rule
        step.order = 4
        step.name = 'Create EPCIS'
        step.step_class = 'quartet_tracelink.steps.TracelinkOutputStep'
        step.description = 'Creates EPCIS XML or JSON and inserts into rule' \
                           'context.'
        step.save()
        if use_template:
            sp = StepParameter.objects.create(
                name='Template',
                value='unit test template',
                step=step
            )

    def _create_company_from_sgln(self, sgln, type=Company):
        from gs123.check_digit import calculate_check_digit
        gln13 = sgln.split(':')[-1]
        gln13 = gln13.split('.')
        gln13 = '%s%s' % (gln13[0], gln13[1])
        gln13 = calculate_check_digit(gln13)
        print('gln = %s', gln13)
        type.objects.create(
            name='unit test company %s' % gln13,
            GLN13=gln13,
            SGLN=sgln,
            address1='123 Unit Test Street',
            address2='Unit 2028',
            postal_code='12345',
            city='Unit Testville',
            state_province='PA',
            country='US'
        )

    def _create_task(self, rule):
        task = Task()
        task.rule = rule
        task.name = 'unit test task'
        task.save()
        return task

    def _add_forward_data_step_parameter(self, step: Step):
        step_parameter = StepParameter()
        step_parameter.step = step
        step_parameter.name = 'Forward Data'
        step_parameter.value = 'True'
        step_parameter.description = 'Whether or not to construct new data ' \
                                     'or to just forward the data in the ' \
                                     'rule.'
        step_parameter.save()

    def _create_task_step(self, rule):
        step = Step()
        step.rule = rule
        step.order = 5
        step.name = 'Create Output Task'
        step.step_class = 'quartet_output.steps.CreateOutputTaskStep'
        step.description = 'Looks for any EPCIS data on the context and ' \
                           'then, if found, creates a new output task using ' \
                           'the configured Output Rule step parameter.'
        step.save()
        step_parameter = StepParameter()
        step_parameter.step = step
        step_parameter.name = 'Output Rule'
        step_parameter.value = 'Transport Rule'
        step_parameter.description = 'The name of the rule to create a new ' \
                                     'task with.'
        step_parameter.save()
        step_parameter = StepParameter()
        step_parameter.step = step
        step_parameter.name = 'run-immediately'
        step_parameter.value = 'True'
        step_parameter.description = 'The name of the rule to create a new ' \
                                     'task with.'
        step_parameter.save()
        return step

    def _parse_test_data(self, test_file='data/epcis.xml',
                         parser_type=BusinessEPCISParser,
                         recursive_decommission=False):
        curpath = os.path.dirname(__file__)
        if isinstance(parser_type, BusinessEPCISParser):
            parser = parser_type(
                os.path.join(curpath, test_file),
                recursive_decommission=recursive_decommission
            )
        else:
            parser = parser_type(
                os.path.join(curpath, test_file),
            )
        message_id = parser.parse()
        print(parser.event_cache)
        parser.clear_cache()
        return message_id, parser
