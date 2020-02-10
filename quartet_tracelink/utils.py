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
from django.utils.translation import gettext as _
from quartet_capture import models as capture_models
from quartet_output import models as output_models
from quartet_templates import models as template_models
from list_based_flavorpack.models import ListBasedRegion, ProcessingParameters
from serialbox import models as sb_models


class TraceLinkHelper:
    """
    Will create number range configurations and all associated end points
    and processing rules, etc.
    """
    processing_class_path = ('list_based_flavorpack.processing_classes.'
                             'third_party_processing.processing.'
                             'ThirdPartyProcessingClass')

    prod_numbers = 'https://api.tracelink.com:443/soap/snx/snrequest'
    dev_numbers = 'https://itestapi.tracelink.com:443/soap/snx/snrequest'
    nr_transport_step = 'list_based_flavorpack.steps.NumberRequestTransportStep'
    nr_response_parser = ('quartet_integrations.tracelink.steps.DBResponseStep')

    def create_number_rule(self):
        self.create_rule()
        self.create_example_pool()


    def create_rule(self):
        rule, created = capture_models.Rule.objects.get_or_create(
            name="Tracelink Number Request"
        )
        if created:
            rule.description = 'Requests numbers from Tracelink - To be used ' \
                               'from Number Range module (Allocate)'
            rule.save()
            step_1 = capture_models.Step()
            step_1.name = 'Number Request Transport Step'
            step_1.description = ('Requests numbers and passes the response '
                                  'to the next step (for parsing)')
            step_1.step_class = ('list_based_flavorpack.steps.'
                                 'NumberRequestTransportStep')
            step_1.order = 1
            step_1.rule = rule
            step_1.save()
            capture_models.StepParameter.objects.create(
                name='content-type',
                value='text/xml',
                step=step_1
            )
            step_2 = capture_models.Step()
            step_2.name = 'Tracelink Number Reponse Parser'
            step_2.description = ('Parses numbers from Tracelink and writes '
                                  'them persistently for use in Number '
                                  'Range module.')
            step_2.step_class = self.nr_response_parser
            step_2.order = 2
            step_2.rule = rule
            step_2.save()
        return rule

    def create_endpoints(self):
        """
        Returns a two-tuple with the itest EndPoint model reference and
        the production.  Will create one or both if they do not exist.
        :return: itest, prod EndPoint instances.
        """
        try:
            itest = output_models.EndPoint.objects.get(
                name='Tracelink iTest Number Request'
            )
        except output_models.EndPoint.DoesNotExist:
            itest = output_models.EndPoint.objects.create(
                name='Tracelink iTest Number Request',
                urn='https://itestapi.tracelink.com:443/soap/snx/snrequest'
            )
        try:
            prod = output_models.EndPoint.objects.get(
                name='Tracelink Production Number Request'
            )
        except output_models.EndPoint.DoesNotExist:
            prod = output_models.EndPoint.objects.create(
                name='Tracelink Production Number Request',
                urn='https://api.tracelink.com:443/soap/snx/snrequest'
            )
        return itest, prod

    def create_example_authentication(self):
        try:
            auth = output_models.AuthenticationInfo.objects.get(
                username='example_user'
            )
        except output_models.AuthenticationInfo.DoesNotExist:
            auth = output_models.AuthenticationInfo.objects.create(
                username='example_user',
                password='example',
                description='Example auth.',
                type='Basic'
            )
        return auth

    def create_example_pool(self):
        itest, prod = self.create_endpoints()
        template = self.create_template()
        pool, created = sb_models.Pool.objects.get_or_create(
            readable_name='Example Tracelink Pool',
            machine_name='00355555123459'
        )
        if created:
            region = ListBasedRegion(
                readable_name='Example Tracelink Region',
                machine_name='00355555123459',
                active=True,
                order=1,
                number_replenishment_size=5000,
                processing_class_path='list_based_flavorpack.processing_classes.third_party_processing.processing.DBProcessingClass',
                end_point=itest,
                rule=self.create_rule(),
                authentication_info=self.create_example_authentication(),
                template=template,
                pool=pool
            )
            region.save()
            params = {
                'randomized_number':'X',
                'object_key_value':'GTIN Value Goes Here',
                'object_key_name':'GTIN',
                'encoding_type':'SGTIN',
                'id_type':'GS1_SER',
                'receiving_system': 'Receiving GLN 13 Goes Here',
                'sending_system': 'Sender GLN 13 Goes Here'
            }
            self.create_processing_parameters(params, region)

    def create_template(self):
        curpath = os.path.dirname(__file__)
        f = open(os.path.join(curpath,
                              './templates/quartet_tracelink/number_request.xml'))
        template_text = f.read()
        f.close()
        try:
            template = template_models.Template.objects.get(
                name='Tracelink Number Request'
            )
        except template_models.Template.DoesNotExist:
            template = template_models.Template.objects.create(
                name='Tracelink Number Request',
                content=template_text,
                description='Tracelink number request template.'
            )
        return template

    def create_processing_parameters(self, input: dict, region):
        for k, v in input.items():
            try:
                ProcessingParameters.objects.get(key=k,
                                                 list_based_region=region)
            except ProcessingParameters.DoesNotExist:
                ProcessingParameters.objects.create(key=k,
                                                    value=v,
                                                    list_based_region=region)


