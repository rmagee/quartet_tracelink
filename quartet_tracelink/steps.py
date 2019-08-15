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
from quartet_capture.rules import RuleContext
from quartet_masterdata.db import DBProxy
from quartet_masterdata.models import Company
from quartet_output import steps
from quartet_output.steps import EPCPyYesOutputStep, ContextKeys
from quartet_tracelink.parsing.epcpyyes import get_default_environment
from quartet_tracelink.parsing.parser import TraceLinkEPCISParser
from quartet_output.steps import DynamicTemplateMixin

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
    def get_parser_type(self):
        """
        Returns the parser that uses the tracelink template EPCPyYes objects.
        """
        return TraceLinkEPCISParser


class TracelinkOutputStep(EPCPyYesOutputStep):
    """
    Will look for any EPCPyYes events in the context and render them to
    XML or JSON depending on the step parameter configuration.
    """

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
                      creation_date_and_time=None):
        '''
        Slap in an SBDH.
        '''
        if sender_sgln and receiver_sgln:
            sender = sbdh.Partner(sbdh.PartnerType.SENDER,
                                  sbdh.PartnerIdentification('GLN',
                                                             self.get_gln_from_sgln(
                                                                 sender_sgln)))
            receiver = sbdh.Partner(sbdh.PartnerType.RECEIVER,
                                    sbdh.PartnerIdentification('GLN',
                                                               self.get_gln_from_sgln(
                                                                   receiver_sgln)))
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
            dt_obj = parser.parse(dt_string).astimezone(timezone('UTC'))
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
                self.convert_dates(event, increment_dates, increment_val)
                if isinstance(event, template_events.ObjectEvent):
                    gtin14 = self._get_gtin(event)
                    if gtin14:
                        event.gtin14 = gtin14
                increment_val += 1

            epcis_document = template_events.EPCISEventListDocument(
                all_events,
                sbdh_out,
                template=env.get_template(
                    'quartet_tracelink/tracelink_epcis_events_document.xml'
                )
            )
            if self.get_boolean_parameter('JSON', False):
                data = epcis_document.render_json()
            else:
                data = epcis_document.render()
            rule_context.context[
                ContextKeys.OUTBOUND_EPCIS_MESSAGE_KEY.value
            ] = data

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


class TracelinkFilteredEventOutputStep(TracelinkOutputStep):
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
            self.transform_event(filtered_events[0])
            self.transform_business_transaction(filtered_events[0])
            dest, source = self.get_sgln_info(filtered_events[0])
            db_records = self.get_partner_info_by_sgln(filtered_events[0])
            sbdh = self.generate_sbdh(
                sender_sgln=source,
                receiver_sgln=dest
            )
            for event in filtered_events:
                self.convert_dates(event)
            epcis_document = template_events.EPCISEventListDocument(
                filtered_events,
                sbdh,
                template=env.get_template(
                    'quartet_tracelink/tracelink_epcis_events_document.xml'
                ),
                additional_context={
                    'masterdata': db_records,
                    'transaction_date': datetime.utcnow().date().isoformat()
                }
            )
            if self.get_boolean_parameter('JSON', False):
                data = epcis_document.render_json()
            else:
                data = epcis_document.render()
            self.info('Warning: this step is overwriting the Outbound '
                      'EPCIS Message key context key data.  If any data '
                      'was in this key prior to this step and had not '
                      'yet been processed, it will have been overwritten.')
            rule_context.context[
                ContextKeys.OUTBOUND_EPCIS_MESSAGE_KEY.value
            ] = data

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

class DaVinciTracelinkOutputStep(TracelinkFilteredEventOutputStep):
    pass
