// SPDX-FileCopyrightText: Helmholtz-Zentrum Dresden-Rossendorf, FWKE, ChimeraTK Project <chimeratk-support@desy.de>
// SPDX-License-Identifier: LGPL-3.0-or-later
/*
 * DataHandler.cpp
 *
 *  Created on: May 28, 2018
 *      Author: Klaus Zenker (HZDR)
 */

#include "DataHandler.h"

#include "TFile.h"
#include "TLeafObject.h"
#include "TMath.h"
#include "TTree.h"
#include "TTreeReader.h"

#include <boost/filesystem.hpp>
#include <boost/fusion/algorithm.hpp>
#include <boost/fusion/include/at_key.hpp>
#include <boost/log/core.hpp>
#include <boost/log/expressions.hpp>

#include <algorithm>
#include <numeric>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

using namespace std;

namespace uDAQ {
  DataHandler::DataHandler(const std::string& folder, const bool& sort, const std::vector<std::string>& matchString,
      const size_t& maxFiles, const std::string& treeName)
  : m_decimation(1), m_treeName(treeName), m_lastTrigger(nullptr), m_localEntry(0), m_newFile(false), m_tinfo(nullptr),
    m_timeStamp(nullptr) {
    boost::filesystem::path p(folder);
    if(!boost::filesystem::is_directory(p)) throw std::runtime_error("The given folder string is not a directory");
    BOOST_LOG_TRIVIAL(info) << "\t Using matching strings: " << endl;
    for(auto st = matchString.begin(); st != matchString.end(); st++) {
      BOOST_LOG_TRIVIAL(info) << "\t" << *st << endl;
    }
    if(sort) {
      std::vector<std::pair<Long_t, std::string>> files;
      boost::filesystem::directory_iterator start(p);
      boost::filesystem::directory_iterator end;
      for(; start != end; start++) {
        if(start->path().leaf().extension().string().compare(".root") == 0) {
          std::string tmp(start->path().string().c_str());
          if(m_treeName.empty()) {
            m_treeName = extractTreeName(tmp.c_str());
          }
          if(checkMatch(tmp, matchString))
            files.push_back(std::make_pair(getTimeStamp(tmp.c_str(), m_treeName).first, tmp));
        }
      }
      if(files.size() < 1) {
        BOOST_LOG_TRIVIAL(error) << "There are no files in the Chain. Maybe the match string did not match any file."
                                 << endl;
        throw std::runtime_error("No files in the chain.");
      }
      std::sort(files.begin(), files.end());
      auto it = files.begin();
      m_chain = new TChain(m_treeName.c_str());
      if(maxFiles > 0 && maxFiles < files.size()) it = files.end() - maxFiles;
      while(it != files.end()) {
        BOOST_LOG_TRIVIAL(info) << "\t File -> " << it->second << "(timestamp: " << it->first << ")" << endl;
        m_chain->AddFile(it->second.c_str());
        it++;
      }
    }
    else {
      std::vector<std::string> files;
      boost::filesystem::directory_iterator start(p);
      boost::filesystem::directory_iterator end;
      for(; start != end; start++) {
        if(start->path().leaf().extension().string().compare(".root") == 0) {
          std::string tmp(start->path().string().c_str());
          if(checkMatch(tmp, matchString)) files.push_back(tmp);
        }
      }
      if(files.size() < 1) {
        BOOST_LOG_TRIVIAL(error) << "There are no files in the Chain. Maybe the match string did not match any file."
                                 << endl;
        throw std::runtime_error("No files in the chain.");
      }
      std::sort(files.begin(), files.end());
      auto it = files.begin();
      if(treeName.empty()) m_treeName = extractTreeName(it->c_str());
      m_chain = new TChain(m_treeName.c_str());
      if(maxFiles > 0 && maxFiles < files.size()) it = files.end() - maxFiles;
      while(it != files.end()) {
        BOOST_LOG_TRIVIAL(info) << "\t File -> " << *it << endl;
        m_chain->AddFile(it->c_str());
        it++;
      }
    }
    auto branches = m_chain->GetListOfBranches();
    BOOST_LOG_TRIVIAL(info) << "Chain name: " << m_treeName << endl;
    BOOST_LOG_TRIVIAL(info) << "Chain contains: " << m_chain->GetNbranches() << " branches." << endl;
    for(int i = 0; i < m_chain->GetNbranches(); i++) {
      m_branches.push_back(branches->At(i)->GetName());
      BOOST_LOG_TRIVIAL(debug) << "Branch name: " << branches->At(i)->GetName() << endl;
    }

    BOOST_LOG_TRIVIAL(debug) << "Reading number of trees..." << endl;
    m_nTrees = m_chain->GetNtrees();
    BOOST_LOG_TRIVIAL(info) << "Number of trees is: " << m_nTrees << endl;
    BOOST_LOG_TRIVIAL(debug) << "Reading number of events..." << endl;
    m_nEntries = m_chain->GetEntries();
    BOOST_LOG_TRIVIAL(info) << "Number of events is: " << m_nEntries << endl;
    //  m_chain->SetBranchStatus("*", 0);
    //  m_chain->SetBranchStatus("timeInfo", 1);
    m_chain->LoadTree(0);
    TObject* br = m_chain->GetListOfBranches()->FindObject("timeStamp");
    if(br) {
      m_timeStamp = new TTimeStamp();
      m_chain->SetBranchAddress("timeStamp", &m_timeStamp, &m_timeStampBranch);
      if(!m_timeStampBranch) throw std::runtime_error("Failed to read timeInfo branch");
    }
    else {
      m_tinfo = new hdf5converter::timeInfo_t();
      m_chain->SetBranchAddress("timeInfo", &m_tinfo, &m_tBranch);
      if(!m_tBranch) throw std::runtime_error("Failed to read timeInfo branch");
    }
  }

