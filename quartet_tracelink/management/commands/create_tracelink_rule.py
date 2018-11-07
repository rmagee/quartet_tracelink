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
from django.core.management.base import BaseCommand, CommandError
from quartet_capture import models
from quartet_output.models import EndPoint, EPCISOutputCriteria, \
    AuthenticationInfo


class Command(BaseCommand):
    help = _(
        'Loads the quartet_output demonstration and transport rules into '
        'the database.'
    )

    def handle(self, *args, **options):
        endpoint = EndPoint.objects.create(
            name=_('Local SFTP Server'),
            urn=_('sftp://localhost:22')
        )
        auth = AuthenticationInfo.objects.create(
            username=_('Test SFTP User'),
            password=_('Test SFTP Password'),
            type='SSH',
            description=_('A test user for the example rule.')
        )
        output = EPCISOutputCriteria.objects.create(
            name=_('Test TL Criteria'),
            action='ADD',
            event_type='Transaction',
            biz_location='urn:epc:id:sgln:305555.123456.0',
            end_point=endpoint,
            authentication_info=auth
        )
        rule = models.Rule.objects.create(
            name=_('TL EPCIS Output Filter'),
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
            value='Test Transaction Criteria',
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
            name=_('Render EPCIS XML'),
            description=_(
                'Pulls any EPCPyYes objects from the context and creates an XML message'),
            step_class='quartet_output.steps.EPCPyYesOutputStep',
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
            step = output_step,
            name='Output Rule',
            value='SFTP Transport Rule'
        )
        trule = models.Rule.objects.create(
            name=_('SFTP Transport Rule'),
            description=_('An output Rule for any data filtered by EPCIS Output Criteria '
                          'rules.')
        )
        sdstep = models.Step.objects.create(
            name=_('Send Data'),
            description=_('This will send the task message using the source EPCIS Output '
                          'Critria EndPoint and Authentication Info.'),
            step_class='quartet_output.steps.TransportStep',
            order=1,
            rule=trule
        )
        models.StepParameter.objects.create(
            step=sdstep,
            name='Output Rule',
            value='Transport Rule',
            description=_('The rule that will handle any tasks created by this '
                        'step.')
        )
