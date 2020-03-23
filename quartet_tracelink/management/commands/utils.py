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
from django.utils.translation import gettext as _
from django.db.utils import IntegrityError
from quartet_capture import models
from quartet_output.models import EndPoint, EPCISOutputCriteria, \
    AuthenticationInfo


def create_output_filter_rule(rule_name='Tracelink Delayed Output Filter',
                              delay_rule=False):
    create_criteria()
    if not models.Rule.objects.filter(name=rule_name).exists():
        rule = models.Rule.objects.create(
            name=rule_name,
            description=_('Will inspect inbound messages for output '
                          'processing.')
        )
        parse_step = models.Step.objects.create(
            name=_('Inspect EPCIS'),
            description=_(
                'Parse and insepect EPCIS events using output criteria.'),
            step_class='quartet_tracelink.steps.OutputParsingStep',
            order=1,
            rule=rule
        )
        models.StepParameter.objects.create(
            name='EPCIS Output Criteria',
            step=parse_step,
            value='Test Tracelink Transaction Criteria',
            description=_(
                'This is the name of the EPCIS Output Criteria record to use.')

        )
        models.Step.objects.create(
            name=_('Add Commissioning Data'),
            description=_(
                'Adds commissioning events for filtered EPCs and their children.'),
            step_class='quartet_tracelink.steps.AddCommissioningDataStep',
            order=2,
            rule=rule
        )
        models.Step.objects.create(
            name=_('Add Aggregation Data'),
            description=_(
                'Adds aggregation events for included EPCs in any filtered events.'),
            step_class='quartet_output.steps.UnpackHierarchyStep',
            order=3,
            rule=rule
        )
        models.Step.objects.create(
            name=_('Render Tracelink XML'),
            description=_(
                'Pulls any EPCPyYes objects from the context and creates an XML message'),
            step_class='quartet_tracelink.steps.TracelinkOutputStep',
            order=4,
            rule=rule
        )
        output_step = models.Step.objects.create(
            name=_('Queue Outbound Message'),
            description=_('Creates a Task for sending any outbound data'),
            step_class='quartet_output.steps.CreateOutputTaskStep',
            order=5,
            rule=rule
        )
        models.StepParameter.objects.create(
            step=output_step,
            name='Output Rule',
            value='Transport Rule'
        )
        if delay_rule == True:
            second_parse_step = models.Step.objects.create(
                name=_('Inspect EPCIS'),
                description='Used to assign an output criteria to the second '
                            'message for forwarding filtered events.',
                step_class='quartet_tracelink.steps.OutputParsingStep',
                order=6,
                rule=rule
            )
            models.StepParameter.objects.create(
                name='EPCIS Output Criteria',
                step=second_parse_step,
                value='Test Tracelink Transaction Criteria',
                description=_(
                    'This is the name of the EPCIS Output Criteria record to use.')

            )
            render_events = models.Step.objects.create(
                name=_('Render Filtered Events'),
                description=_('Takes any events that were filtered by the '
                              'prior step and renders them to XML for '
                              'sending by the next step.'),
                step_class='quartet_tracelink.steps.TracelinkFilteredEventOutputStep',
                order=7,
                rule=rule
            )
            transform_switch = models.StepParameter.objects.create(
                name='Transform Business Transaction',
                value='True',
                description=_('Whether or not to preform any transformations '
                              'on the business transaction section.  Default:'
                              'False.  Set to True or False.'),
                step=render_events
            )
            trans_source_type = models.StepParameter.objects.create(
                name='Transaction Source Type',
                value='urn:epcglobal:cbv:btt:RMA',
                description='This is the source we are looking to change. '
                            'This value will be replaced with the destination '
                            'type value.',
                step=render_events

            )
            trans_dest_type = models.StepParameter.objects.create(
                name='Transaction Destination Type',
                value='urn:epcglobal:cbv:btt:desadv',
                description='This is the value that will replace the source '
                            'type if the source type is found.',
                step=render_events
            )
            btf = models.StepParameter.objects.create(
                name='Business Transaction Prefix',
                value='urn:epcglobal:cbv:bt:0355555000006:',
                description='This value will be placed in front of any '
                            'businsess transaction identifiers found in '
                            'the source transaction.',
                step=render_events
            )
            replace = models.StepParameter.objects.create(
                name='Replace',
                value='',
                description='This is a value to replace with an empty string'
                            'if the replace value is found.',
                step=render_events
            )
            queue_outbound_message = models.Step.objects.create(
                name='Queue Outbound Message',
                description=_('Creates a task and sends it to the delayed '
                              'transport rule or whatever transport rule is '
                              'configured via the Output Rule step parameter.'),
                step_class='quartet_output.steps.CreateOutputTaskStep',
                order=8,
                rule=rule
            )
            output_rule_param = models.StepParameter.objects.create(
                name='Output Rule',
                description=_('The name of the rule to send the context '
                              'data to.'),
                value='Delayed Transport Rule',
                step=queue_outbound_message
            )
            sdstep = create_transport_rule(rule_name='Delayed Transport Rule',
                                           add_delay=delay_rule)
        sdstep = create_transport_rule()
        return rule