  bool DataHandler::checkMatch(const std::string& file, const std::vector<std::string>& matchStrings) {
    if(matchStrings.size() == 0) return true;
    for(auto st = matchStrings.begin(); st != matchStrings.end(); st++) {
      if(file.find(*st) != std::string::npos) {
        return true;
      }
    }
    return false;
  }

  DataHandler::~DataHandler() {
    BOOST_LOG_TRIVIAL(debug) << "Data handler destructor called." << endl;
    delete m_chain;
  }

  size_t DataHandler::getTypeFromTree(const char* branchName) {
    /*
     * Check Trace:
     * - auto b = m_chain->GetBranch("aLLRF.1-3GHz");
     * - std::string(b->GetClassName()).empty() -> true if not a trace
     * In case it is not a trace check data type:
     * - auto l = chain->GetListOfLeaves()
     * - TLeafObject* lo = (TLeafObject*)l->FindObject("aLLRF.1-3GHz")
     * - lo->GetTypeName()
     */
    auto b = m_chain->GetBranch(branchName);
    if(!b) throw std::runtime_error(std::string("Failed to find branch: ") + branchName);

    if(!std::string(b->GetClassName()).empty()) {
      if(std::string(b->GetClassName()).compare("TArrayF") == 0) return 1;
      if(std::string(b->GetClassName()).compare("TArrayD") == 0) return 2;
      if(std::string(b->GetClassName()).compare("TArrayI") == 0) return 3;
      if(std::string(b->GetClassName()).compare("TArrayL") == 0) return 4;
      if(std::string(b->GetClassName()).compare("TArrayS") == 0) return 5;
      if(std::string(b->GetClassName()).compare("TArrayC") == 0) return 6;
      throw std::runtime_error(std::string("Unknown datatype for array branch: ") + branchName);
    }
    auto l = m_chain->GetListOfLeaves();
    TLeafObject* lo = (TLeafObject*)l->FindObject(branchName);
    std::string typeName = lo->GetTypeName();
    if(typeName.compare("Float_t") == 0) return 1;
    if(typeName.compare("Double_t") == 0) return 2;
    if((typeName.compare("Int_t") == 0) || (typeName.compare("UInt_t") == 0)) return 3;
    if((typeName.compare("Long64_t") == 0) || (typeName.compare("ULong64_t") == 0)) return 4;
    if((typeName.compare("Short_t") == 0) || (typeName.compare("UShort_t") == 0) || (typeName.compare("Char_t") == 0) ||
        (typeName.compare("UChar_t") == 0))
      return 5;
    if(typeName.compare("Bool_t") == 0) return 6;
    throw std::runtime_error(std::string("Unknown datatype for scalar branch: ") + branchName);
  }

