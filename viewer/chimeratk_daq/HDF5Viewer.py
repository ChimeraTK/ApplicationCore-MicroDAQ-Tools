#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys
import glob, os
import numpy
import math

import argparse
import logging

from PyQt5 import QtGui
from PyQt5 import QtCore
from PyQt5 import QtWidgets
import pyqtgraph as pg

import h5py
from chimeratk_daq.MicroDAQviewerUI import Ui_MainWindow
from chimeratk_daq.HDF5Worker import worker
from chimeratk_daq.TimeXAxis import DateAxisItem

def dragEnterEventGraph(ev):
  ev.acceptProposedAction()
  ev.accept()


def dragMoveEventGraph(ev):
  ev.acceptProposedAction()
  ev.accept()


class TableManager():
  
  def __init__(self, app):
    self.app = app
    self.tableItems = []
    self.app.tableWidget.dropEvent = self.dropEvent

  def dropEvent(self, ev):
    ev.acceptProposedAction()
    ev.accept()
    self.addParameter()
    
  def addParameter(self):
    # list holding the item name and the row [name, row]
    for item in self.app.treeWidget.selectedItems() :
      self.app.tableWidget.insertRow(self.app.tableWidget.rowCount())
      self.tableItems.append([str(item.data(0, QtCore.Qt.UserRole)), self.app.tableWidget.rowCount()-1])
    self.app.startDataCollection()
      
  def updateTable(self, data):
    for parameter in self.tableItems:
      item = QtWidgets.QTableWidgetItem()
      item.setText(parameter[0])
      self.app.tableWidget.setItem(parameter[1],0, item)
      item = QtWidgets.QTableWidgetItem()
      if len(data[parameter[0]][0]) == 1:
        item.setText(str(data[parameter[0]][1][0]))
      else:
        item.setForeground(QtGui.QBrush(QtGui.QColor("#48ba0b")))
        item.setText("µ="+"%.3f" % data[parameter[0]][1].mean() + " σ=" + "%.3f" % data[parameter[0]][1].std())
      self.app.tableWidget.setItem(parameter[1],1, item)
      
  def removeRows(self, rows):
    # sort and start deleting the last row first to ensure the remaining row numbers are correct!
    rows.sort(reverse=True)
    for row in rows:
      self.app.tableWidget.removeRow(row)

class PlotManager():

  def __init__(self, app):
    self.app = app
    self.legend = None
    self.plot = pg.PlotWidget()
    self.plot.setAcceptDrops(True)
    self.plot.dropEvent = self.dropEvent
    self.plot.dragEnterEvent = dragEnterEventGraph
    self.plot.dragMoveEvent = dragMoveEventGraph
    self.plotItems = []
    self.axis = DateAxisItem(plotItem=self.plot.getPlotItem(), orientation='bottom')
    self.axis.hide()
    
  def setup(self, isTimeAxis = False):
    if isTimeAxis == True:
      self.axis.attachToPlotItem()
    else:
      self.axis.detachFromPlotItem()

  def putGraph(self):
    self.plotItems = []
#     isTrace = None
    for item in self.app.treeWidget.selectedItems() :
      self.plotItems.append(str(item.data(0, QtCore.Qt.UserRole)))
    self.app.startDataCollection()

  def dropEvent(self, ev):
    ev.acceptProposedAction()
    ev.accept()
    self.putGraph()
      
  def updatePlot(self, data):
    # reset the plot and remove legend and title
    self.plot.clear()
    self.plot.setTitle("")
    if self.legend != None:
      self.plot.scene().removeItem(self.legend)
    # add legend if multiple plot entries are present
    if len(self.plotItems) > 1:
      self.legend = self.plot.addLegend()
    penIndex = 0
    # loop over plot entries
    for item in self.plotItems :
      self.app.setStatusBarMsg("Updating" + item + " data..." )
      myPen = pg.mkPen(penIndex,len(self.plotItems))
      penIndex = penIndex + 1
      if len(self.plotItems) == 1:
        self.plot.setTitle(item)
      if self.app.chainCombo.currentIndex() == 0 and len(data[item][0]) > 1:
        self.setup(False)
      else:
        self.setup(True)
      if(len(data[item][0]) == 1):
        curve = self.plot.plot(pen=myPen, name=item, symbol='o')
      else:
        curve = self.plot.plot(pen=myPen, name=item)
