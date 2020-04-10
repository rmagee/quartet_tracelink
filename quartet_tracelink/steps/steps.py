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
import re
from datetime import datetime
from datetime import timedelta
from dateutil import parser
from pytz import timezone

from EPCPyYes.core.SBDH import sbdh
from EPCPyYes.core.v1_2 import template_events, events
from EPCPyYes.core.v1_2.CBV import dispositions
from gs123.check_digit import calculate_check_digit
from gs123.conversion import URNConverter
from gs123.regex import urn_patterns
from quartet_capture import models, rules
from quartet_capture.rules import RuleContext
from quartet_masterdata.db import DBProxy
from quartet_masterdata.models import Company
from quartet_output import steps
from quartet_output.steps import DynamicTemplateMixin
from quartet_output.steps import EPCPyYesOutputStep, ContextKeys
from quartet_tracelink.parsing.epcpyyes import get_default_environment
from quartet_tracelink.parsing.parser import TraceLinkEPCISParser, \
    TraceLinkEPCISCommonAttributesParser

sgln_regex = re.compile(r'^urn:epc:id:sgln:(?P<cp>[0-9]+)\.(?P<ref>[0-9]+)')


class AddCommissioningDataStep(steps.AddCommissioningDataStep,
                               DynamicTemplateMixin):
    def process_events(self, events: list):
        """
        Changes the default template and environment for the EPCPyYes
        object events.
        """
        env = get_default_environment()
        template = self.get_template(
            env,
            'quartet_tracelink/disposition_assigned.xml'
        )
        for event in events:
            for epc in event.epc_list:
                if ':sscc:' in epc:
                    parsed_sscc = URNConverter(epc)
                    event.company_prefix = parsed_sscc._company_prefix
                    event.extension_digit = parsed_sscc._extension_digit
                    break
            event.template = env.get_template(template)
            event._env = env

        return events


class OutputParsingStep(steps.OutputParsingStep):

    def __init__(self, db_task: models.Task, **kwargs):
        super().__init__(db_task, **kwargs)
        self.data_parser = None
        self.object_event_template = self.get_or_create_parameter(
            'Object Event Template',
            'quartet_tracelink/disposition_assigned.xml',
            'The template to use to render object events.  Should be a '
            'template path- not a quartet_templates template name.'
        )

    def get_parser_type(self, *args):
        """
        Returns the parser that uses the tracelink template EPCPyYes objects.
        """
        return TraceLinkEPCISParser

    def instantiate_parser(self, data, parser_type, skip_parsing):
        self.info(
            'instantiating parser...skip parser set to %s ' % skip_parsing)
        self.parser = super().instantiate_parser(data, parser_type,
                                                 skip_parsing)
        parser.info_func = self.info
        parser.object_event_template = self.object_event_template
        return self.parser


