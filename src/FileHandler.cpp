// SPDX-FileCopyrightText: Helmholtz-Zentrum Dresden-Rossendorf, FWKE, ChimeraTK Project <chimeratk-support@desy.de>
// SPDX-License-Identifier: LGPL-3.0-or-later
/*
 * FileHandler.cpp
 *
 *  Created on: Oct 16, 2017
 *      Author: Klaus Zenker (HZDR)
 */

#include "FileHandler.h"

#include "TString.h"

#include <iostream>

using namespace hdf5converter;

H5FileHandler::H5FileHandler(const std::string& fileName, llrfData_t* data)
: _file(fileName.c_str(), H5F_ACC_RDONLY), _data(data) {}

long H5FileHandler::GetNEvents() {
  return _file.getNumObjs();
}

void H5FileHandler::readVector(const H5::DataSet& d, TArrayF& vd) {
  //\ToDo: Include try catch and DataSet creation here!
  auto space = d.getSpace();
  hsize_t dims_out[1];
  space.getSimpleExtentDims(dims_out, NULL);
  vd.Set(dims_out[0]);
  H5::DataSpace mem(1, dims_out);
  d.read(&vd[0], H5::PredType::NATIVE_FLOAT, mem, space);
}

void H5FileHandler::readGroup(const H5::Group& grp) {
  auto nMax = grp.getNumObjs();
  for(size_t ch = 0; ch < nMax; ch++) {
    if(grp.getObjTypeByIdx(ch) == H5G_obj_t::H5G_GROUP) {
      readGroup(grp.openGroup(grp.getObjnameByIdx(ch)));
    }
    else {
      H5::DataSet dataSet = grp.openDataSet(grp.getObjnameByIdx(ch));
      TArrayF vdata;
      readVector(dataSet, vdata);
      auto name = dataSet.getObjName();
      name.erase(0, currentMainGroup->getObjName().length() + 1);
      if(vdata.fN == 1)
        _data->paramter[name] = vdata.At(0);
      else
        _data->trace[name] = vdata;
    }
  }
}

void H5FileHandler::readData(const unsigned long& event) {
  dateparser parser("%Y-%m-%d %H:%M:%s");
  if(!parser(_file.getObjnameByIdx(event))) {
    throw std::runtime_error("Could not parse the time information.");
  }
  H5G_obj_t type = _file.getObjTypeByIdx(event);
  if(type != H5G_GROUP) {
    std::stringstream ss;
    ss << "Found unexpected object, which is not of type H5::Group. Name is: " << _file.getObjnameByIdx(event);
    throw std::runtime_error(ss.str());
  }
  currentMainGroup = std::make_shared<H5::Group>(_file.openGroup(_file.getObjnameByIdx(event)));
  timeInfo_t info;
  info.timeStamp = parser.time;
  info.msec = parser.msec;
  info.strTimeStamp = _file.getObjnameByIdx(event).c_str();
  info.datime = TDatime(info.timeStamp);
  _data->timeInfo = info;

  readGroup(*currentMainGroup.get());
}

RootFileHandler::RootFileHandler(const std::string& fileName, const std::string& treeName, const Int_t& compression)
: _file(fileName.c_str(), "RECREATE", "", compression),
  _tree(new TTree(treeName.c_str(), "Data converted hdf5 files")) {}

RootFileHandler::~RootFileHandler() {
  if(_tree != nullptr && _tree->GetEntries() > 0) _tree->Write();
  delete _tree;
  _file.Close();
}

const char* RootFileHandler::convertPath(std::string str) {
  replace(str.begin(), str.end(), '/', '.');
  return str.c_str();
}

void RootFileHandler::addEvent() {
  if(_tree->GetNbranches() == 0) {
    for(auto& p : _data.paramter) {
      _tree->Branch(convertPath(p.first), &p.second);
    }
    for(auto it = _data.trace.begin(); it != _data.trace.end(); it++) {
      _tree->Branch(convertPath(it->first), &it->second);
    }
    _tree->Branch("timeInfo", &_data.timeInfo, 32000, 0);
  }
  _tree->Fill();
}

void RootFileHandler::handleFile(const std::string& h5file) {
  H5FileHandler handler(h5file, &_data);
  auto nEvents = handler.GetNEvents();
  for(int i = 0; i < nEvents; i++) {
    try {
      handler.readData(i);
      addEvent();
    }
    catch(std::runtime_error& e) {
      std::cerr << e.what() << std::endl;
    }
    catch(...) {
      std::cerr << "Error..." << std::endl;
    }
  }
}
