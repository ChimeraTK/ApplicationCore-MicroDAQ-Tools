/*
 * DataHandler.h
 *
 *  Created on: May 28, 2018
 *      Author: Klaus Zenker (HZDR)
 */

#ifndef DATAHANDLER_H_
#define DATAHANDLER_H_

#include "TTree.h"
#include "TChain.h"
#include "TPad.h"
#include "TGraph.h"
#include "TMultiGraph.h"
#include "TArrayF.h"
#include "TArrayI.h"
#include "TArrayD.h"
#include "TArrayL.h"
#include "TArrayS.h"
#include "TTimeStamp.h"

#include "data_types.h"

#include <thread>
#include <atomic>
#include <memory>
#include <set>
#include <numeric>

#include <boost/log/trivial.hpp>
#include <boost/fusion/container/map.hpp>

namespace uDAQ{

/**
 * Trigger information.
 *
 * This class is also used to steer the trigger search. Two possible search routines are covered:
 * - Next event only: Start from the nextEvent and look for the next event only.
 * - Investigate all events and store the result in triggered events.
 */
struct triggerData{
  std::string processVariable; ///< The trigger variable
  std::string type; ///< The comparison operator: '<', '>', '='
  Double_t threshold; ///< The trigger threshold
  int arrayPosition; ///< Array position used for trigger decision. If < 0 special comparisons values are compared to the trigger threshold: -1 (mean), -2 (max), -3 (min), -4 (any value)
  bool increase; ///< Define the direction used to search for a trigger
  bool simpleSearch; ///< If true only the next trigger is searched
  Long_t nextEvent; ///< Used when doing a trigger search for the next event.
  std::vector<uint> triggeredEvents; ///< Stored event numbers fulfilling the trigger criteria. Used when doing a complete search.
  triggerData(const triggerData &) = delete;
  triggerData(triggerData &&) = default;
  triggerData(const std::string &_processVariable,const std::string &_type, const Double_t &_threshold, const int &_arrayPosition, const bool &_increase = true):
    processVariable(_processVariable), type(_type), threshold(_threshold), arrayPosition(_arrayPosition), increase(_increase), simpleSearch(false), nextEvent(0){};
  /**
   * Compare trigger information with other trigger information.
   *
   * Used to check if the trigger was changed and trigger decision has to be recalculated.
   */
  bool operator==(const triggerData &d){
    // always return false if simple search was used to trigger a new search in DataHandler::getTriggerDecision()
    if(simpleSearch || d.simpleSearch)
      return false;
    if(d.threshold == threshold && d.type.compare(type) == 0 && d.processVariable.compare(processVariable) == 0 && d.arrayPosition == arrayPosition)
      return true;
    else
      return false;
  }

  void testValue(const Double_t &value, const Long64_t &event){
    if(type.compare(">") == 0 && value > threshold)
      triggeredEvents.at(event)++;
    if(type.compare("<") == 0 && value < threshold)
      triggeredEvents.at(event)++;
    if(type.compare("=") == 0 && value == threshold)
      triggeredEvents.at(event)++;
  }

  size_t getNTrigger(){
    return std::accumulate(triggeredEvents.begin(), triggeredEvents.end(),0);
  }
};

template <typename T>
struct chainHelper{
  T* parr;
  T arr;
  TBranch* branch;
  bool isTrace;
//  std::map<std::string,std::pair<T, T*> > map;
  chainHelper(TBranch* b, const bool &istrace = false): branch(b), isTrace(istrace){
    if(isTrace){
      arr = T();
    } else {
      arr = T(1);
    }
    parr = &arr;
  }
  chainHelper():parr(nullptr), branch(nullptr), isTrace(false){};
};

extern template struct chainHelper<TArrayF>;

/**
 * Copied from ChimeraTK
 * \ToDo: Check if the original can be used here.
 */
template<template<typename> class TemplateClass>
class TemplateUserTypeMap {
 public:
  boost::fusion::map<boost::fusion::pair<TArrayF, TemplateClass<TArrayF>>,
                     boost::fusion::pair<TArrayD, TemplateClass<TArrayD>>,
                     boost::fusion::pair<TArrayI, TemplateClass<TArrayI>>,
                     boost::fusion::pair<TArrayL, TemplateClass<TArrayL>>,
                     boost::fusion::pair<TArrayS, TemplateClass<TArrayS>>
//                     boost::fusion::pair<Double_t, TemplateClass<Double_t>>
                     > table;
};

enum TimeAxis{ FALSE, TRUE, AUTO};

namespace detail{
  struct UpdateData;
}

class DataHandler{
protected:
  /**
   * \defgroup thread Thread related members used when reading a time line or performing a trigger search.
   * @{
   */

