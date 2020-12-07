# ApplicationCore-MicroDAQ-Tools

This packages provides tools related to the ApplicationCore-MicroDAQ package that add the DAQ modules to ApplciationCore.
Basically the package provides a PyQT5 based data inspector `MicroDAQViewer`.
Features of that viewer are e.g.:

* Plot scalar and array data for single events
* Table view of scalar and array data
* Timeline of scalar and array data (time range can be given a number of events or directly by specifying the time range)
* Search for events fullfilling specific trigger requirements

Also another PyQT5 based program called `UaClient` is included in the package. This is an OPC-UA based live viewer. The OPCUA client is based on freeopcua and requiers to install `opcua-client` via pip3.

If `root` support is enabled addition features are provided:

* `libApplicationCore-MicroDAQ-Tools.so`: Includes ROOT related tools. This library is used by the `MicroDAQViewer` when working on ROOT files
* `hdf5Converter`: C++ application that allows to convert HDF5 files to ROOT files, which reduces the disc usage significantly
* `plot`: Example showing how to use `uDAQ::DataHandler` clas provided in `libApplicationCore-MicroDAQ-Tools.so`

## ROOT file quick analysis

To view a property vs. entry use:

    tree->Draw("Entry$:temperature")
 
To use the time stamp information use:

    tree->Draw("timeInfo.timeStamp:temperature")

In the plot you can use `SetTimeDisplay` for the x-axis. 


## Merging ROOT files

In order to merge ROOT files use:

    hadd merged.root *.root