class TracelinkOutputStep(EPCPyYesOutputStep):
    """
    Will look for any EPCPyYes events in the context and render them to
    XML or JSON depending on the step parameter configuration.
    """

    def __init__(self, db_task: models.Task, **kwargs):
        super().__init__(db_task, **kwargs)
        self.object_event_template = self.get_or_create_parameter(
            'Object Event Template',
            'quartet_tracelink/disposition_assigned.xml',
            'The template to use when rendering '
            'object events.')
        self.parse_utc_dates = self.get_or_create_parameter(
            'Parse UTC Dates', 'True', 'Whether or not to parse dates as '
                                       'UTC for tracelink.'
        )
        self.parse_utc_dates = self.parse_utc_dates in ['True', 'true']
        self.convert_date_strings = self.get_boolean_parameter(
            'Convert Dates', False
        )

    def get_gln_from_company(self, sgln):
        '''
        Retrieves GLN13 from company if matched by SGLN.
        '''
        try:
            return Company.objects.get(SGLN=sgln).GLN13
        except Company.DoesNotExist:
            return None

    def get_gln_from_sgln(self, sgln):
        company_gln = self.get_gln_from_company(sgln)
        if company_gln:
            # return the hardcoded version.
            return company_gln
        match = sgln_regex.match(sgln)
        if match:
            parts = match.groups()
            current_length = len(parts[0] + parts[1])
            if current_length < 12:
                gln = parts[0] + (12 - current_length) * '0' + parts[1]
            else:
                gln = parts[0] + parts[1]
            return calculate_check_digit(gln)
        return None

    def generate_sbdh(self, header_version='1.0', sender_sgln=None,
                      receiver_sgln=None, doc_id_standard='EPCGlobal',
                      doc_id_type_version='1.0',
                      doc_id_instance_identifier=None, doc_id_type='Events',
                      creation_date_and_time=None,
                      sender_gln=None,
                      receiver_gln=None,
                      ):
        '''
        Slap in an SBDH.
        '''
        sender = None
        receiver = None
        if sender_sgln and receiver_sgln:
            sender = sbdh.Partner(sbdh.PartnerType.SENDER,
                                  sbdh.PartnerIdentification(
                                      'GLN',
                                      self.get_gln_from_sgln(
                                          sender_sgln))
                                  )
            receiver = sbdh.Partner(sbdh.PartnerType.RECEIVER,
                                    sbdh.PartnerIdentification(
                                        'GLN',
                                        self.get_gln_from_sgln(
                                            receiver_sgln))
                                    )
        elif sender_gln and receiver_gln:
            sender = sbdh.Partner(
                sbdh.PartnerType.SENDER,
                sbdh.PartnerIdentification('GLN', sender_gln)
            )
            receiver = sbdh.Partner(
                sbdh.PartnerType.RECEIVER,
                sbdh.PartnerIdentification('GLN', receiver_gln)
            )

        if sender and receiver:
            partner_list = [sender, receiver]
            creation_date_and_time = creation_date_and_time or datetime.utcnow().isoformat()
            creation_date_and_time = self.format_datetime(
                creation_date_and_time)
            document_identification = sbdh.DocumentIdentification(
                creation_date_and_time=creation_date_and_time
            )
            return sbdh.StandardBusinessDocumentHeader(
                partners=partner_list,
                document_identification=document_identification
            )
        return None

    def format_datetime(self, dt_string, increment_dates=False,
                        increment_val=0):
        try:
            if self.parse_utc_dates:
                dt_obj = parser.parse(dt_string).astimezone(timezone('UTC'))
            else:
                dt_obj = parser.parse(dt_string)
            if increment_dates:
                dt_obj = dt_obj + timedelta(seconds=increment_val)
            return dt_obj.strftime('%Y-%m-%dT%H:%M:%SZ')
        except:
            return dt_string

    def execute(self, data, rule_context: RuleContext):
        """
        Pulls the object, agg, transaction and other events out of the context
        for processing.  See the step parameters
        :param data: The original message (not used by this step).
        :param rule_context: The RuleContext containing any filtered events
        and also any EPCPyYes events that were created by prior steps.
        """
        self.pre_execute(rule_context)
        env = get_default_environment()
        self.rule_context = rule_context
        append_filtered_events = self.get_boolean_parameter(
            'Append Filtered Events', True)
        prepend_filtered_events = self.get_boolean_parameter(
            'Prepend Filtered Events', False
        )
        increment_dates = self.get_boolean_parameter(
            'Increment Dates', False
        )
        oevents = rule_context.context.get(ContextKeys.OBJECT_EVENTS_KEY.value,
                                           [])
        for event in oevents:
            event.template = self.object_event_template

        aggevents = rule_context.context.get(
            ContextKeys.AGGREGATION_EVENTS_KEY.value, [])
        if append_filtered_events:
            if prepend_filtered_events:
                all_events = self.get_filtered_events() + oevents + aggevents
            else:
                all_events = oevents + aggevents + self.get_filtered_events()
        else:
            all_events = oevents + aggevents
        sbdh_out = None
        if len(all_events) > 0:
            increment_val = 0
            for event in self.get_filtered_events():
                if event.source_list and event.destination_list:
                    destination_sgln, source_sgln = self.get_sgln_info(event)
                    sbdh_out = self.generate_sbdh(
                        sender_sgln=source_sgln,
                        receiver_sgln=destination_sgln
                    )
                    break
            for event in all_events:
                # tracelink is terrible at handling ISO dates so here we go...
                if self.convert_date_strings:
                    self.convert_dates(event, increment_dates, increment_val)
                if isinstance(event, template_events.ObjectEvent):
                    gtin14 = self._get_gtin(event)
                    if gtin14:
                        event.gtin14 = gtin14
                increment_val += 1
            template_path = self.get_or_create_parameter(
                'Template Path',
                'quartet_tracelink/tracelink_epcis_events_document.xml',
                'The jinja 2 template to render.'
            )
            additional_context = {
                'RECEIVER_GLN': rule_context.context.get('RECEIVER_GLN'),
                'SENDER_GLN': rule_context.context.get('SENDER_GLN')
            }
            if additional_context['RECEIVER_GLN'] and additional_context[
                'SENDER_GLN']:
                self.info('Using the values in the context to generate the '
                          'header.')
                sbdh_out = self.generate_sbdh(
                    receiver_gln=rule_context.context.get('RECEIVER_GLN'),
                    sender_gln=rule_context.context.get('SENDER_GLN')
                )
                self.info('SBDH: %s', sbdh_out)
            self.info('Template path: %s', template_path)
            epcis_document = template_events.EPCISEventListDocument(
                all_events,
                sbdh_out,
                template=env.get_template(template_path),
                additional_context=additional_context
            )
            if self.get_boolean_parameter('JSON', False):
                data = epcis_document.render_json()
            else:
                data = epcis_document.render()
            rule_context.context[
                ContextKeys.OUTBOUND_EPCIS_MESSAGE_KEY.value
            ] = data
            self.info('Data (first 2000 characters): %s', data[:1000])

    def convert_dates(self, event, increment_dates=False, increment_val=0):
        if event.event_time.endswith(
            '+00:00') and event.event_timezone_offset != '+00:00':
            converted_dt_string = re.sub(r"\+00:00$",
                                         event.event_timezone_offset,
                                         event.event_time)
            event.event_time = self.format_datetime(
                converted_dt_string, increment_dates, increment_val)
        else:
            event.event_time = self.format_datetime(event.event_time,
                                                    increment_dates,
                                                    increment_val)
        if event.record_time:
            event.record_time = self.format_datetime(event.record_time,
                                                     increment_dates,
                                                     increment_val)

    def pre_execute(self, rule_context: RuleContext):
        """
        Override to do anything with filtered events, etc. before execution.
        :return: None
        """
        pass

    def get_sgln_info(self, event):
        """
        Looks in the inbound message and grabs any SGLN information from
        the extension where the source and destination are defined.
        :param event: The event to look through.
        :return: The SGLNs defined for source and destination owning parties.
        """
        source_sgln = None
        destination_sgln = None
        for source in event.source_list:
            if 'owning_party' in source.type:
                source_sgln = source.source
        for destination in event.destination_list:
            if 'owning_party' in destination.type:
                destination_sgln = destination.destination
        return destination_sgln, source_sgln

    def _get_gtin(self, event: template_events.ObjectEvent):
        """
        Will iterate through the event epcs and get the gtin 14 value
        to support tracelink proprietary messages.
        :param event:
        :return: Will return a gtin14 if it finds an sgtin urn, otherwise
        it will return none.
        """
        for epc in event.epc_list:
            if epc.startswith('urn:epc:id:sgtin:'):
                result = URNConverter(epc)
                return result.gtin14

    def declared_parameters(self):
        ret = super().declared_parameters()
        ret['Template Name'] = 'Jinja 2 template path to override.  Not the ' \
                               'name of a qu4rtet template.'
        return ret


