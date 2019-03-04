=====
Usage
=====

To use quartet_tracelink in a project, add it to your `INSTALLED_APPS`:

.. code-block:: python

    INSTALLED_APPS = (
        ...
        'quartet_tracelink.apps.QuartetTr4c3l1nkConfig',
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