  bool DataHandler::prepareTree(const Long_t& event) {
    // \remark Logging messages are commented out to speed up the function call
    //  BOOST_LOG_TRIVIAL(debug) << "Event: " << event << " (total: " << m_nEntries << ")." << endl;
    TUUID id;
    auto tmp = m_chain->GetCurrentFile();
    if(tmp) {
      id = tmp->GetUUID();
    }
    m_localEntry = m_chain->LoadTree(event);
    if(m_localEntry < 0) {
      // error loading file - happens e.g. if the file was just opened
      return false;
    }
    if(tmp) {
      if(id.Compare(m_chain->GetCurrentFile()->GetUUID()) != 0) {
        m_newFile = true;
        //      BOOST_LOG_TRIVIAL(debug) << "New file detected." << endl;
      }
    }
    else {
      m_newFile = true;
      //    BOOST_LOG_TRIVIAL(debug) << "First file:"  << m_chain->GetCurrentFile()->GetName() << endl;
    }
    if(m_newFile) {
      if(m_tinfo == nullptr) {
        m_chain->SetBranchAddress("timeStamp", &m_timeStamp, &m_timeStampBranch);
      }
      else {
        m_chain->SetBranchAddress("timeInfo", &m_tinfo, &m_tBranch);
      }
    }

    return true;
    //  BOOST_LOG_TRIVIAL(debug) << "Local: " << m_localEntry << endl;
  }

  namespace detail {

    struct ClearData {
      ClearData(DataHandler* caller) : _caller(caller){};
      DataHandler* _caller;
      template<typename PAIR>
      void operator()(PAIR&) const {
        typedef typename PAIR::first_type UserType;
        auto& dataMap = boost::fusion::at_key<UserType>(_caller->data.table);
        dataMap.clear();
      }
    };

