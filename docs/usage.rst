=====
Usage
=====

To use quartet_tr4c3l1nk in a project, add it to your `INSTALLED_APPS`:

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