  std::unique_ptr<std::thread> m_worker;
  std::atomic<bool> m_done;
  std::atomic<bool> m_interrupt;
  std::atomic<double> m_percentage; ///< During time line data processing here the processing in percent is stored

  Long_t m_start;
  Long_t m_end;
  size_t m_decimation; ///< Decimation used in the event loop of getTimeLine
  int m_arrayPosition;
  TimeAxis m_timeAxis;

  void reset(){
    m_done = false;
    m_interrupt = false;
    m_percentage = 0.0;
  }

  /* @} */

  TChain* m_chain; ///< Chain holding all events
  std::string m_treeName; ///< Name of the data TTree
  std::vector<std::string> m_branches; ///< vector of branch names found in the tree
  Int_t m_nTrees; ///< Number of trees in the chain (equal to the number of files)
  Long64_t m_nEntries; ///< Number of all entries in the chain
  std::unique_ptr<triggerData> m_lastTrigger; ///< <<ProcessVariable, triggerType> , triggered Events>
  std::unique_ptr<triggerData> m_trigger; ///< <<ProcessVariable, triggerType> , triggered Events>
  Long64_t m_localEntry; ///< The entry in the current file corresponding to the current event (see prepareTree)
  bool m_newFile;

//  std::pair<Long_t, UInt_t> m_tResult;
  TBranch* m_tBranch;
  TBranch* m_timeStampBranch;

  size_t m_nActiveBranches; ///< Number of variables filled by prepareReading

  /**
   * When looping over a TChain the branch addresses need to be set for each file in the chain.
   * Here the branch addresses are set. In the end the data is loaded by calling TBranch::GetEnty()
   *
   * \param it A pointer to the data to be updated after calling this function.
   * \attention prepareData needs to be called before since data is read for m_localEntry.
   */
//  void updateData(const size_t &i);

  /**
   * Find the file in the chain that includes event and set m_localEntry, which is the corresponding event number in the file.
   *
   * \param event The global event number.
   * \return False in case there was an error when loading file from the chain.
   */
  bool prepareTree(const Long_t &event);

  /**
   * Read time stamp data of the current localEntry.
   */
  virtual void readTimeStamp();

  /**
   * This method is executed in a separate thread
   */
  void collectData();

  /**
   * This is the trigger search function that is executed in a separate thread.
   * It loops over all events and test if they fulfill the trigger criteria (stored in m_trigger).
   * The trigger decisions are stored in the triggerData object. They are accessed later via m_lastTrigger.
   */
  void getTriggerDecision();

  /**
   * Check if the given file matches one of the strings in matchStrings.
   *
   * \param file The file name to be tested
   * \param matchStrings The strings to be tested
   * \return True if the file name matches one of the strings in matchStrings partly or if the
   * size of matchStrings is 0. Else false is returned.
   */
  bool checkMatch(const std::string &file, const std::vector<std::string> &matchStrings);

  /**
   * Extract type information for a given variable.
   * \param variable The name of the variable in the root file.
   * \return The type to be chosen for the fusion map:
   * - 1: float
   * - 2: TArrayF
   * - 3: double
   * - 4: TArrayD
   */
  size_t getTypeFromTree(const char *branchName);

  template <typename T>
  void setupBranch(const std::string &branchName){
    auto& dataArr = boost::fusion::at_key<T>(data.table);
    TBranch* branch;
    std::string tmp = branchName;
    replace(tmp.begin(), tmp.end(), '/', '.');
    bool isTrace = DataHandler::isTrace(tmp);
    BOOST_LOG_TRIVIAL(info) << "Adding branch " << branchName.c_str() << " to list of active branches (isTrace: " << isTrace << ")." << std::endl;
    dataArr.insert(std::make_pair(tmp,chainHelper<T>(nullptr, isTrace)));
    // if not here but in the constructor a segfault is caused
    dataArr[tmp].parr = &dataArr[tmp].arr;
    if (isTrace){
      m_chain->SetBranchAddress(tmp.c_str(), &dataArr[tmp].parr, &branch);
    } else {
      m_chain->SetBranchAddress(tmp.c_str(), &(dataArr[tmp].arr[0]), &branch);
    }
    dataArr[tmp].branch = branch;
  }