    struct UpdateData {
      /**
       * Read data from the file and copy the data to the timeLines.
       * \param caller The DataHandler to use for reading
       * \param nMax The number of events to be collected into the timeLine (defines the length of the timeLien).
       * If eventID < 0 this parameter is ignored. In that case the length of the timeLine is defined by the array
       * length read here. \param event The number of the event that is currently filled. Should start with 0 and end
       * with nMax-1 \param eventID The event number in the TTree/TChain. It is used for the x vector of the Trace. If
       * eventID<0 it is assumed that only a single event is read. In that case the timeLine is actually the array read
       * for this event. The x vector is filled with the array index.
       */
      UpdateData(DataHandler* caller, size_t nMax, size_t event, int eventID = -1)
      : _caller(caller), _nMax(nMax), _event(event), _eventID(eventID) {}
      DataHandler* _caller;
      size_t _nMax;  //<<< Expected length of the timeline to be filled here
      size_t _event; //<<< The event that is currently filled
      int _eventID;  //<<< The ID of the event. If -1 a single event is read!
      template<typename PAIR>
      void operator()(PAIR&) const {
        typedef typename PAIR::first_type UserType;
        auto& dataMap = boost::fusion::at_key<UserType>(_caller->data.table);
        //    BOOST_LOG_TRIVIAL(debug) << "Size of the map: " << dataMap.size() << endl;
        for(auto it = dataMap.begin(); it != dataMap.end(); it++) {
          if(_caller->m_newFile) {
            BOOST_LOG_TRIVIAL(debug) << "Switched to new file: " << _caller->m_chain->GetCurrentFile()->GetName()
                                     << endl;
            if(it->second.isTrace) {
              _caller->m_chain->SetBranchAddress(it->first.c_str(), &it->second.parr, &it->second.branch);
            }
            else {
              _caller->m_chain->SetBranchAddress(it->first.c_str(), &(it->second.arr[0]), &it->second.branch);
            }
          }

          // Read the data
          if(it->second.branch->GetEntry(_caller->m_localEntry) <= 0) {
            BOOST_LOG_TRIVIAL(error) << "Failed reading data for event: " << _event
                                     << " at local event: " << _caller->m_localEntry << ")." << endl;
            continue;
          }
          // Create Trace if not yet done
          if(!_caller->timeLines.count(it->second.branch->GetName())) {
            if(_eventID < 0) {
              _caller->timeLines[it->second.branch->GetName()] = Trace(it->second.arr.GetSize());
            }
            else {
              _caller->timeLines[it->second.branch->GetName()] = Trace(_nMax);
            }
          }
          auto currentTrace = &_caller->timeLines[it->second.branch->GetName()];

          // Put data into the time lines and do the data conversion
          if(_eventID < 0) {
            //        BOOST_LOG_TRIVIAL(debug) << "Filling data for variable " << it->second.branch->GetName() << ",
            //        which has size: " << it->second.arr.GetSize() << endl;
            for(Int_t i = 0; i < it->second.arr.GetSize(); i++) {
              currentTrace->y[i] = it->second.arr[i];
              currentTrace->x[i] = i;
            }
          }
          else {
            if(_caller->m_arrayPosition == -1) {
              currentTrace->y.at(_event) = it->second.arr.GetSum() / it->second.arr.GetSize();
            }
            else if(_caller->m_arrayPosition == -2) {
              currentTrace->y.at(_event) = TMath::MaxElement(it->second.arr.GetSize(), &it->second.arr[0]);
            }
            else if(_caller->m_arrayPosition == -3) {
              currentTrace->y.at(_event) = TMath::MinElement(it->second.arr.GetSize(), &it->second.arr[0]);
            }
            else if(_caller->m_arrayPosition >= 0) {
              if(!it->second.isTrace) {
                currentTrace->y.at(_event) = it->second.arr.At(0);
              }
              else if(it->second.arr.GetSize() - 1 >= _caller->m_arrayPosition) {
                currentTrace->y.at(_event) = it->second.arr.At(_caller->m_arrayPosition);
              }
              else {
                // do not throw here since it can not be catched so far and it might happen regularly
                //            throw std::runtime_error(std::string("Requested array position is too large. Maximum is
                //            :")+std::to_string(it->second.arr.GetSize()-1));
                BOOST_LOG_TRIVIAL(warning) << "Requested array position is too large. Will use maximum instead: "
                                           << it->second.arr.GetSize() - 1 << endl;
                currentTrace->y.at(_event) = it->second.arr.At(it->second.arr.GetSize() - 1);
              }
            }
            else {
              // throwing here is ok since it should not happen -> this is guaranteed by the API usage of the python program
              throw std::runtime_error("Wrong array index using for update. Should be > -4.");
            }
            if(_caller->m_timeAxis == TimeAxis::TRUE ||
                (_caller->m_timeAxis == TimeAxis::AUTO && !it->second.isTrace)) {
              if(_caller->m_tinfo == nullptr) {
                currentTrace->x.at(_event) = _caller->m_timeStamp->GetSec() + _caller->m_timeStamp->GetNanoSec() / 1e9;
              }
              else {
                currentTrace->x.at(_event) = _caller->m_tinfo->timeStamp + _caller->m_tinfo->msec * 1. / 1000;
              }
            }
            else {
              // do not fill the event number but the event ID. E.g. when plotting event 400 to 500 the first event id
              // is 400 and the first event is 0
              currentTrace->x.at(_event) = _eventID;
            }
          }
        }
      }
    };
  } // namespace detail

