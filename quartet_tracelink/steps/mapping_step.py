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
from datetime import datetime

from EPCPyYes.core.SBDH import sbdh
from gs123.regex import urn_patterns
from quartet_capture import models
from quartet_capture.rules import RuleContext
from quartet_masterdata.models import OutboundMapping
from quartet_tracelink.steps import TracelinkFilteredEventOutputStep


class TradingPartnerMappingOutputStep(TracelinkFilteredEventOutputStep):

    def __init__(self, db_task: models.Task, **kwargs):
        super().__init__(db_task, **kwargs)
        self.mapping = None
        self.rule_context = None

    def get_mapping(self, filtered_events):
        '''
        Will look for trading partner mappings by pulling the company prefix
        out of the first epc in the message and look up that company in
        the quartet master_material company mapping model.
        :param urns: The urns in the current filtered event.
        :return: A company mapping model instance from the quartet_masterdata
            package.
        '''

        for event in filtered_events:
            if self.mapping: break
            epc_list = getattr(event, 'epc_list')
            if not epc_list:
                epc_list = getattr(event, 'epcs')
            for pattern in urn_patterns:
                match = pattern.match(epc_list[0])
                if match:
                    self.info('Found a matching urn...%s', epc_list[0])
                    fields = match.groupdict()
                    company_prefix = fields['company_prefix']
                    self.info('Using company prefix %s', company_prefix)
                    try:
                        self.mapping = OutboundMapping.objects.get(
                            company__gs1_company_prefix=company_prefix)
                        break
                    except OutboundMapping.DoesNotExist:
                        raise self.CompanyConfigurationError(
                            'The outbound mapping with main company having '
                            ' gs1 company prefix %s does not'
                            ' exist in the database.  Please conifgure this '
                            'company along with an outbound mapping for this '
                            'step to function correctly.' % company_prefix
                        )

    class CompanyConfigurationError(Exception):
        pass

    def additional_context(self, partner_records):
        additional_context = super().additional_context(partner_records)
        additional_context['outbound_mapping'] = self.mapping
        return additional_context

    def process_events(self, events: list):
        self.get_mapping(events)
        return super().process_events(events)

    def generate_sbdh(self, header_version='1.0', sender_sgln=None,
                      receiver_sgln=None, doc_id_standard='EPCGlobal',
                      doc_id_type_version='1.0',
                      doc_id_instance_identifier=None, doc_id_type='Events',
                      creation_date_and_time=None, sender_gln=None,
                      receiver_gln=None):
        sender_gln = self.rule_context.context.get('SENDER_GLN')
        receiver_gln = self.rule_context.context.get('RECEIVER_GLN')
        if sender_gln and receiver_gln:
            return super().generate_sbdh(header_version, sender_sgln,
                                         receiver_sgln, doc_id_standard,
                                         doc_id_type_version,
                                         doc_id_instance_identifier, doc_id_type,
                                         creation_date_and_time, sender_gln,
                                         receiver_gln)

    def pre_execute(self, rule_context: RuleContext):
        self.rule_context = rule_context