  /**
   * Simply increase or decrease the event number based on the maximum event number and the given event.
   * \param last The last event number. Used to calculate the next event.
   * \param increase If true the next event is last + 1. Else it is last -1.
   *
   * \return The next event. If it is invalid -1 is returned. This happens if event limits are reached (either -1 or nMax).
   */
  Long64_t getNextEvent(Long64_t last, bool increase =  true);

public:
  /**
   * Depending on the available information in the Root file either m_tinfo or m_timeStamp will be filled.
   */
  hdf5converter::timeInfo_t* m_tinfo;///< Depricated time information written by the hdf5converter
  TTimeStamp* m_timeStamp;///< Current time information written by ctk::RootDAQ

//  template<typename UserType>
//  using BranchList = std::vector<std::string>;
//  TemplateUserTypeMap<BranchList> branchList;

  template<typename UserType>
  using DataList = std::map<std::string, chainHelper<UserType> >;
  TemplateUserTypeMap<DataList> data;

  std::map<std::string, Trace> timeLines;///< Store time line data for process variables

  /**
   * If no TTree name is passed the first TTree found in the file will be used.
   *
   * \param folder Folder used to search for root files.
   * \param sort If true root files are opened and the timestamp of the first event is extracted. Input files are sorted afterwards
   * by this timestamp.
   * \param matchString If set only files matching the given string are considered.
   * This can be used to work on a subset of files.
   * \param maxFiles Limit the number of files to be processed. Files are sorted by name or by timestamp and only the
   * latest files are considered
   * \param treeName The name of the TTree holding the data.
   */
  DataHandler(const std::string &folder,
              const bool &sort = true,const std::vector<std::string> &matchString = std::vector<std::string>(), const size_t &maxFiles = 0,
              const std::string &treeName = "");
  virtual ~DataHandler();

  /**
   * Go through the list of keys in the given file and find the
   * first object that is a TTree.
   * That name can be used to set up a TChain with that name.
   *
   * \param file Name of the root file to be analysed.
   *
   * \return The name of the first TTree object.
   * \throw std::runtime_error if no TTree object is found.
   */
  static std::string extractTreeName(const std::string &file);

  /**
   * Read data from a TTree.
   * If the processVariable is a scalar the vector length of x any is 1.
   * \param processVariables Name of the process variables to be read. Can be given as Probe/amplitude and will
   * be converted to Probe.amplitude, which corresponds to the branch name in the TTree
   * \param event The event to be read.
   * \param dx The step width of the x vector (x axis).
   * return  Map that includes the x and y vectors. The key is the processVariable name.
   */
  void readData(const Long_t &event);

  /**
   * Prepare the data map for the given process variables.
   *
   * \remark In order to set branches the process variables names are changes: /Probe/Test -> .Probe.Test. The chainHelper uses the PV names.
   */
  void prepareReading(const std::set<std::string> &processVariables);

  /**
   * Start a worker thread that fills timeLines. The status of the data processing is accessible via m_percentage.
   * The worker can also be stopped via m_interrupt.
   *
   * \param startEvent First event to be processed.
   * \param endEvent First event that will not be processed any more.
   * \param decimation In the event loop the event number is increased by this value.
   * \param arrayPosition The element in arrays that is put into the trace. If it is -1 the average of the array is considered.
   * If it is -2 the maximum is considered. If it is -3 the minimum is considered.
   * \param TimeAxis If true the x axis is filled time stamps. Else index is used for the x axis.
   *
   */
  void getTimeLine(const Long_t startEvent = 0, Long_t endEvent = -1, const size_t &decimation = 1, const int &arrayPosition = 0, TimeAxis=TimeAxis::TRUE);

  /**
   * Plot data of an array stored in the TTree.
   * \param processVariable Name of the process variable to be read. Can be given as Probe/amplitude and will
   * be converted to Probe.amplitude, which corresponds to the branch name in the TTree
   * \param event The event to be read.
   */
  TGraph* plotTrace(std::string processVariable, const Long_t &event);

  /**
   * Plot data of arrays stored in the TTree.
   * \param processVariables Name of the process variables to be read. Can be given as Probe/amplitude and will
   * be converted to Probe.amplitude, which corresponds to the branch name in the TTree
   * \param event The event to be read.
   */
  TMultiGraph* plotTraces(const std::set<std::string> &processVariables, const Long_t &event);