  void DataHandler::prepareReading(const std::set<std::string>& processVariables) {
    BOOST_LOG_TRIVIAL(debug) << "Enter activation." << endl;
    //  auto& branchList = boost::fusion::at_key<TArrayF>(branchList.table);
    boost::fusion::for_each(data.table, detail::ClearData(this));
    BOOST_LOG_TRIVIAL(debug) << "Going to activate " << processVariables.size() << " branches." << endl;
    for(auto branchName = processVariables.begin(), end = processVariables.end(); branchName != end; branchName++) {
      // test variable type
      auto type = getTypeFromTree(branchName->c_str());
      if(type == 1) {
        setupBranch<TArrayF>(*branchName);
      }
      else if(type == 2) {
        setupBranch<TArrayD>(*branchName);
      }
      else if(type == 3) {
        setupBranch<TArrayI>(*branchName);
      }
      else if(type == 4) {
        setupBranch<TArrayL>(*branchName);
      }
      else if(type == 5) {
        setupBranch<TArrayS>(*branchName);
      }
      else if(type == 6) {
        setupBranch<TArrayC>(*branchName);
      }
    }
    m_nActiveBranches = processVariables.size();
    BOOST_LOG_TRIVIAL(debug) << "Activation done." << endl;
  }

  void DataHandler::readData(const Long_t& event) {
    //  BOOST_LOG_TRIVIAL(debug) << "Reading event data for event: " << event  << endl;
    prepareTree(event);
    boost::fusion::for_each(data.table, detail::UpdateData(this, 1, 0));
    m_newFile = false;
  }

  struct dataHelper {
    TBranch* b;
    std::vector<double>* x;
    std::vector<double>* y;
    TArrayF* a;
  };

  void DataHandler::collectData() {
    BOOST_LOG_TRIVIAL(debug) << "Prepare structure..." << endl;
    timeLines.clear();
    size_t nMax = TMath::Ceil(1. * (m_end - m_start) / (1. * m_decimation));
    m_newFile = true;
    BOOST_LOG_TRIVIAL(debug) << "Preparation is done." << endl;
    BOOST_LOG_TRIVIAL(debug) << "Event range: " << m_start << " - " << m_end << endl;
    BOOST_LOG_TRIVIAL(debug) << "Decimation: : " << m_decimation << endl;
    std::vector<Trace>::iterator itFill;
    size_t filledEvents = 0;
    size_t skippedEvents = 0;
    // event loop
    for(auto i = m_start; i < m_end; i += m_decimation) {
      if(!prepareTree(i)) {
        skippedEvents += 1;
        continue;
      }
      if(!m_timeAxis == TimeAxis::FALSE) readTimeStamp();
      boost::fusion::for_each(data.table, detail::UpdateData(this, nMax, filledEvents, i));
      filledEvents++;
      m_percentage = 100. * (filledEvents) / nMax;
      if(m_interrupt) break;
      m_newFile = false;
    }
    // resize the traces in case there was an interrupt
    if(m_interrupt) {
      for(auto it = timeLines.begin(); it != timeLines.end(); it++) {
        it->second.x.resize(filledEvents);
        it->second.y.resize(filledEvents);
      }
    }
    if(skippedEvents > 0) BOOST_LOG_TRIVIAL(error) << "Skipped " << skippedEvents << " due to read errors." << endl;
    BOOST_LOG_TRIVIAL(debug) << "Collected data of " << filledEvents << " events." << endl;
    m_done = true;
  }

  void DataHandler::getTimeLine(
      const Long_t startEvent, Long_t endEvent, const size_t& decimation, const int& arrayPosition, TimeAxis timeAxis) {
    m_end = endEvent;
    if(m_end == -1) {
      m_end = m_nEntries;
    }
    m_start = startEvent;
    m_arrayPosition = arrayPosition;
    m_timeAxis = timeAxis;
    m_decimation = decimation;
    reset();
    m_worker = make_unique<std::thread>(&DataHandler::collectData, this);
  }

  TGraph* DataHandler::plotTrace(std::string processVariable, const Long_t& event) {
    std::set<std::string> l;
    l.insert(processVariable);
    prepareReading(l);
    readData(event);

    BOOST_LOG_TRIVIAL(info) << "Name: " << processVariable << " Size: " << timeLines[processVariable].x.size() << endl;
    TGraph* g = new TGraph(timeLines[processVariable].x.size());
    for(size_t i = 0; i < timeLines[processVariable].x.size(); i++) {
      g->SetPoint(i, i, timeLines[processVariable].y[i]);
    }
    return g;
  }