class TracelinkFilteredEventOutputStep(TracelinkOutputStep,
                                       DynamicTemplateMixin):
    """
    Very similar to the EPCPyYesOutput step except that this step will
    only render the filtered events and place them into the same outbound
    OUTBOUND_EPCIS_MESSAGE_KEY context key for processing by a
    CreateOutputTaskStep later in the rule for example.
    """

    def execute(self, data, rule_context: RuleContext):
        """
        Will pull any filtered events off of the rule context using the
        FILTERED_EVENTS_KEY context key.
        :param data: The data coming into the step from the rule.
        :param rule_context: A reference to the rule context.
        """
        self.rule_context = rule_context
        env = get_default_environment()
        self.rule_context = rule_context
        increment_dates = self.get_boolean_parameter(
            'Increment Dates', False
        )
        filtered_events = self.get_filtered_events()
        self.info('Found %s filtered events.' % len(filtered_events))
        if len(filtered_events) > 0:
            self.process_events(filtered_events)
            self.transform_event(filtered_events[0])
            self.transform_business_transaction(filtered_events[0])
            dest, source = self.get_sgln_info(filtered_events[0])
            db_records = self.get_partner_info_by_sgln(filtered_events[0])
            sbdh = self.generate_sbdh(
                sender_sgln=source,
                receiver_sgln=dest
            )
            if self.convert_date_strings:
                for event in filtered_events:
                    self.convert_dates(event)
            epcis_document = template_events.EPCISEventListDocument(
                filtered_events,
                sbdh,
                template=self.get_template(env, 'quartet_tracelink/tracelink_'
                                                'epcis_events_document.xml'),
                additional_context=self.additional_context(db_records)
            )
            if self.get_boolean_parameter('JSON', False):
                data = epcis_document.render_json()
            else:
                data = epcis_document.render()
                self.info('Rendering: %s', data
                          )
            self.info('Warning: this step is overwriting the Outbound '
                      'EPCIS Message key context key data.  If any data '
                      'was in this key prior to this step and had not '
                      'yet been processed, it will have been overwritten.')
            rule_context.context[
                ContextKeys.OUTBOUND_EPCIS_MESSAGE_KEY.value
            ] = data

    def additional_context(self, partner_records):
        """
        Override this to add or modify the additional context passed to the
        tracelink EPCPyYes events.
        :param partner_records: Trading partner records for the header
        master data.
        :return: The additional context dictionary to use when rendering
        templates.  This context is supplemental to the one EPCPyYes expects
        natively.
        """
        return {
            'masterdata': partner_records,
            'transaction_date': datetime.utcnow().date().isoformat()
        }

    def transform_event(self, event: events.EPCISBusinessEvent):
        """
        Override this to transform any data in a filtered event.
        :param event: The event that was filtered.
        :return: None.
        """
        if not event.disposition:
            event.disposition = self.get_parameter(
                'Default Disposition',
                dispositions.Disposition.in_transit.value
            )

    def transform_business_transaction(self, event: events.EPCISBusinessEvent):
        """
        Transforms an inbound event into a different one since Tracelink
        has very odd support for EPCIS.  As of this writing they only
        support despatch advice events for shipping business steps.  Strange.
        :param event: The event with the business step to transform.
        :return: None
        """
        if self.get_boolean_parameter('Transform Business Transaction', False):
            transaction_source_type = self.get_parameter(
                'Transaction Source Type')
            transaction_destination_type = self.get_parameter(
                'Transaction Destination Type')
            business_transaction_prefix = self.get_parameter(
                'Business Transaction Prefix', '')
            replace = self.get_parameter('Replace', '')

            for transaction in event.business_transaction_list:
                if transaction.type == transaction_source_type:
                    transaction.type = transaction_destination_type
                    val = '%s%s' % (business_transaction_prefix,
                                    transaction.biz_transaction.strip()
                                    .replace(replace, ''))
                    transaction.biz_transaction = val

    def get_partner_info_by_sgln(self, event):
        """
        Will lookup partner info based on the SGLNs in the source and
        destination events.
        :return: A list of epcpyyes partner events.
        """
        sglns = []
        proxy = DBProxy()
        for source in event.source_list:
            sglns.append(source.source)
        for destination in event.destination_list:
            sglns.append(destination.destination)
        return proxy.get_epcis_master_data_locations(sglns)

    @property
    def declared_parameters(self):
        return {
            'Transform Business Transaction': 'Bookean, default is False.  If this is true,'
                                              ' the step will attempt to transform a business '
                                              'transaction using the parameters below.',
            'Transaction Source Type': 'The transaction event type you are '
                                       'looking to transform.  If found, the '
                                       'step will attempt to transform it.',
            'Transaction Destination Type': 'This will be the replaced '
                                            'value.',
            'Business Transaction Prefix': 'If this is specified, the step '
                                           'will append this to any business '
                                           'transactions that are being '
                                           'transformed.',
            'Replace': 'Put a string value you would like to replace in '
                       'the business transaction source transaction string. ',
            'Default Disposition': 'If no disposition is specified, use this '
                                   'value.  Must be full URN.'
        }

    def on_failure(self):
        pass
