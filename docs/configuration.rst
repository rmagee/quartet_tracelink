Steps Configuration
===================

Output Parsing
--------------
At the beginning of a standard EPCIS Output Rule, change the first step to:

    quartet_tracelink.steps.OutputParsingStep

This step will add filtered events into the context that are based on
derivative EPCPyYes objects that render tracelink proprietary EPCIS formats
that are required by the tracelink platform.  The tracelink platform does
not support EPCIS 1.2 or even standard EPCIS 1.1 unless special tracelink
tags are put into the EPCIS data.


Add Commissioning Data Step
---------------------------
As the second step, add the following:

quartet_tracelink.steps.AddCommissioningDataStep

This renders commissioning events with the tracelink special gtin field along
with the old EPCIS 1.1 format since tracelink does not support EPCIS 1.2.

Output Step
-----------
As the penultimate step, add the following:

quartet_tracelink.steps.TracelinkOutputStep

This step will use the same EPCPyYes objects to render the special tracelink
EPCIS data to the context for sending.