  TMultiGraph* DataHandler::plotTraces(const std::set<std::string>& processVariables, const Long_t& event) {
    prepareReading(processVariables);
    readData(event);
    TMultiGraph* mg = new TMultiGraph();
    TGraph* g;
    for(auto it = processVariables.begin(); it != processVariables.end(); it++) {
      g = new TGraph(timeLines[*it].x.size());
      for(size_t i = 0; i < timeLines[*it].x.size(); i++) {
        g->SetPoint(i, i, timeLines[*it].y[i]);
      }
      g->SetTitle(it->c_str());
      mg->Add(g);
    }
    return mg;
  }

  Long64_t DataHandler::getNextEvent(Long64_t last, bool increase) {
    if(increase) {
      if((last + 1) == m_nEntries)
        return -1;
      else
        return last + 1;
    }
    else {
      return last - 1;
    }
  }

  void DataHandler::getTriggerDecision() {
    BOOST_LOG_TRIVIAL(debug) << "Prepare trigger search..." << endl;
    std::set<std::string> s;
    std::string processVariable = m_trigger->processVariable;
    s.insert(processVariable);
    replace(processVariable.begin(), processVariable.end(), '/', '.');
    prepareReading(s);
    if(m_lastTrigger != nullptr && *m_trigger.get() == *m_lastTrigger.get()) {
      BOOST_LOG_TRIVIAL(info) << "Trigger did not change. No search necessary." << endl;
      m_done = true;
      return;
    }
    BOOST_LOG_TRIVIAL(debug) << "Trigger threshold is: " << m_trigger->threshold << endl;

    m_trigger->triggeredEvents = std::vector<uint>(m_nEntries);
    if(!isTrace(processVariable) && m_trigger->arrayPosition != 0) {
      BOOST_LOG_TRIVIAL(warning) << "Array position for process variables that are no traces should be 0 instead of "
                                 << m_trigger->arrayPosition << " for triggered process variable: " << processVariable
                                 << ". No search will be performed." << endl;
      return;
    }
    BOOST_LOG_TRIVIAL(debug) << "Start trigger search..." << endl;
    Long64_t event = 0;
    Long64_t toProcess = m_nEntries;
    Long64_t processed = 0;
    if(m_trigger->simpleSearch) {
      event = getNextEvent(m_trigger->nextEvent, m_trigger->increase);
      if(m_trigger->increase)
        toProcess = m_nEntries - event;
      else
        toProcess = event;
      if(event < 0 || event >= m_nEntries) {
        BOOST_LOG_TRIVIAL(error) << "Wrong start event(" << event << ") given when starting a trigger search!" << endl;
        m_trigger->nextEvent = -1;
        m_percentage = 100;
        m_done = true;
        return;
      }
    }

    // set default search result to no match found
    m_trigger->nextEvent = -1;
    //  for(Long64_t event = 0; event < m_nEntries; event++){
    while(true) {
      if(!prepareTree(event)) {
        continue;
      }
      // always use the same event id -> the same Trace is used every time and the data is replaced
      boost::fusion::for_each(data.table, detail::UpdateData(this, 1, 0, -1));
      const Trace* tl = &timeLines[processVariable];
      if(m_trigger->arrayPosition >= 0) {
        m_trigger->testValue(tl->y.at(m_trigger->arrayPosition), event);
      }
      else if(m_trigger->arrayPosition == -1) {
        if(tl->y.size() > 0) {
          auto mean = std::accumulate(tl->y.begin(), tl->y.end(), 0.0) / tl->y.size();
          m_trigger->testValue(mean, event);
        }
        else {
          BOOST_LOG_TRIVIAL(error) << "Array size is 0 in trigger decision calculation." << endl;
        }
      }
      else if(m_trigger->arrayPosition == -2) {
        auto max = std::max_element(tl->y.begin(), tl->y.end());
        m_trigger->testValue(*max, event);
      }
      else if(m_trigger->arrayPosition == -3) {
        auto min = std::min_element(tl->y.begin(), tl->y.end());
        m_trigger->testValue(*min, event);
      }
      else if(m_trigger->arrayPosition == -4) {
        for(size_t index = 0; index < tl->y.size(); index++) {
          m_trigger->testValue(tl->y.at(index), event);
        }
      }
      else {
        std::stringstream ss;
        ss << "Unknown array position given: " << m_trigger->arrayPosition
           << ". Allowed values are >0, -1 (mean), -2 (max), -3 (min), -4 (any)";
        throw std::runtime_error(ss.str());
      }
      processed += 1;
      m_percentage = 100. * processed / (1. * toProcess);
      m_newFile = false;
      if(m_interrupt) break;

      // stop simple serach if trigger was found
      if(m_trigger->simpleSearch && m_trigger->triggeredEvents[event]) {
        m_trigger->nextEvent = event;
        break;
      }
      event = getNextEvent(event, m_trigger->increase);
      if(event < 0) break;
    }
    if(m_trigger->simpleSearch) {
      if(m_trigger->nextEvent >= 0)
        BOOST_LOG_TRIVIAL(debug) << "Trigger search done. Found next event:" << m_trigger->nextEvent << "." << endl;
      else
        BOOST_LOG_TRIVIAL(debug) << "Trigger search done. No trigger found in simple search." << endl;
    }
    else {
      BOOST_LOG_TRIVIAL(debug) << "Trigger search done. Found " << m_trigger->getNTrigger() << " events." << endl;
    }
    m_lastTrigger.reset(new triggerData(std::move(*m_trigger.get())));
    m_percentage = 100;
    m_done = true;
  }