def create_example_rule(rule_name="TraceLink EPCIS Output Filter"):
    try:
        endpoint = output_models.EndPoint.objects.get(
            name=('Tracelink Example SFTP Server')
        )
        print(
            '\033[0;31;40m Found existing endpoint with location %s' % endpoint.urn)
    except output_models.EndPoint.DoesNotExist:
        endpoint = output_models.EndPoint.objects.create(
            name=_('Tracelink Example SFTP Server'),
            urn=_(
                'sftp://itestb2b.tracelink.com:5022/home/[*** CUSTOMER FOLDER ****]/inbox/SNX_DISPOSITION_ASSIGNED/')
        )
        print(
            "\033[0;32;40m Created a new endpoint- MAKE sure to change the URN value!!! \n")

    try:
        auth = output_models.AuthenticationInfo.objects.get(
            username=('Test SFTP User')
        )
        print(
            '\033[0;31;40m Found existing Authentication Info instance for test sftp user.')
    except output_models.AuthenticationInfo.DoesNotExist:
        auth = output_models.AuthenticationInfo.objects.create(
            username=_('Test SFTP User'),
            password=_('Test SFTP Password'),
            type='SSH',
            description=_('A test user for the example rule.')
        )
        print('\033[0;32;40m created a new authenticaiton info instance.')
    try:
        output = output_models.EPCISOutputCriteria.objects.get(
            name=_('Test TL Criteria')
        )
        print('\033[0;31;40m found an existing Output Criteria.')
    except output_models.EPCISOutputCriteria.DoesNotExist:
        output = output_models.EPCISOutputCriteria.objects.create(
            name=_('Test TL Criteria'),
            action='ADD',
            event_type='Transaction',
            biz_location='urn:epc:id:sgln:305555.123456.0',
            end_point=endpoint,
            authentication_info=auth
        )
        print('\033[0;32;40m Created a new Output Criteria.')
    try:
        rule = capture_models.Rule.objects.get(
            name=rule_name
        )
        print('\033[0;31;40m found an existing example rule!')
    except:
        rule = capture_models.Rule.objects.create(
            name=rule_name,
            description=_('Will inspect inbound messages for output '
                          'processing.')
        )
        parse_step = capture_models.Step.objects.create(
            name=_('Inspect EPCIS'),
            description=_(
                'Parse and insepect EPCIS events using output criteria.'),
            step_class='quartet_tracelink.steps.OutputParsingStep',
            order=1,
            rule=rule
        )
        capture_models.StepParameter.objects.create(
            name='EPCIS Output Criteria',
            step=parse_step,
            value='Test Transaction Criteria',
            description=_(
                'This is the name of the EPCIS Output Criteria record to use.')

        )
        capture_models.Step.objects.create(
            name=_('Add Commissioning Data'),
            description=_(
                'Adds commissioning events for filtered EPCs and their children.'),
            step_class='quartet_tracelink.steps.AddCommissioningDataStep',
            order=2,
            rule=rule
        )
        capture_models.Step.objects.create(
            name=_('Add Aggregation Data'),
            description=_(
                'Adds aggregation events for included EPCs in any filtered events.'),
            step_class='quartet_output.steps.UnpackHierarchyStep',
            order=3,
            rule=rule
        )
        capture_models.Step.objects.create(
            name=_('Render Tracelink XML'),
            description=_(
                'Pulls any EPCPyYes objects from the context and creates an XML message'),
            step_class='quartet_tracelink.steps.TracelinkOutputStep',
            order=4,
            rule=rule
        )
        output_step = capture_models.Step.objects.create(
            name=_('Queue Outbound Message'),
            description=_('Creates a Task for sending any outbound data'),
            step_class='quartet_output.steps.CreateOutputTaskStep',
            order=5,
            rule=rule
        )
        capture_models.StepParameter.objects.create(
            step=output_step,
            name='Output Rule',
            value='SFTP Transport Rule'
        )
    try:
        trule = capture_models.Rule.objects.get(
            name='SFTP Transport Rule'
        )
        print('\033[0;31;40m found an existing SFTP transport rule!')
    except capture_models.Rule.DoesNotExist:
        trule = capture_models.Rule.objects.create(
            name=_('SFTP Transport Rule'),
            description=_(
                'An output Rule for any data filtered by EPCIS Output Criteria '
                'rules.')
        )
        sdstep = capture_models.Step.objects.create(
            name=_('Send Data'),
            description=_(
                'This will send the task message using the source EPCIS Output '
                'Critria EndPoint and Authentication Info.'),
            step_class='quartet_output.steps.TransportStep',
            order=1,
            rule=trule
        )
        capture_models.StepParameter.objects.create(
            step=sdstep,
            name='Output Rule',
            value='Transport Rule',
            description=_(
                'The rule that will handle any tasks created by this '
                'step.')
        )
        print('\033[0;32;40m created a new example SFTP transport rule!')
    print('\033[0;37;40m Complete.')