def create_transport_rule(rule_name='Transport Rule', add_delay=False):
    try:
        trule = models.Rule.objects.create(
            name=rule_name,
            description=_(
                'An output Rule for any data filtered by EPCIS Output Criteria '
                'rules.')
        )
        if add_delay:
            delay_step = models.Step.objects.create(
                name=_('Wait Three Seconds'),
                description=_(
                    "Wait for three seconds until moving to the next "
                    "step"),
                step_class='quartet_output.steps.DelayStep',
                rule=trule,
                order=1
            )
            delay_step_param = models.StepParameter.objects.create(
                name='Timeout Interval',
                value='3',
                description=_(
                    'The amount of time in seconds to pause the rule.'),
                step=delay_step
            )

        sdstep = models.Step.objects.create(
            name=_('Send Data'),
            description=_(
                'This will send the task message using the source EPCIS Output '
                'Critria EndPoint and Authentication Info.'),
            step_class='quartet_output.steps.TransportStep',
            order=2,
            rule=trule
        )
    except IntegrityError:
        trule = models.Rule.objects.get(name=rule_name)
    return trule


def create_criteria(endpoint_name='Local Echo Server',
                    username=None,
                    criteria_name=None):
    try:
        endpoint = EndPoint.objects.create(
            name=_(endpoint_name),
            urn=_('http://localhost')
        )
    except IntegrityError:
        print('Endpoint already exists.')
        endpoint = EndPoint.objects.get(name=endpoint_name)
    try:
        auth, created = AuthenticationInfo.objects.get_or_create(
            username=_('Test Tracelink User') or username,
            password=_('Test Tracelink Password'),
            type='Test User',
            description=_('A test user for the example rule.'))
    except IntegrityError:
        print('Authentication info already exists.')
        auth = AuthenticationInfo.objects.get(username='Test Tracelink User')
    try:
        output = EPCISOutputCriteria.objects.create(
            name=_('Test Tracelink Transaction Criteria') or criteria_name,
            action='OBSERVE',
            event_type='Object',
            biz_location='urn:epc:id:sgln:305555.123456.0',
            end_point=endpoint,
            authentication_info=auth
        )
    except IntegrityError:
        print('Criteria already exists.')


def create_itest_endpoint():
    try:
        EndPoint.objects.create(
            name='Tracelink SNX Request',
            urn='https://itestapi.tracelink.com:443/soap/snx/snrequest'
        )
    except IntegrityError:
        print('Tracelink SNX Request endpoing already exists.')


def create_output_step(rule, order=1, skip_parsing='True',
                       criteria_name='Tracelink Output Shipping Criteria'
                       ):
    step = models.Step()
    step.rule = rule
    step.order = order
    step.name = 'Output Determination'
    step.step_class = 'quartet_tracelink.steps.OutputParsingStep'
    step.description = 'unit test step'
    step.save()
    step_parameter = models.StepParameter()
    step_parameter.step = step
    step_parameter.name = 'EPCIS Output Criteria'
    step_parameter.value = criteria_name
    step_parameter.save()
    models.StepParameter.objects.create(
        step=step,
        name='Skip Parsing',
        value=skip_parsing
    )


def create_agg_step(rule):
    step = models.Step()
    step.rule = rule
    step.order = 3
    step.name = 'UnpackHierarchies'
    step.step_class = 'quartet_output.steps.UnpackHierarchyStep'
    step.description = 'Unpack Hierarchies Step'
    step.save()


def create_comm_step(rule):
    step = models.Step()
    step.rule = rule
    step.order = 2
    step.name = 'CreateCommissioning'
    step.step_class = 'quartet_tracelink.steps.AddCommissioningDataStep'
    step.description = 'Retrieve all commissioning info.'
    step.save()


def create_tracelink_epcpyyes_step(rule, append_events='False'):
    step = models.Step()
    step.rule = rule
    step.order = 4
    step.name = 'Create EPCIS'
    step.step_class = 'quartet_tracelink.steps.TraceLinkCommonAttributesOutputStep'
    step.description = 'Creates EPCIS XML or JSON and inserts into rule' \
                       'context.'
    step.save()
    models.StepParameter.objects.create(
        step=step,
        name='Append Filtered Events',
        value=append_events
    )


def create_task_step(rule, order=5, transport_rule='Transport Rule'):
    step = models.Step()
    step.rule = rule
    step.order = order
    step.name = 'Create Output Task'
    step.step_class = 'quartet_output.steps.CreateOutputTaskStep'
    step.description = 'Looks for any EPCIS data on the context and ' \
                       'then, if found, creates a new output task using ' \
                       'the configured Output Rule step parameter.'
    step.save()
    step_parameter = models.StepParameter()
    step_parameter.step = step
    step_parameter.name = 'Output Rule'
    step_parameter.value = transport_rule
    step_parameter.description = 'The name of the rule to create a new ' \
                                 'task with.'
    step_parameter.save()
    step_parameter = models.StepParameter()
    step_parameter.step = step
    step_parameter.name = 'run-immediately'
    step_parameter.value = 'False'
    step_parameter.description = 'The name of the rule to create a new ' \
                                 'task with.'
    step_parameter.save()
    return step

def create_render_shipping_step(rule):
    step = models.Step()
    step.rule = rule
    step.order = 7
    step.name = 'Render Shipping'
    step.step_class = 'quartet_tracelink.steps.TradingPartnerMappingOutputStep'
    step.description = 'Renders a shipping event with partner mappings.'
    step.save()
    return step

def create_common_attributes_rule():
    rule = models.Rule.objects.create(
        name='Tracelink Common Attributes Delayed',
        description='A common attributes rule'
    )
    create_output_step(rule)
    create_comm_step(rule)
    create_agg_step(rule)
    create_tracelink_epcpyyes_step(rule)
    create_task_step(rule)
    create_output_step(rule, skip_parsing='False', order=6,
                       criteria_name='Tracelink Shipping')
    create_render_shipping_step(rule)
    create_task_step(rule, order=8, transport_rule='Delayed Transport Rule')

