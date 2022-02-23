# BOPTEST-BACnet-proxy
A BACnet proxy to the building simulations in the [BOPTEST](https://github.com/ibpsa/project1-boptest) framework. Uses [BACpypes](https://github.com/JoelBender/bacpypes) and Python.

## Overview
The BOPTEST (Building Optimization Performance Testing) framework is a project of the International Building Peformance Simulation Association (IBPSA), the US Department of Energy, several US National Labs, and other collaborators. BOPTEST was created to benchmark building control algorithms, and to make it easier to get started.
You don't need to know the in-depth details of building simulation in order to use BOPETST.

BOPTEST builds on [Modelica](https://en.wikipedia.org/wiki/Modelica) and the [Modelica Buildings Library](https://simulationresearch.lbl.gov/modelica/) to run high-fidelity physics based building simulations, along with some custom Modelica blocks that use the FMI standard to exchange data between the simulation and the outside world. 
BOPTEST packages all of the software up along with preconfigured building models into self-contained Docker images. The Docker images contain a REST endpoint built on Flask that can drive the simulation and exchange data between the caller and the simulation, including overriding some control signals and setpoints the simulation is using. 
The Docker image has everything necessary for the simulation - it includes realistic, granular weather and occupancy data, layout information about the zones and thermal properties of the building, and baseline controls for the building. 
You can literally make a call to the `/initialize` endpoint, and then call the `/advance` endpoint 120\*24\*365 times, each time telling the `/advance` endpoint to advance the state of the simulation by 30 seconds, you'll get at the end a simulated history of 1 years' worth of building performance, along with a set of key performance indicaors (KPIs) calculated for the building on how it did for energy usage/occupant comfort/etc, using the baseline control configuration in the system. 
Happily, it's pretty fast, so you can get a year's worth of simulated building data in only a few minutes/hours of wallclock time.

Of course, the point of BOPTEST is to be able to test different controllers and control algorithms on realistic building configurations, so you can override the control signals and setpoints of the baseline controllers at each call to the `/advance` end point to test different algorithms. 
The BOPTEST distribution includes several different preconfigured simulatable buildings, each one called a 'test case'. 

But, just because you can run the simulation faster than wallclock time doesn't mean you have to, and that's what we've been experimenting with. 
This repository has a simple server - the `BoptestBACnetProxy` - that drives a BOPTEST simulation at wallclock speeds. 
Every 5 seconds of realworld time, the `BoptestBACnetProxy` advances the BOPTEST simulation forward by 5 seconds. 
To interact with the simulation, the `BoptestBACnetProxy` reads the current state of the simulation out of BOPTEST and makes those values available as BACnet objects. 
The `BoptestBACnetProxy` can also be written to using BACnet, and any of the "input" points that are overwritten in the proxy and passed in to the BOPTEST simulation.
This way, users can interact with the building simulation through the BACnet client or controller of their choice and override setpoints and such, and see physically-correct results in the virtual sensor objects also through BACnet.

The end result is a fully digital building that can be created and interacted with as though it was a real building, using standard protocols.


## Getting Started
To run it, follow the install instructions
from https://github.com/ibpsa/project1-boptest and run it with testcase1,
```
TESTCASE=testcase1 docker compose up
```

Then, in another terminal, edit the `BACpypes.ini` file to match the IP address details of your site, and run 
```
python BopTestProxy.py testcase1.json
```
(remember that ObjectIdentifer property in BACnet must be unique across your entire BACnet installation, so you may need to change the 599 to something else, consult your local BACnet administrator)

Finally, on another machine, use the BACnet client of your choice to observe the state of the simulation throough BACnet and optionally overwrite some control point values to influence the simulation.
Remember that BACnet uses UDP and port 47808 ('BAC0' in hex) so you may need to adjust your firewall rules on both machines.

## Configuration
At the moment, we are creating JSON files to do the mapping between BACnet and BOPTEST, one for each test case, though they are very simple. In the future, we may drop the JSON files and get the mapping information right from BOPTEST using the `/inputs` and `/measurements` endpoints. 
The reason we do not currently do so is to be sure we have stable BACnet object instance IDs.

## Brick Models
We are working on creating a [Brick model](https://brickschema.org/) for each of the test cases.
The Brick models include the BACnet references necessary for Brick+BACnet-enabled software to interact with the BOPTEST simulation, through the proxy.

## License
The `BopTestProxy.py` is a slightly modified version of the OpenWeatherServer.py sample from the BACpypes package, which was written by Joel Bender and was made available under the MIT License. 