  void DataHandler::startTriggerSearch(std::string processVariable, const double& triggerThreshold,
      const std::string& triggerType, const int& arrayPosition) {
    m_trigger.reset(new triggerData(processVariable, triggerType, triggerThreshold, arrayPosition));
    reset();
    timeLines.clear();
    m_worker = make_unique<std::thread>(&DataHandler::getTriggerDecision, this);
  }

  Long_t DataHandler::findNextTrigger(const Long_t& currentEvent) {
    if(m_lastTrigger->simpleSearch) return m_lastTrigger->nextEvent;
    for(int i = currentEvent + 1; i < m_nEntries; i++) {
      if(m_lastTrigger->triggeredEvents.at(i) > 0) {
        BOOST_LOG_TRIVIAL(debug) << "Next triggered event is: " << i << endl;
        return i;
      }
    }
    return -1;
  }

  Long_t DataHandler::findPreviousTrigger(const Long_t& currentEvent) {
    if(m_lastTrigger->simpleSearch) return m_lastTrigger->nextEvent;
    for(int i = currentEvent - 1; i >= 0; i--) {
      if(m_lastTrigger->triggeredEvents.at(i) > 0) {
        BOOST_LOG_TRIVIAL(debug) << "Next triggered event is: " << i << endl;
        return i;
      }
    }
    return -1;
  }

  void DataHandler::startSimpleTriggerSearch(std::string processVariable, const double& triggerThreshold,
      const std::string& triggerType, const int& arrayPosition, const Long_t& currentEvent, const bool& increase) {
    m_trigger.reset(new triggerData(processVariable, triggerType, triggerThreshold, arrayPosition, increase));
    m_lastTrigger.reset(nullptr);
    reset();
    timeLines.clear();
    // Use next event to set the start point for the trigger search
    m_trigger->nextEvent = currentEvent;
    m_trigger->simpleSearch = true;
    m_worker = make_unique<std::thread>(&DataHandler::getTriggerDecision, this);
  }

