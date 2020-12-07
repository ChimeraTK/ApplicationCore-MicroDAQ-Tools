from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5 import QtWidgets
from PyQt5.QtGui import QLabel
import h5py
import logging
import numpy as np
import datetime

class errorPopup(QtWidgets.QWidget):
  '''
  Simple pop up to show errors. 
  Since all here is running in a different thread we can not simply throw an exception....
  '''  
  def __init__(self, name):
      super().__init__()

      self.name = name

      self.initUI()

  def initUI(self):
      lblName = QLabel(self.name, self)

class Trigger():
  '''
  The trigger class is used to implement a trigger that can be used to find a 
  specific data set fullfilling the trigger condition.
  Three inputs are required:
  - Trigger source: The item from the item list to trigger on
  - Trigger operator: Choose a certain trigger condition operator (<,=,>)
  - Trigger level: Choose the trigger level
  
  If no event fullfills the trigger search will return the initial start event. 
  @param worker(chimeratk_daq.worker): The worker that is using the trigger.
  @param limits(int,int): The limits of the trigger search.
  '''
  def __init__(self, worker, limits):
    self.startEvent = None
    self.limits = limits
    self.source = None
    self.worker = worker
    self.findNext = None
    self.searchRequested = False
    self.eventNumber = None
    self.found = False
    self.threshold = None
    self.operator = None
    self.arrayPos = None
    self.isTrace = None

  def getValueToCompare(self, hdf5Object):
    if not self.isTrace:
      return hdf5Object[0]
    if(self.arrayPos == -1):
      arr = np.asarray(hdf5Object)
      return arr.mean()
    elif(self.arrayPos == -2):
      arr = np.asarray(hdf5Object)
      return arr.max()
    elif(self.arrayPos == -3):
      arr = np.asarray(hdf5Object)
      return arr.min()
    else:
      return hdf5Object[self.arrayPos]
  
  def testValue(self, hdf5Object):
    '''
    Test if a data point fullfills the trigger requirement.
    This is called on every event to be checked.
    @return True if event fullfills the trigger requirement.
    '''
    for subitem in self.source.split("/"):
      if subitem != "":
        hdf5Object = hdf5Object[subitem]
    if self.operator == ">":
      if(self.arrayPos == -4):
        if any(i > self.threshold for i in hdf5Object) == True:
          return True
      else:
        if self.getValueToCompare(hdf5Object) > self.threshold:
          return True
    elif self.operator == "<":
      if(self.arrayPos == -4):
        if any(i < self.threshold for i in hdf5Object) == True:
          return True
      else:
        if self.getValueToCompare(hdf5Object) < self.threshold:
          return True
    elif self.operator == "=":
      if(self.arrayPos == -4):
        if any(i == self.threshold for i in hdf5Object) == True:
          return True
      else:
        if self.getValueToCompare(hdf5Object) == self.threshold:
          return True
        
    else:
      raise TypeError("Unknown operator set: " + self.operator)
    return False
     
  def popError(self, msg):   
    '''
    Pop up an error message.
    @param msg (string): The messgage to be shown in the popup dialog
    '''  
    self.exPopup = errorPopup(msg)
    self.exPopup.setGeometry(100, 200, 700, 100)
    self.exPopup.show()
  
  def findEvent(self):
    '''
    Actual event/data loop to search for trigger. Trigger search starts 
    Once a trigger is found search is stopped.
    You can investigate the trigger search result by checking: 
    - found: True if triggered event is found
    - eventNumber: The event that fullfills the trigger requirement. If no event fullfills the requirement this is the event where the search started.
    The search can be interrupted by setting the parameter stop of the worker to True. 
    '''
    logging.debug("Current trigger parameter: TH: {}, Source: {}, ArrayPos: {}, Operator: {}, IsTrace: {}".format(self.threshold, self.source, self.arrayPos, self.operator, self.isTrace))
    if self.source == None:
      logging.debug("No trigger source set")
      msg = "No trigger source set! \n Please choose a source by adding one from the item list and use right click context menu..."
      self.popError(msg)
      return
    iFirstEvent = self.startEvent
    if (iFirstEvent == self.limits[1]) and self.findNext == True:
      logging.debug("Already at the end.")
      return
    if (iFirstEvent == 0) and self.findNext == False:
      logging.debug("Already at the beginning.")
      return
    try:
      # increasing event number loop
      if(self.findNext == True):
        self.eventNumber = iFirstEvent + 1
        while(self.eventNumber < self.limits[1]):
          if self.worker.stop:
            logging.info("Event loop was stopped by the user.")
            self.worker.percentage.emit(100)
            return
          self.worker.percentage.emit(100.*self.eventNumber/(self.limits[1]-iFirstEvent))
          if self.testValue(self.worker.getHDF5Object(self.eventNumber)) == True:
            self.worker.percentage.emit(100)
            self.found = True
            return
          self.eventNumber = self.eventNumber + 1
        self.eventNumber = iFirstEvent
      # decreasing event number loop
      else: 
        self.eventNumber = iFirstEvent - 1
        while(self.eventNumber >= self.limits[0]):
          if self.worker.stop:
            logging.info("Event loop was stopped by the user.")
            self.worker.percentage.emit(100)
            return
          self.worker.percentage.emit(100.*(iFirstEvent-self.eventNumber)/(iFirstEvent - self.limits[0]))
          if self.testValue(self.worker.getHDF5Object(self.eventNumber)) == True:
            self.worker.percentage.emit(100)
            self.found = True
            return
          self.eventNumber = self.eventNumber - 1
        self.eventNumber = iFirstEvent
    except TypeError as msg:
      self.eventNumber = iFirstEvent
      self.popError(msg)

