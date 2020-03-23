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
from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _

from quartet_tracelink.management.commands.utils import \
    create_common_attributes_rule

# Rule.objects.filter(name='Tracelink Common Attributes Delayed').delete()

class Command(BaseCommand):
    help = _(
        'Loads the quartet_output demonstration and transport rules into '
        'the database. to reset, launch the django shell and :'
        'Rule.objects.filter(name=\'Tracelink Common Attributes Delayed\').delete()'
    )

    def handle(self, *args, **options):
        create_common_attributes_rule()