  bool DataHandler::isTrace(std::string processVariable) {
    auto b = m_chain->GetBranch(processVariable.c_str());
    if(!b) {
      throw std::runtime_error(std::string("Could not find branch with name: ") + processVariable);
    }
    if(std::string(b->GetClassName()).empty())
      return false;
    else {
      BOOST_LOG_TRIVIAL(debug) << "Process variable " << processVariable << " with type "
                               << m_chain->GetBranch(processVariable.c_str())->GetClassName() << endl;
      return true;
    }
  }

  void DataHandler::setLogLevel(int logLevel) {
    if(logLevel == 0) {
      boost::log::core::get()->set_filter(boost::log::trivial::severity >= boost::log::trivial::debug);
    }
    else if(logLevel == 1) {
      boost::log::core::get()->set_filter(boost::log::trivial::severity >= boost::log::trivial::info);
    }
    else {
      boost::log::core::get()->set_filter(boost::log::trivial::severity >= boost::log::trivial::error);
    }
  }

  void DataHandler::readTimeStamp(const Long_t& event) {
    prepareTree(event);
    readTimeStamp();
  }

  void DataHandler::readTimeStamp() {
    if(m_timeStamp != nullptr) m_timeStampBranch->GetEntry(m_localEntry);
    if(m_tinfo != nullptr) m_tBranch->GetEntry(m_localEntry);
  }

  std::pair<Long_t, UInt_t> DataHandler::getTimeStamp(const char* filename, std::string treeName, const Long_t& event) {
    TFile f(filename);
    TTree* t = nullptr;
    f.GetObject(treeName.c_str(), t);
    if(t == nullptr) throw std::runtime_error(std::string("Failed to read ") + treeName + "from file: " + filename);
    BOOST_LOG_TRIVIAL(debug) << "Opened tree: " << treeName << " from file: " << filename << " which contains "
                             << t->GetEntries() << " entries." << endl;
    std::pair<Long_t, UInt_t> result;
    bool hasTimeStamp = false;
    TTimeStamp* timeStamp = new TTimeStamp();
    hdf5converter::timeInfo_t* tinfo;
    auto bTimeInfo = t->GetBranch("timeStamp");
    if(bTimeInfo == nullptr) {
      tinfo = new hdf5converter::timeInfo_t();
      bTimeInfo = t->GetBranch("timeInfo");
      if(bTimeInfo != nullptr) bTimeInfo->SetAddress(&tinfo);
    }
    else {
      hasTimeStamp = true;
      bTimeInfo->SetAddress(&timeStamp);
    }
    if(bTimeInfo == nullptr)
      throw std::runtime_error(std::string("Failed to read timeInfo from ") + treeName + " in file: " + filename +
          " which contains " + std::to_string(t->GetEntries()) + " entries!");

    t->GetEvent(event);
    if(hasTimeStamp) {
      result.first = timeStamp->GetSec();
      result.second = timeStamp->GetNanoSec() / 1000.;
    }
    else {
      result.first = tinfo->timeStamp;
      result.second = tinfo->msec;
    }
    BOOST_LOG_TRIVIAL(debug) << "Read time stamp: " << result.first << "." << result.second << endl;
    return result;
  }

  std::pair<bool, double> DataHandler::isDone() {
    std::pair<bool, double> p;
    p.first = m_done;
    p.second = m_percentage;
    if(m_done) m_worker->join();
    return p;
  }

  std::string DataHandler::extractTreeName(const std::string& file) {
    TFile* f = TFile::Open(file.c_str());
    auto l = f->GetListOfKeys();
    std::string t("TTree");
    for(Int_t key = 0; key < l->GetSize(); key++) {
      auto obj = f->Get(l->At(key)->GetName());
      if(t.compare(obj->ClassName()) == 0) {
        std::string treeName(l->At(key)->GetName());
        f->Close();
        return treeName;
      }
    }
    f->Close();
    throw std::runtime_error(std::string("No TTree found in the root file: ") + file);
  }

  template struct chainHelper<TArrayF>;
  template struct chainHelper<TArrayD>;
  template struct chainHelper<TArrayI>;
  template struct chainHelper<TArrayL>;
  template struct chainHelper<TArrayS>;
  template struct chainHelper<TArrayC>;
} // namespace uDAQ