class worker(QThread):
  '''
  Worker class to be used with the HDF5Viewer.
  It starts a separate thread in order not to block the main GUI window.
  Two tasks can be handled by the worker:
  - trigger search
  - data collection
   Comunication with the main thread is done via signals.
   See also run().
   '''
  
  updateStatus = pyqtSignal(int)
  triggerResult = pyqtSignal(int)
  percentage = pyqtSignal(float)
  updated = pyqtSignal()
  
  def __init__(self, app, files, sortByTimeStamp = False, maxFiles = None):
    QThread.__init__(self, app)
    self.app = app
    self.stop = False
    self.files = []      # list of the actual opened hdf5 files
    self.eventList = {}  # pair of file index and hdf5 file toplevel object
    self.nEvents = 0
    self.loadFiles(files, sortByTimeStamp, maxFiles)
    self.trigger = Trigger(self, (0,self.nEvents))
    # Data collection parameters
    self.arrayPos = None # array position considered for data colletcion
    self.isSingleEvent = None     # type of data collection
    self.data = {}       # collected data
    self.plotItems = []  # list of items to be collected
    self.nChainEvents = None # NUmber of chained events
    self.eventRange = (0,self.nEvents) # Range to loop over
    self.decimation = None
        
  def loadFiles(self, files, sortByTimeStamp, maxFiles):
    for filename in files:
      try:
        self.files.append(h5py.File(filename, 'r'))
        # no need to check max files here because is sortByTimeStamp is false the shrinking is already done
      except OSError:
        logging.error("Failed to open file: " + filename)
    if sortByTimeStamp:
      # if sort by time stamp is required sort and shrink list now
      logging.debug("Sorting files by time stamp...")
      self.files.sort(key=lambda x: next(iter(x.keys())))
      self.files = self.files[len(self.files)-maxFiles:]
      logging.debug("Sorting files done.")
      

    logging.info("Reading events...")
    fileIndex = 0
    for theFile in self.files:
      logging.info("File " + str(fileIndex) + " (" + theFile.filename + ")")
      for toplevel in theFile:
        self.eventList[self.nEvents] = (fileIndex, toplevel)
        self.nEvents = self.nEvents + 1
      fileIndex = fileIndex + 1

  def getTimeString(self, event):
    ''' 
    Get the timestamp of an event as string.
    @param event(int): Event number.
    @return The timestamp string as e.g. 2020-01-01 00:00:00.12
    '''
    if event == -1:
      event = self.nEvents-1
    (fileIndex, toplevel) = self.eventList[event]
    return toplevel
  
  def getHDF5Object(self, event):
    '''
    Get the HDF5 object correcponding to the given event number.
    @param event(int): Event numbner.
    '''
    # find corresponding top-level directory name and file
    (fileIndex, toplevel) = self.eventList[event]
    # get the file
    theFile = self.files[fileIndex]
    # return the toplevel object
    return theFile[toplevel]

  def getNumberOfEvents(self):
    return self.nEvents
  
  def prepareTrigger(self, app, startEvent, next, operator, threshold, arrayPosition):
    self.trigger.threshold = threshold
    self.trigger.operator = operator
    self.trigger.arrayPos = arrayPosition
    self.trigger.searchRequested = True
    self.trigger.findNext = next
    self.trigger.startEvent = startEvent
    self.stop = False
    
  def prepareDataCollection(self, eventRange, arrayPosition, isSingleEvent, items, nChainEvents, decimation):
    self.arrayPos = arrayPosition
    self.isSingleEvent = isSingleEvent
    self.data = {}
    self.plotItems = items
    self.nChainEvents = nChainEvents
    self.eventRange = eventRange
    self.trigger.searchRequested = False
    self.decimation = decimation
    self.stop = False
    
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
    
    # Trigger search
    if self.trigger.searchRequested:
      logging.debug("Satring trigger search.")
      self.trigger.findEvent()
      
      if not self.trigger.found:
        logging.info("No trigged event found!")
      else:
        logging.info("Trigged event is: " + str(self.trigger.eventNumber))
        
      self.triggerResult.emit(self.trigger.eventNumber)
      self.trigger.searchRequested = False
      self.trigger.found = False
      return
    # Data collection
    else:
      logging.debug("Starting data collection.")
  
      for event in range(self.eventRange[0], self.eventRange[1], self.decimation):
        if self.stop:
          logging.info("Event loop was stopped by the user.")
          break
        #event loop
        hdfObject = self.getHDF5Object(event)
        for item in self.plotItems:
          if not item in self.data:
            self.data[item] = ([],[])
          # item loop
