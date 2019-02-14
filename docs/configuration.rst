Creating a Tracelink Output Filer Rule
======================================

Output filter rules look for conditions in data and, if those conditions exist,
will perform additional operations against the inbound data. This example
processes an inbound shipping event by looking for shipping event data and then
taking all of the children of the shipped EPCs and creating a message with
the commissioning and aggregation events for all of the children included.

As a quick note, Tracelink is an inflexible platfrom and does not support EPCIS
in it's current form...and this must be worked around.  This QU4RTET exension package
contains some rules and steps that format messages
into the particular "EPCIS" format that Tracelink requires.

Managment Command/Utility
-------------------------

If you're on the TL;DR path, there is a management command that will set up
an example output filter rule for you.  At the command line execute

.. code-block:: text

    python mangage.py setup_tracelink

This will create an example output filter rule and an example number pool as
well. It will be up to you to modify the endpoints, authentication and
any template parameters and templates accordingly.

Create an EPCIS Output Criteria
===============================
Create a new *Output/EPCIS Output Criteria* and add values you know will
be in a shipment message for a specific business scenario.
For example, a specific business step, event type, event action and SGLN.
Save this and name it accordingly.  This is what the first step in the
following rule configuration will use to filter out certain events for
processing.

The Output Filter Rule
======================
Create a new rule.

Add the following steps:

Output Parsing Step
-------------------
At the beginning of a standard EPCIS Output Rule, change the first step to:

.. code-block:: text

    quartet_tracelink.steps.OutputParsingStep

This step will add filtered events into the context that are based on
derivative EPCPyYes objects that render tracelink proprietary EPCIS formats
that are required by the tracelink platform.  The tracelink platform does
not support EPCIS 1.2 or even standard EPCIS 1.1 unless special tracelink
tags are put into the EPCIS data.

The following steps are in order from 1 to 5 and you can give them
name/descriptions according to your preference.  The order should be sequential
from 1 to 5 for each.

Add Commissioning Data Step
---------------------------
As the second step, add the following:

.. code-block:: text

    quartet_tracelink.steps.AddCommissioningDataStep

This renders commissioning events with the tracelink special gtin field along
with the old EPCIS 1.1 format since tracelink does not support EPCIS 1.2.

EPCIS Output Criteria Step Parameter
####################################
Add a step parameter to this step called `EPCIS Output Criteria` and give it
the name of the *EPCIS Output Criteria* we defined above.

Add Aggregation Step
--------------------
If there is aggregation in your business scenario, add this step as the third
step.  Add the following Class path to the configuration.

.. code-block:: text

    quartet_output.steps.UnpackHierarchyStep

Render Tracelink XML Step
-------------------------
The fourth step should be the step that takes the data added to the channel
by the last two steps and renders it into the special non-compliant EPCIS
that Tracelink requires.

.. code-block:: text

    quartet_tracelink.steps.TracelinkOutputStep

Append Filtered Events Step Parameter
#####################################
For this step, add a new step parameter named `Append Filtered Events`.  Set
this to the value `False`.


Queue Outbound Messge Step
--------------------------
As the fifth in order and final step, add the following:

.. code-block:: text

    quartet_output.steps.CreateOutputTaskStep

This step will use the same EPCPyYes objects to render the special tracelink
EPCIS data to the context for sending.

Output Rule Step Parameter
##########################
Add a step param to the this step with the name `Output Rule` and the value
`Transport Rule`.  There should already be a default *Transport Rule* defined
in your system.
