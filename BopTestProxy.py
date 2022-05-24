# -*- coding: utf-8 -*-

"""
BOPTEST Proxy Server

This sample application uses BOPTEST framework to create a virtual building
and make it available over BACnet. To run it, follow the install instructions
from https://github.com/ibpsa/project1-boptest and run it with testcase1,
ala 
TESTCASE=testcase1 docker compose up

Then, in another terminal, run python BopTestProxy.py testcase1.json

Finally, on another machine, use the BACnet client of your choice to
observe the state of the simulation throough BACnet and optionally 
overwrite some control point values to influence the simulation


This code is based on the OpenWeatherServer.py sample and remains almost
identical to that sample.
"""

import os
import requests
import time
import json
import rdflib

from bacpypes.debugging import bacpypes_debugging, ModuleLogger
from bacpypes.consolelogging import ConfigArgumentParser

from bacpypes.core import run, deferred
from bacpypes.task import recurring_function

from bacpypes.basetypes import DateTime
from bacpypes.primitivedata import Real
from bacpypes.object import AnalogValueObject, DateTimeValueObject

from bacpypes.app import BIPSimpleApplication
from bacpypes.service.device import DeviceCommunicationControlServices
from bacpypes.service.object import ReadWritePropertyMultipleServices
from bacpypes.local.device import LocalDeviceObject
from bacpypes.local.object import AnalogValueCmdObject, Commandable, AnalogOutputCmdObject
from bacpypes.object import register_object_type, AnalogInputObject

# some debugging
_debug = 0
_log = ModuleLogger(globals())

# application interval is refresh time in seconds 
APPINTERVAL = 5 * 1000 # 5 seconds

# dictionary of names to objects
objects = {}
inputs = {}
nextState = None
g = None

klassMapping = {'analog-value': AnalogValueCmdObject, 'analog-input': AnalogInputObject, 'analog-output': AnalogOutputCmdObject}
unitMapping = {'http://qudt.org/vocab/unit/K': "degreesKelvin", 'http://qudt.org/vocab/unit/PPM': "partsPerMillion"}

baseurl = "http://localhost:5000"
boptest_measurements = None
boptest_inputs = None

# TODO - what should some of the BOPTEST objects be - maybe
# AnalogInputs or BinaryInputs?
# Not currently using this class
# TODO - why does BACpyes have a builtin AnalogValueCmdObject but not a builtin AnalogInputCmdObject?
@bacpypes_debugging
@register_object_type(vendor_id=999)
class AnalogInputCmdObject(Commandable(Real), AnalogInputObject):
    def _set_value(self, value):
        if _debug:
            AnalogInputCmdObject._debug("_set_value %r", value)

        # numeric values are easy to set
        self.presentValue = value

# We are using this class
# TODO - why are we using this class instead of just AnalogValueCmdObject?
# This was how OpenWeatherServer.py did it - was it just so it could log the change?
@bacpypes_debugging
@register_object_type(vendor_id=999)
class LocalAnalogValueObject(AnalogValueCmdObject):
    def _set_value(self, value):
        if _debug:
            LocalAnalogValueObject._debug("_set_value %r", value)

        # numeric values are easy to set
        self.presentValue = value



# TODO: Rather than a JSON file, look at the BOPTEST /inputs and /measurements
# endpoints to create BACnet objects for the running testcase. But, we need an instance number
# and want some control over that, because we want to use that number in the Brick model too
# TODO: Don't create all of these as the same BACnet object type, some should be
# AIs or BIs, or maybe AO/BOs
# TODO: BOPTEST has _activate input points that pair with other settings, but 
# this proxy could combine those into single BACnet point that if written to 
# with a higher priority, would override the default BOPTEST setting?

@bacpypes_debugging
def create_objects(app, configfile):
    """Create the objects that hold the result values."""
    if _debug:
        create_objects._debug("create_objects %r", app)
    global objects, inputs, g

    g= rdflib.Graph()
    g.parse(configfile)
    points = g.query("select ?point ?name ?bacnetRef ?unit where {?point ref:hasExternalReference ?bo . ?bo bacnet:object-identifier ?bacnetRef . ?bo bacnet:object-name ?name OPTIONAL {?point brick:hasUnit ?unit} }")
    for point in points:
        rdfBacnetName = point[1]
        rdfBacnetRef = point[2]
        rdfBacnetUnit = point[3]
        if _debug:
            create_objects._debug("    - name: %r", point[1])
        klassName, instanceNum = rdfBacnetRef.split(",", 2)
        print(klassName + " " + instanceNum)
        klass = klassMapping[klassName]
        instanceNum = int(instanceNum)
        name = str(rdfBacnetName)
        units = None
        if rdfBacnetUnit:
            units = unitMapping[str(rdfBacnetUnit)]
        
        if klassName == 'analog-input':
            obj = klass(objectName = name, objectIdentifier=(klass.objectType, instanceNum), presentValue=0.0)
        else:
            obj = klass(objectName = name, objectIdentifier=(klass.objectType, instanceNum), relinquishDefault = 0.0)
        if _debug:
            create_objects._debug("    - obj: %r", obj)

        if units is not None:
            obj.units = units

        # add it to the application
        app.add_object(obj)
        # keep track of the object by name
        objects[name] = obj
        if name in boptest_inputs:
            inputs[name] = obj


