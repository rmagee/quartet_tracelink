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
from quartet_capture.rules import Step
from quartet_output import steps
from quartet_tracelink.parsing.epcpyyes import get_default_environment
from quartet_tracelink.parsing.parser import TraceLinkEPCISParser
from gs123.conversion import URNConverter
from quartet_output.steps import EPCPyYesOutputStep, ContextKeys, \
    FilteredEventStepMixin
from quartet_capture.rules import RuleContext
from EPCPyYes.core.v1_2 import template_events
from EPCPyYes.core.SBDH import sbdh
from gs123.check_digit import calculate_check_digit
from dateutil import parser
from pytz import timezone
from quartet_masterdata.models import Company


sgln_regex = re.compile(r'^urn:epc:id:sgln:(?P<cp>[0-9]+)\.(?P<ref>[0-9]+)')


class AddCommissioningDataStep(steps.AddCommissioningDataStep):
    def process_events(self, events: list):
        """
        Changes the default template and environment for the EPCPyYes
        object events.
        """
        env = get_default_environment()
        for event in events:
            for epc in event.epc_list:
                if ':sscc:' in epc:
                    parsed_sscc = URNConverter(epc)
                    event.company_prefix = parsed_sscc._company_prefix
                    event.extension_digit = parsed_sscc._extension_digit
                    break
            event.template = env.get_template(
                'quartet_tracelink/disposition_assigned.xml')
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
            current_length =  len(parts[0] + parts[1])
            if current_length < 12:
                gln = parts[0] + (12-current_length) * '0' + parts[1]
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
                                                             self.get_gln_from_sgln(sender_sgln)))
            receiver = sbdh.Partner(sbdh.PartnerType.RECEIVER,
                                    sbdh.PartnerIdentification('GLN',
                                                               self.get_gln_from_sgln(receiver_sgln)))
            partner_list = [sender, receiver]
            return sbdh.StandardBusinessDocumentHeader(partners=partner_list)
        return None

    def format_datetime(self, dt_string):
        dt_obj = parser.parse(dt_string).astimezone(timezone('UTC'))
        return dt_obj.strftime('%Y-%m-%dT%H:%M:%SZ')
        
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
            for event in self.get_filtered_events():
                if event.source_list and event.destination_list:
                    source_sgln = None
                    destination_sgln = None
                    for source in event.source_list:
                        if 'owning_party' in source.type:
                            source_sgln = source.source
                    for destination in event.destination_list:
                        if 'owning_party' in destination.type:
                            destination_sgln = destination.destination
                    sbdh_out = self.generate_sbdh(
                        sender_sgln=source_sgln,
                        receiver_sgln=destination_sgln
                    )
                    break
            for event in all_events:
                if event.event_time.endswith('+00:00') and event.event_timezone_offset != '+00:00':
                    converted_dt_string = re.sub(r"\+00:00$", event.event_timezone_offset, event.event_time)
                    event.event_time = self.format_datetime(converted_dt_string)
                else:
                    event.event_time = self.format_datetime(event.event_time)

                if event.record_time:
                    event.record_time = self.format_datetime(event.record_time)
            
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
