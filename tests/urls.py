# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import

from django.conf.urls import url, include

from quartet_tracelink.urls import urlpatterns as quartet_tracelink_urls

app_name = 'quartet_tracelink'

urlpatterns = [
    url(r'^', include(quartet_tracelink_urls)),
]