  /**
   * Search for events that fulfill the trigger criteria. The last trigger criteria is stored internally and
   * if the next search uses the same criteria the search will finish immediately.
   * The search is done in a separate thread. Check if search is done by calling isDone()
   * After you can get trigger results by calling findNextTrigger or findPreviousTrigger.
   * \param currentEvent The trigger is searched starting at the given event. Events before that event are not considered.
   * \param triggerThreshold The threshold used to search for events
   * \param triggerType This should be an operator known to ROOT (e.g. >, <, ==)
   * \param arrayPosition If an position is given only the corresponding position in arrays is considered in the trigger decision
   */
  void startTriggerSearch(std::string processVariable, const double &triggerThreshold, const std::string &triggerType, const int &arrayPosition);

  /**
   * Search for the next event that fulfill the trigger criteria.
   * The search is done in a separate thread. Check if search is done by calling isDone()
   * After you can get trigger results by calling findNextTrigger or findPreviousTrigger.
   * \param currentEvent The trigger is searched starting at the given event. Events before that event are not considered.
   * \param triggerThreshold The threshold used to search for events
   * \param triggerType This should be an operator known to ROOT (e.g. >, <, ==)
   * \param arrayPosition If an position is given only the corresponding position in arrays is considered in the trigger decision
   * \param currentEvent Event where to start the trigger search
   * \param increase Define the search direction
   * \return The event number of the next triggered event. If no event was trigger -1 is returned.
   */
  void startSimpleTriggerSearch(std::string processVariable, const double &triggerThreshold, const std::string &triggerType, const int &arrayPosition, const Long_t &currentEvent, const bool &increase);

  /**
   * Search for the next triggered event with respect to the given current event.
   * \return The event number of the next triggered event. If no event was trigger -1 is returned.
   * \attention To be called after trigger search finished.
   */
  Long_t findNextTrigger(const Long_t &currentEvent);

  /**
   * Search for the previous triggered event with respect to the given current event.
   * \return The event number of the previous triggered event. If no event was trigger -1 is returned.
   * \attention To be called after trigger search finished.
   */
  Long_t findPreviousTrigger(const Long_t &currentEvent);

  static void setLogLevel(int LogLevel);

  /**
   * \return The number of TTrees in the internal TChain.
   * This number corresponds to the number of handled files.
   * \remark This number is read only once in the constructor.
   */
  int getNFiles(){return m_nTrees;}

  /**
   * \return Number of branches in the chain. It is 0 if the tree name was wrong.
   */
  int getNBranches(){return m_branches.size();}

  /**
   * \return The number of entries of the internal TChain.
   * This number is the number of input files times the number of events per file.
   * \remark This number is read only once in the constructor.
   */
  int getEntries(){return m_nEntries;}

  bool isTrace(std::string processVariable);

  std::string getTreeName(){ return m_treeName;};

  /**
   * Get a list of all branches in the TTree.
   * This list is similar to the process variables in the original h5 files, except that the delimiter is a dot instead of a slash.
   * Furthermore, it includes the time information branch.
   */
  std::vector<std::string> getBranchList(){return m_branches;};

  /**
   * Read the timestamp information for a given event.
   * \param event The event in the TTree to read the time from
   * \remark Depending on the available information in the Root file either m_tinfo (deprecated and written by hdf5converter) or
   *  m_timeStamp (written by ctk::RootDAQ) will be filled.
   */
  virtual void readTimeStamp(const Long_t &event);

  /**
   * Return the time stamp for a given event.
   * This requires to open the file once and read one event.
   * \param filename The name of the root file containing the llrf TTree
   * \param treeName The name of the TTree
   * \param event The event in the TTree to read the time from
   * \return Pair of seconds since EPOCH and micro seconds.
   * \remark This function is used to sort the files to be handled by the DataHandler if
   *         sorting is requested.
   */
  static std::pair<Long_t, UInt_t> getTimeStamp(const char* filename, std::string treeName, const Long_t &event = 0);

  /**
   * \defgroup thread Thread related members
   * @{
   */
  void stop(){m_interrupt = true;}
  std::pair<bool,double> isDone();
  /* @} */

  friend struct uDAQ::detail::UpdateData;
};
}

#endif /* DATAHANDLER_H_ */
