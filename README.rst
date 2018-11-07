=============================
quartet_tr4c3l1nk
=============================

.. image:: https://gitlab.com/serial-lab/quartet_tr4c3l1nk/badges/master/coverage.svg
   :target: https://gitlab.com/serial-lab/quartet_tr4c3l1nk/pipelines
.. image:: https://gitlab.com/serial-lab/quartet_tr4c3l1nk/badges/master/build.svg
   :target: https://gitlab.com/serial-lab/quartet_tr4c3l1nk/commits/master
.. image:: https://badge.fury.io/py/quartet_tr4c3l1nk.svg
    :target: https://badge.fury.io/py/quartet_tr4c3l1nk

An EPCIS to TraceLink Codec

Documentation
-------------

The full documentation is at https://serial-lab.gitlab.io/quartet_tr4c3l1nk/

Quickstart
----------

Install quartet_tr4c3l1nk::

    pip install quartet_tr4c3l1nk

Add it to your `INSTALLED_APPS`:

.. code-block:: python

    INSTALLED_APPS = (
        ...
        'quartet_tr4c3l1nk.apps.QuartetTr4c3l1nkConfig',
        ...
    )

Add quartet_tr4c3l1nk's URL patterns:

.. code-block:: python

    from quartet_tr4c3l1nk import urls as quartet_tr4c3l1nk_urls


    urlpatterns = [
        ...
        url(r'^', include(quartet_tr4c3l1nk_urls)),
        ...
    ]

Features
--------

* TODO

Running Tests
-------------

Does the code actually work?

::

    source <YOURVIRTUALENV>/bin/activate
    (myenv) $ pip install tox
    (myenv) $ tox