@recurring_function(APPINTERVAL)
@bacpypes_debugging
def update_boptest_data():
    """Read the current simulation data from the API and set the object values."""
    if _debug:
        update_boptest_data._debug("update_boptest_data")
    global objects, inputs

    # ask the web service
    # We get results direct from /advance now but you could ask the simulation for historic data
    #response = requests.put(
    #    "http://localhost:5000/results", data={'point_name':'TRooAir_y', 'start_time': timestep * 30, 'final_time': (timestep+1)*30}
    #)

    # TODO: Is there a way to get the current priorty value a point is currently written at?
    #       that way, we don't have to pass in the overwriteable signals if they match the BOPTest
    #       presets. This is slightly complicated because BOPTest is "sticky" - once you overwrite the
    #       the built-in it remembers that setting for future calls to /advance. Work around that here by just
    #       always overwriting the inputs from whatever is in the BACnet registers
    # TODO: should some of these signals combine into one BACnet object, e.g. in testcase1, if someone overwrites
    #       oveAct_u, should the proxy automatically turn on oveAct_activate, without exposing oveAct_activate as
    #       a BACnet point? We'd have to pair them somehow...
    signals = {}
    for k,v in inputs.items():
        signals[k] = v._highest_priority_value()

    response = requests.post(
    #    "http://localhost:5000/advance", data={"oveAct_u": next_oveAct_u, "oveAct_activate": next_oveAct_activate}
        "http://localhost:5000/advance", data=signals
    )
    if response.status_code != 200:
        print("Error response: %r" % (response.status_code,))
        return

    # turn the response string into a JSON object
    json_response = response.json()

    # set the object values
    # We advance the simulation by 5 seconds at each call to the loop, but we don't update the external world
    # with those results until the NEXT call to this function. 
    #
    # TODO: rather than using recurring_function, we should schedule ourselves to be called again at (5secs-elapsed_function_time)
    # because if say the call to /advance takes 3 seconds, we want to get called again in 2 seconds, not in 5 seconds. 
    global nextState
    if nextState:
        for k, v in nextState.items():
            if _debug:
                update_boptest_data._debug("    - k, v: %r, %r", k, v)
                
            if k in objects:
                #objects[k]._set_value(v)
                objects[k].presentValue = v

    nextState = json_response

# BAC0 uses the ReadPropertyMultiple service so make that available
@bacpypes_debugging 
class ReadPropertyMultipleApplication(
   BIPSimpleApplication,
   ReadWritePropertyMultipleServices,
   DeviceCommunicationControlServices,
   ):
   pass

@bacpypes_debugging
def main():
    global vendor_id, g

    parser = ConfigArgumentParser(description=__doc__)

    parser.add_argument('brick_model', type=str, help='Brick model that defines the site, a ttl file')
    # parse the command line arguments
    args = parser.parse_args()
    
    if _debug:
        _log.debug("initialization")
    if _debug:
        _log.debug("    - args: %r", args)

    # TODO: Take the URL as a commandline argument
    # TODO: check the results to make sure we acutally get an OK!
    # TODO: Take a commandline option for warmup period - e.g. let the simulation settle in respoonse to
    # outside air temps etc before starting
    global nextState
    res = requests.put('{0}/initialize'.format(baseurl), data={'start_time':0, 'warmup_period':0} ).json()
    nextState = res

    global boptest_measurements, boptest_inputs
    boptest_measurements = requests.get(baseurl + "/measurements").json()
    boptest_inputs = requests.get(baseurl+"/inputs").json()

    # We advance the simulation by 5 seconds at each call to /advance, and APPINTERVAL is also 5 seconds, so the simulationo
    # moves in sync with wallclock time. To see things happen faster, set this time greater than 5 seconds
    res = requests.put('{0}/step'.format(baseurl), data={'step':5})

    # make a device object
    this_device = LocalDeviceObject(ini=args.ini)
    if _debug:
        _log.debug("    - this_device: %r", this_device)

    # make a sample application
    this_application = ReadPropertyMultipleApplication(this_device, args.ini.address)

    # create the objects and add them to the application
    create_objects(this_application, args.brick_model)
    
    # run this update when the stack is ready
    deferred(update_boptest_data)

    if _debug:
        _log.debug("running")

    run()

    if _debug:
        _log.debug("fini")


if __name__ == "__main__":
    main()