#       logging.debug("Data length: {}, Data-x: {}, Data-y: {}".format(len(data[item][0]),data[item][0],data[item][1]))
      curve.setData(data[item][0],data[item][1])
      self.app.setStatusBarMsg("")


class HDF5Viewer(QtGui.QMainWindow, Ui_MainWindow):
  
  def updateEvent(self, event):
    # obtain new event number
    self.iCurrentEvent = event
    
    # If an event was set using the event spin box setting the setting the slider position at this point would signal another updateEvent
    # block signals from the slider at this point and just update the position 
    self.horizontalSlider.blockSignals(True)
    self.horizontalSlider.setSliderPosition(event)
    self.horizontalSlider.blockSignals(False)
    
    self.setStatusBarMsg("Updating plots ...",'info')
    # update all plots
#     for i in range(0, self.nPlots):
#       self.plotManagers[i].updatePlot()
      
    self.setStatusBarMsg("Updating tables ...", 'info')
    #update table
#     self.tableManager.updateTable()
    self.startDataCollection()
    
    # update status bar
    if self.chainCombo.currentIndex() == 0:
      # find corresponding top-level directory name
      timesString = self.worker.getTimeString(event)
      self.setStatusBarMsg(timesString)
      self.tableWidget.setToolTip("For arrays the mean and standard deviation is shown")
    elif self.chainCombo.currentIndex() == 1:
      self.setStatusBarMsg("Event cluster: " + str(event) + "/" +  str(math.ceil(self.nEvents/self.spinChainEvents.value())-1))
    else:
      self.setStatusBarMsg("All events are considered")
    
  def sliderMoved(self):
    # obtain new event number
    if not self.worker.isRunning():
      self.spinEvent.setValue(self.horizontalSlider.value())
    else:
      logging.debug("Worker is busy.")

  def buildVariableTree(self, parentFileItem, parentTreeItem, path):
    # iterate over sub-items
    for name in parentFileItem:
    
      newPath = path + "/" + name
      # print("adding item: "+ newPath)
    
      # create tree item
      entry = QtGui.QTreeWidgetItem(parentTreeItem)
      entry.setText(0, name)
      entry.setData(0, QtCore.Qt.UserRole, newPath)
      
      
      # recurse into sub-items, if class is group
      if parentFileItem.get(name, getclass=True) == h5py._hl.group.Group:
        self.buildVariableTree(parentFileItem[name], entry, newPath)
      else:
        #check if array and choose different text color
        if(parentFileItem.get(name).shape[0] == 1):
          entry.setForeground(0,QtGui.QBrush(QtGui.QColor("#0a3cba"))) #blue
        else:
          entry.setForeground(0,QtGui.QBrush(QtGui.QColor("#48ba0b"))) #green
            
  def openTreeContextMenu(self, position):
    menu = QtGui.QMenu()
    for i in range(0, self.nPlots):
      menu.addAction("Put to plot (" + str(i % 3) + "," + str(int(i / 3)) + ")", lambda: self.plotManagers[i].putGraph()) 
    menu.addAction("Add to table", lambda: self.tableManager.addParameter())
    menu.addAction("Use as trigger", lambda: self.setTrigger())
    menu.exec_(self.treeWidget.viewport().mapToGlobal(position))
    
  def openTableContextMenu(self, position):
    menu = QtGui.QMenu()
    rows = []
    for item in self.tableWidget.selectedItems():
      rows.append(self.tableWidget.row(item))
      
    menu.addAction("Remove selected rows", lambda: self.tableManager.removeRows(rows))
    menu.exec_(self.tableWidget.viewport().mapToGlobal(position))
  
  def updateRange(self):
    # set slider range
    if self.chainCombo.currentIndex() == 0 or self.chainCombo.currentIndex() == 3:
      self.horizontalSlider.setRange(0, self.worker.getNumberOfEvents() -1)
      self.tableWidget.setToolTip("The mean over all considered events is shown. In case of arrays only the specified " 
      "array position (index) is considered for the mean calculation.")
    else:
      self.horizontalSlider.setEnabled(True)
      if self.chainCombo.currentIndex() == 1:
        self.horizontalSlider.setRange(0, math.ceil(self.worker.getNumberOfEvents()/self.spinChainEvents.value())-1)
      elif self.chainCombo.currentIndex() == 2:
        self.horizontalSlider.setRange(self.timeRange[0], self.timeRange[1])
    # enable slider if makes sense
    if self.chainCombo.currentIndex() == 0 or self.chainCombo.currentIndex() == 1:
      self.horizontalSlider.setEnabled(True)
    else:
      self.horizontalSlider.setEnabled(False)

    # enable array options and trigger related settings if not no chain
    if self.chainCombo.currentIndex() == 0:
      self.eventArrayCombo.setEnabled(False)
      self.eventArrayCombo.blockSignals(True)
      self.eventArrayCombo.setCurrentIndex(0)
      self.eventArrayCombo.blockSignals(False)
      self.spinArrayPosition.setEnabled(False)
      self.bNextTrigger.setEnabled(True)
      self.bPreviousTrigger.setEnabled(True)
      self.spinDecimation.setEnabled(False)

    else:
      self.eventArrayCombo.setEnabled(True)
      self.bNextTrigger.setEnabled(False)
      self.bPreviousTrigger.setEnabled(False)
      self.spinDecimation.setEnabled(True)

    # Events are chained
    if self.chainCombo.currentIndex() == 1:
      self.spinChainEvents.setEnabled(True)
      self.tableWidget.setToolTip("The mean over all considered events is shown. In case of arrays only the specified " 
      "index is considered for the mean calculation.")
    else:
      self.spinChainEvents.setEnabled(False)
    
    # Enable date range setting   
    if self.chainCombo.currentIndex() == 2:
      self.dateFirst.setEnabled(True)
      self.dateLast.setEnabled(True)
      self.bPlot.setEnabled(True)
    else:
      self.dateFirst.setEnabled(False)
      self.dateLast.setEnabled(False)
      self.bPlot.setEnabled(False)
      
    # Enable spin box if not all or time range is selected
    if self.chainCombo.currentIndex() >1:
      self.spinEvent.setEnabled(False)
    else:
      self.spinEvent.setEnabled(True)

    self.spinEvent.setMaximum(self.horizontalSlider.maximum())
      
    if self.chainCombo.currentIndex() != 2:
      self.spinEvent.blockSignals(True)
      self.spinEvent.setValue(0)
      self.spinEvent.blockSignals(False)
      self.updateEvent(0)
    else:
      if self.rangeIsSet == True:
        self.updateEvent(self.timeRange[0])
      else:
        self.setStatusBarMsg("Set time range to be plotted and press plot.", 'info')
    self.progressBar.setValue(0)
  
  def chainComboChanged(self, option):
    self.updateRange()

  @staticmethod   
  def rotate(l, n):
    '''
    Rotate the given list l by n steps:
    l = [0,1,2,3,4,5]
    rotate(l,2) -> [2,3,4,5,0,1]
    '''
    return l[n:] + l[:n] 

  
  def setTimeRange(self, event, isFirst):
    '''
    Set the time range indicator and internal time range (event number)
    @param event: The event to be used for the time range
    @param isFirst: If True the first event of the time range is set. Else the last is set.
    '''
    t = QtCore.QDateTime.fromString(self.worker.getTimeString(event),"yyyy-MM-dd HH:mm:ss.z")
    if isFirst == True:
      self.timeRange[0] = event
      self.dateFirst.setDateTime(t)
    else:
      self.timeRange[1] = event
      self.dateLast.setDateTime(t)
      
  def dateToPlotRange(self):
    '''
    Find the events fitting into the date range set by the user.
    '''
    if self.rangeIsSet == False:
      self.setStatusBarMsg("Updating range ...")
      
      tStart = self.dateFirst.dateTime()
      tEnd = self.dateLast.dateTime()
      if tStart >= tEnd:
        self.setStatusBarMsg("Fix the selected range!",'error')
        return
      last = 0
      lastQt = None
      found = None
      for event in range(self.nEvents):
        tqt = QtCore.QDateTime.fromString(self.worker.getTimeString(event),"yyyy-MM-dd HH:mm:ss.z")
        if event == 0:
          lastQt = tqt
        elif lastQt >= tqt:
          self.setStatusBarMsg("Files are not sortet by time stamps. Consider using --sortByTimeStamp option!", 'error')
          return
        if found == None and tqt >= tStart:
          self.timeRange[0] = last
          self.dateFirst.setDateTime(lastQt)
          found = True
        last = event
        lastQt = tqt
        if tqt >= tEnd:
          self.timeRange[1] = event
          self.dateLast.setDateTime(tqt)
          break 
      self.rangeIsSet = True
   
    self.updateEvent(self.timeRange[0])
  
      
  def userSetDate(self,date):
    self.rangeIsSet = False

  def setStatusBarMsg(self, msg, level = 'status'):
    '''
    Print message in the status bar.
    @param msg: Message to be shown.
    @param level:  Level to be used. Available are: error (red), status (black), info (green)
    '''
    if level == 'error':
      self.statusbar.setStyleSheet("QStatusBar{padding-left:8px;background:rgba(255,0,0,255);color:black;font-weight:bold;}")
    elif level == 'info':
      self.statusbar.setStyleSheet("QStatusBar{padding-left:8px;background:rgba(0,204,0,255);color:black;font-weight:bold;}")
    else:
      self.statusbar.setStyleSheet("QStatusBar{padding-left:8px;background:rgba(255,0,0,0);color:black;font-weight:normal;}")
    self.statusbar.showMessage(str(msg))
  
  def startDataCollection(self):
    eventRange = (self.horizontalSlider.minimum(),self.horizontalSlider.maximum())
    if self.chainCombo.currentIndex() == 0:
      eventRange = (self.horizontalSlider.value(),self.horizontalSlider.value()+1)
    elif self.chainCombo.currentIndex() == 1:
      eventRange = (self.horizontalSlider.value()*self.spinChainEvents.value(),self.horizontalSlider.value()*self.spinChainEvents.value()+self.spinChainEvents.value())
    elif self.chainCombo.currentIndex() == 2:
      eventRange = (self.timeRange[0],self.timeRange[1])  
    logging.debug("Data collection is called with event range {} - {}".format(eventRange[0], eventRange[1]))
    items = set()
    for plot in self.plotManagers:
      items.update(plot.plotItems)
    tableItems = [item[0] for item in self.tableManager.tableItems]
    items.update(tableItems)
    
    arrayPosition = self.spinArrayPosition.value()
    if(self.spinArrayPosition.isEnabled() == False):
      arrayPosition = -1*self.eventArrayCombo.currentIndex() -1
      logging.debug("Using array property: " + str(arrayPosition))
    else:
      logging.debug("Using array position: " + str(arrayPosition))
    if len(items) > 0:
      self.bStop.setEnabled(True)
      if self.chainCombo.currentIndex() == 0:
        isSingleEvent = True
      else:
        isSingleEvent = False
      self.worker.prepareDataCollection(eventRange, arrayPosition, isSingleEvent, items,self.spinChainEvents.value(), self.spinDecimation.value())
      self.worker.start()
    
  def updateData(self):
    logging.debug("Updating data in plots.")
    self.bStop.setEnabled(False)
    for plot in self.plotManagers:
      plot.updatePlot(self.worker.data)
    self.tableManager.updateTable(self.worker.data)
  
  def getTriggerArrayPos(self):
    if self.arrayPos.isEnabled():
      logging.debug("Using array position: " + str(self.arrayPos.value()))
      return self.arrayPos.value()
    else:
      pos = -1*self.triggerArrayCombo.currentIndex() -1
      logging.debug("Using array property: " + str(pos))
      return pos
  
  def startTriggerSearchNext(self):
    if not self.worker.isRunning():
      self.bStop.setEnabled(True)
      self.worker.prepareTrigger(self, self.spinEvent.value(), True, self.triggerOperator.currentText(),self.triggerValue.value(),self.getTriggerArrayPos())
      self.worker.start()
    else:
      self.setStatusBarMsg("Wroker is busy.", 'error')
  
  def startTriggerSearchPrevious(self):
    if not self.worker.isRunning():
      self.bStop.setEnabled(True)
      self.worker.prepareTrigger(self, self.spinEvent.value(), False, self.triggerOperator.currentText(),self.triggerValue.value(),self.getTriggerArrayPos())
      self.worker.start()
    else:
      self.setStatusBarMsg("Wroker is busy.", 'error')
    
  def handleTrigger(self, triggeredEvent):
    self.horizontalSlider.setSliderPosition(triggeredEvent)
    self.bStop.setEnabled(False)

  def dropTriggerEvent(self,ev):
    ev.acceptProposedAction()
    ev.accept()
    self.setTrigger()

    
  def setTrigger(self):
    for item in self.treeWidget.selectedItems() :
      self.triggerSource.setText(str(item.data(0, QtCore.Qt.UserRole)))
      self.worker.trigger.source = str(item.data(0, QtCore.Qt.UserRole))
      if item.foreground(0).color().name() == "#0a3cba":
        self.triggerArrayCombo.setEnabled(False)
        self.worker.trigger.isTrace = False
      else:
        self.triggerArrayCombo.setEnabled(True)
        self.worker.trigger.isTrace = True
      break

  def fillData(self):
    return
  
  def stopWorker(self):
    self.worker.stop = True

  def updateTriggerArrayPosition(self):
    if self.triggerArrayCombo.currentIndex() == 4:
      self.arrayPos.setEnabled(True)
    else:
      self.arrayPos.setEnabled(False)
    
  def updateEventArrayPosition(self):
    if self.eventArrayCombo.currentIndex() == 3:
      self.spinArrayPosition.setEnabled(True)
    else:
      self.spinArrayPosition.setEnabled(False)
    self.updateRange()
    
  def setDebugging(self, enable = True):
    logger = logging.getLogger()
    if enable:
      logger.setLevel(logging.DEBUG)
    else:
      logger.setLevel(logging.INFO)
    
  def __init__(self, args, parent=None):
    super(HDF5Viewer, self).__init__(parent)
    self.setupUi(self)
    
    if len(args.matchString) == 0:
      args.matchString = [""]
      
    # check if path ends with '/'
    if(len(args.path[0]) != 0):
      if(args.path[0].endswith('/') == False):
        args.path[0] = args.path[0] + '/'
        logging.debug("Add missing slash to the path string. New string is: " + args.path[0])
      
    
    # open all data*.h5 files in current directory
    self.listOfFiles = []

    self.timeRange = [0,0]
    self.rangeIsSet = False

    tmpList = []
    startIndex = 0
    for match in args.matchString:
      for filename in glob.glob(args.path[0] + "*" + match + "*.h5"):
        try:
          # new file name style
          tmpList.append((int(filename[filename.rfind("buffer")+6:filename.rfind(".")]),filename))
        except ValueError:
          # old file name style
          tmpList.append((int(filename[filename.rfind("data")+4:filename.rfind(".")]),filename))

    if args.sortByName == True:
      #Sort and shrink before opening files...
      tmpList.sort()
      try:
        with open(args.path[0] + 'currentBuffer') as bufferFile:
          currentBuffer = int(next(bufferFile).split()[0])
      except FileNotFoundError as e:
        print("The currentBuffer file is missing in the given path. Try using no sort or sortByTimeStamp")
        sys.exit()
      tmpList = HDF5Viewer.rotate(tmpList, currentBuffer)
      if args.maxFiles != None and args.maxFiles <= len(tmpList):
        startIndex = len(tmpList) - args.maxFiles
      
    for f in tmpList[startIndex:]:
      self.listOfFiles.append(f[1])

    # make sure at least one file found
    if len(self.listOfFiles) == 0:
      logging.error("No files found in current directory.")
      sys.exit(1)

    self.worker = worker(self, files = self.listOfFiles, sortByTimeStamp = args.sortByTimeStamp, maxFiles = args.maxFiles)
    self.nPlots = args.nPlots
    if self.nPlots <= 2 or self.nPlots == 4:
      nMax = 2
    else:
      nMax = 3
    # add graph widgets
    self.plotManagers = []
    for i in range(0, self.nPlots):
      self.plotManagers.append(PlotManager(self))
      self.gridLayout.addWidget(self.plotManagers[i].plot, i % nMax, i / nMax)
      
    # enable context menu in tree widget
    self.treeWidget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
    self.treeWidget.customContextMenuRequested.connect(self.openTreeContextMenu)

    # loop over first data entry to find the variable tree
    for toplevel in self.worker.files[0]:
      self.buildVariableTree(self.worker.files[0][toplevel], self.treeWidget, "")
      break

    # count total number of events and build event list
    self.nEvents = self.worker.getNumberOfEvents()
    self.spinNEvents.setValue(self.nEvents)
    self.spinChainEvents.setValue(10)
    # configure slider
    self.horizontalSlider.setRange(0, self.nEvents - 1)
    self.horizontalSlider.setSingleStep(1)
    self.horizontalSlider.valueChanged.connect(self.sliderMoved)
    self.horizontalSlider.rangeChanged.connect(self.sliderMoved)
    # set initial time range
    self.setTimeRange(0, True)
    self.setTimeRange(self.nEvents - 1, False)
    
    # enable context menu in tree widget
    self.tableWidget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
    self.tableWidget.customContextMenuRequested.connect(self.openTableContextMenu)
    
    self.tableManager = TableManager(self)
    self.bNextTrigger.clicked.connect(self.startTriggerSearchNext)
    self.bPreviousTrigger.clicked.connect(self.startTriggerSearchPrevious)
    self.chainCombo.currentIndexChanged.connect(self.updateRange)
    self.spinChainEvents.valueChanged.connect(self.updateRange)
    self.spinArrayPosition.valueChanged.connect(self.updateRange)
    self.spinDecimation.editingFinished.connect(self.updateRange)
    
    self.triggerArrayCombo.currentIndexChanged.connect(self.updateTriggerArrayPosition)
    self.eventArrayCombo.currentIndexChanged.connect(self.updateEventArrayPosition)
    
    self.spinEvent.valueChanged.connect(self.updateEvent)
    self.spinEvent.setMaximum(self.horizontalSlider.maximum())
    
    self.dateFirst.setCalendarPopup(True)
    self.dateLast.setCalendarPopup(True)
    
    t1 = QtCore.QDateTime.fromString(self.worker.getTimeString(0),"yyyy-MM-dd HH:mm:ss.z")
    t2 = QtCore.QDateTime.fromString(self.worker.getTimeString(-1),"yyyy-MM-dd HH:mm:ss.z")
    self.dateFirst.setMinimumDateTime(t1)
    self.dateFirst.setMaximumDateTime(t2)
    self.dateLast.setMinimumDateTime(t1)
    self.dateLast.setMaximumDateTime(t2)
    self.dateFirst.setDateTime(t1)
    self.dateLast.setDateTime(t2)
    self.rangeIsSet = True
    self.timeRange = [0,self.nEvents]
    
    self.dateFirst.dateTimeChanged.connect(self.userSetDate)
    self.dateLast.dateTimeChanged.connect(self.userSetDate)
    self.bPlot.clicked.connect(self.dateToPlotRange)
    
    self.triggerSource.dropEvent = self.dropTriggerEvent
    self.worker.triggerResult.connect(self.handleTrigger)
    self.progressBar.setValue(0)
    self.progressBar.setEnabled(True)
    self.bStop.clicked.connect(self.stopWorker)
    self.worker.percentage.connect(self.progressBar.setValue)
    self.worker.updated.connect(self.updateData)
    
    # Not used with HDF5
    self.simpleSearch.setEnabled(False)
   
    # call sliderMoved once to update everything
    self.updateEvent(0)
    
    #connect debug option
    self.actionEnableDebugging.triggered.connect(self.setDebugging)