#           logging.debug("Looking for item: /{}{}".format(toplevel,item))
          toplevel = self.eventList[event][1]
          dataObject = hdfObject["/"+toplevel+item]
#           logging.debug("Object has shape: {} test: {}".format(dataObject.shape[0], dataObject.shape[0] > 1))
          
          timestamp = datetime.datetime.strptime(toplevel.strip('/'),"%Y-%m-%d %H:%M:%S.%f")
          if self.isSingleEvent:
            if self.eventRange[1] - self.eventRange[0] != 1:
              logging.error("Error when type no chain is requested.")
            arr = np.asarray(dataObject,dtype=np.float32)
            i = 0
            for y in arr:
              self.data[item][0].append(i)
              self.data[item][1].append(y)
              i = i+1 
          else:
            self.data[item][0].append(timestamp.timestamp())
            if not dataObject.shape[0] > 1:
              # scalar
#               logging.debug("Extracted scalar data: {}".format(dataObject[0]))
              self.data[item][1].append(dataObject[0])
            else:
              # array
              arr = np.asarray(dataObject,dtype=np.float32)
              if self.arrayPos >= 0:
                self.data[item][1].append(arr[self.arrayPos])
#                 logging.debug("Extracted array data: {}".format(arr[self.arrayPos]))
              elif self.arrayPos == -1:
                arr = np.asarray(dataObject)
                self.data[item][1].append(arr.mean())
              elif self.arrayPos == -2:
                arr = np.asarray(dataObject)
                self.data[item][1].append(arr.max())
              elif self.arrayPos == -3:
                arr = np.asarray(dataObject)
                self.data[item][1].append(arr.min())
              else:
                logging.error("Unknown array position: {}".format(self.arrayPos))
          
        self.percentage.emit(100.*event/(self.eventRange[1]-self.eventRange[0]))
      for item in self.plotItems:
        # convert to numpy
        self.data[item] = (np.asarray(self.data[item][0]),np.asarray(self.data[item][1]))
      self.percentage.emit(100)
      self.updated.emit()
      logging.debug("Data collection done")
      return 
 