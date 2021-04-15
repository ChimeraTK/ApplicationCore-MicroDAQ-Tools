import sys
# Set path to find root
sys.path.append("/usr/lib/root")
import ROOT
# Load micro daq library
ROOT.gSystem.Load("/usr/lib/libApplicationCore-MicroDAQ-Tools.so")
from ROOT.uDAQ import DataHandler, Trace, TimeAxis
from PyQt5.QtCore import QThread, pyqtSignal
import logging
from time import sleep

def pyboolToRoot(pybool):
  '''
  Convert a python bool to ROOT type bool
  '''
  if pybool == True:
    return ROOT.kTRUE
  else:
    return ROOT.kFALSE

class worker(QThread):
  triggerResult = pyqtSignal(int)
  percentage = pyqtSignal(float)
  updated = pyqtSignal()
  def __init__(self, args):
    QThread.__init__(self)
    if args.debug == True:
      DataHandler.setLogLevel(0)
    else:
      DataHandler.setLogLevel(1)
    vMatch = ROOT.vector('std::string')()
    for i in args.matchString:
      vMatch.push_back(i)
    self.DataHandler = DataHandler(args.path[0], pyboolToRoot(args.sortByTimeStamp), vMatch, args.maxFiles)
    if self.DataHandler.getTreeName() == "llrf_server_data":
      logging.info("Working on LLRF data.")
#       self.DataHandler = DataHandlerLLRF(args.path, pyboolToRoot(args.sortByTimeStamp), args.matchString, args.maxFiles)
      self.averaging = args.averaging
      self.isLLRFData = True
    else:
      logging.info("Working on generic MicroDaq data.")
      self.isLLRFData = False
    self.maxEvents = self.DataHandler.getEntries()
    self.nEvents = 0
    self.currentEvent = 0
    self.arrayPosition = 0
    self.pvSet =  ROOT.set('std::string')()
    self.data = ROOT.map('std::string', 'uDAQ::Trace')()
    self.triggerInfo = {}
  def getNFiles(self):
    return self.DataHandler.getNFiles()
  
  def getNBranches(self):
    return self.DataHandler.getNBranches()
  
  def getTimeStamp(self, event):
    self.DataHandler.readTimeStamp(event)
    try:
      return (self.DataHandler.m_timeStamp.GetSec(), self.DataHandler.m_timeStamp.GetNanoSec()/1000)
    except ReferenceError:
      return (self.DataHandler.m_tinfo.timeStamp, self.DataHandler.m_tinfo.msec)
  
  def isTrace(self,pv):
    return self.DataHandler.isTrace(pv)
  
  def getBranchList(self):
    return self.DataHandler.getBranchList()
  
  def prepareWorker(self, nEvents, pvs, currentEvent, type, arrayPosition = 0, decimation = 1):
    '''
    Prepare thread for an data update.
    @param nEvents: Number of events added up for the parameter 
    @param pvs (std::set<std::string>): set of process variables
    @param currentEvent (int): Current event
    @param arrayPosition (int): Position in arrays to be used when constructing arrays
    @param decimation (int): In the event loop the event number is increased by this value
    @param type (int): Set the requested type of data:
          - 0: No chain
          - 1: Chained events
          - 2: Time range 
          - 3: All events 
    '''
    self.nEvents = nEvents
    self.pvSet = pvs
    self.currentEvent = currentEvent
    self.arrayPosition = arrayPosition
    self.requestType = type
    self.decimation = decimation
    
  def prepareTriggerSearch(self, triggerPV, currentEvent, triggerThreshold, operator, arrayPosition, findNext, simpleSearch):
    '''
    Prepare a trigger search.
    @param triggerPV (string): The process varibale used as trigger.
    @param currentEvent (int): Where to start the search.
    @param triggerThreahols (double): The trigger treshold.
    @param operator (string): The operator used for triggering (<, >, =)
    @param arrayPosition (int): If the trigger source is a trace the position given here is considered for triggering.
                                If arrayPosition < 0 the whole trace will be consered for triggering.
    @param findNext (bool): Defines the trigger direction. The search is always started at currentEvent. If true
                            only events after the currentEvent are investigated. Else events before currentEvent.
    @param simpleSearch (bool): If true only the next trigger is searched for. Else all events are investigated.
    '''
    self.triggerInfo['threshold'] = triggerThreshold
    self.triggerInfo['operator'] = operator
    self.triggerInfo['findNext'] = findNext
    self.pvSet.clear()
    self.pvSet.insert(triggerPV)
    self.currentEvent = currentEvent
    self.arrayPosition = arrayPosition
    self.triggerInfo['simpleSearch'] = simpleSearch

  
  def run(self):
    '''
    The worker can perform two tasks:
    1. Perform a trigger search.
    @signal: triggerResult(int): Emitted when trigger search is done
    @signal: percentage: Updates the percentage that is already processed.
    
    2. Construct an array containing the parameter values for a certain number of events.
    In case the parameter is an array per event and no chain is used
    only the user defined index is considered,
    @signal: percentage: Updates the percentage that is already processed.
    @signal: updated: Emitted when worker is ready
    
    @warning: Don't use the signal finished, since it is emitted in both cases and you don't know what was done. 
    '''
    if len(self.triggerInfo) != 0:
      event = -1
      if(self.triggerInfo['simpleSearch'] == True):
        self.DataHandler.startSimpleTriggerSearch(list(self.pvSet)[0],
                                                  self.triggerInfo['threshold'], 
                                                  self.triggerInfo['operator'], 
                                                  self.arrayPosition,
                                                  self.currentEvent,
                                                  self.triggerInfo['findNext'])
        while(True):
          (done, percentage) = self.DataHandler.isDone()
          self.percentage.emit(percentage)
          if done == True:
            break
          sleep(0.5)
        logging.info("Finished simple trigger search.")
        
      else:
        self.DataHandler.startTriggerSearch(list(self.pvSet)[0],self.triggerInfo['threshold'], self.triggerInfo['operator'], self.arrayPosition)
        while(True):
          (done, percentage) = self.DataHandler.isDone()
          self.percentage.emit(percentage)
          if done == True:
            break
          sleep(0.5)
        logging.info("Finished complete trigger search.")
          
      if(self.triggerInfo['findNext'] == True):
        event = self.DataHandler.findNextTrigger(self.currentEvent)
      else:
        event = self.DataHandler.findPreviousTrigger(self.currentEvent)
      logging.info("Trigger search found trigger {}".format(event))  
      self.triggerResult.emit(event)
      self.triggerInfo.clear()
      return
    
    self.data.clear()
    self.DataHandler.prepareReading(self.pvSet)
    # read singe event
    if self.requestType == 0:
#       self.data = self.DataHandler.getTimeLine(self.currentEvent,self.currentEvent+1,self.arrayPosition, 2)
      self.DataHandler.readData(self.currentEvent)
      for pv in self.pvSet:
        self.data[pv] = self.DataHandler.timeLines[pv]
        if self.data[pv].x.size() > 1:
          # put time info to the x vector in case of LLRF data
          if self.isLLRFData:
            for i in range(self.data[pv].x.size()):
              self.data[pv].x[i] = i*10. / (65e6 / self.averaging)
        else:
          (ts, tms) = self.getTimeStamp(self.currentEvent)
          self.data[pv].x[0] = ts + tms*1./1000
          logging.debug("Filling: " + str(ts + tms*1./1000) + " result: " + str(self.data[pv].x.at(0)))
    else:
      # read chained events
      if self.requestType == 1:
        self.DataHandler.getTimeLine(self.currentEvent*self.nEvents,(self.currentEvent+1)*self.nEvents, self.decimation, self.arrayPosition, pyboolToRoot(True))
      # read time range 
      elif self.requestType == 2:
        self.DataHandler.getTimeLine(self.currentEvent,self.currentEvent + self.nEvents, self.decimation, self.arrayPosition, pyboolToRoot(True))
      # read all events
      else:
        self.DataHandler.getTimeLine(0,self.maxEvents, self.decimation,self.arrayPosition, pyboolToRoot(True))
      
      while(True):
        (done, percentage) = self.DataHandler.isDone()
        self.percentage.emit(percentage)
        if done == True:
          break
        sleep(0.5)
      self.data = self.DataHandler.timeLines
    logging.info("Worker done")
    self.updated.emit()
    
  def stop(self):
    self.DataHandler.stop()

