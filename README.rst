=============================
quartet_tracelink
=============================

.. image:: https://gitlab.com/serial-lab/quartet_tracelink/badges/master/coverage.svg
   :target: https://gitlab.com/serial-lab/quartet_tracelink/pipelines
.. image:: https://gitlab.com/serial-lab/quartet_tracelink/badges/master/pipeline.svg
   :target: https://gitlab.com/serial-lab/quartet_tracelink/commits/master
.. image:: https://badge.fury.io/py/quartet_tracelink.svg
    :target: https://badge.fury.io/py/quartet_tracelink

An EPCIS to TraceLink Codec that overcomes (or tries to) many of the
quirks, garbage, non-standard BS and other well-known shortcomings of the Tracelink EPCIS interface.

Documentation
-------------

The full documentation is at https://serial-lab.gitlab.io/quartet_tracelink/

Quickstart
----------

Install quartet_tracelink::

    pip install quartet_tracelink

Add it to your `INSTALLED_APPS`:

.. code-block:: python

    INSTALLED_APPS = (
        ...
        'quartet_tracelink.apps.QuartetTracelinkConfig',
        ...
    )

Add quartet_tracelink's URL patterns:

.. code-block:: python

    from quartet_tracelink import urls as quartet_tracelink_urls


    urlpatterns = [
        ...
        url(r'^', include(quartet_tracelink_urls)),
        ...
    ]


Running Tests
-------------

Does the code actually work?

::

    source <YOURVIRTUALENV>/bin/activate
    (myenv) $ pip install tox
    (myenv) $ tox

