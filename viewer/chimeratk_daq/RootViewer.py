#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys
import glob, os
import numpy
import math
import datetime

import argparse
import logging

from PyQt5 import QtGui
from PyQt5 import QtCore
from PyQt5 import QtWidgets

import pyqtgraph as pg

from chimeratk_daq.TimeXAxis import DateAxisItem, getDateString

## Switch to using white background and black foreground
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')
pg.setConfigOption('leftButtonPan', False)

import h5py
from chimeratk_daq.MicroDAQviewerUI import Ui_MainWindow 

from chimeratk_daq.RootWorker import worker

import ROOT

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
    for parameter in self.tableItems:    
      self.app.worker.pvSet.insert(parameter[0])
    
    self.app.startDataCollection(self.app.worker.pvSet)
      
  def updateTable(self, treeData):
    for parameter in self.tableItems:
      item = QtWidgets.QTableWidgetItem()
      item.setText(parameter[0])
      self.app.tableWidget.setItem(parameter[1],0, item)
      item = QtWidgets.QTableWidgetItem()
      if treeData[parameter[0]].x.size() > 1:
        arr = numpy.asanyarray(list(treeData[parameter[0]].y), dtype = numpy.float32)
        item.setForeground(QtGui.QBrush(QtGui.QColor("#48ba0b")))
        item.setText("µ="+"%.3f" % arr.mean() + " σ=" + "%.3f" % arr.std())
      else:
        item.setText(str(treeData[parameter[0]].y.at(0)))
      self.app.tableWidget.setItem(parameter[1],1, item)
      
  def removeRows(self, rows):
    # sort and start deleting the last row first to ensure the remaining row numbers are correct!
    rows.sort(reverse=True)
    for row in rows:
      # remove row
      self.app.tableWidget.removeRow(row)
      # remove parameter
      self.tableItems.remove(list(filter(lambda x: x[1] == row, self.tableItems))[0])

class PlotManager():

  def __init__(self, app):
    self.app = app
    self.legend = None
    self.plotItems = []    
    self.plot = pg.PlotWidget()
    self.plot.setAcceptDrops(True)
    self.plot.dropEvent = self.dropEvent
    self.plot.dragEnterEvent = dragEnterEventGraph
    self.plot.dragMoveEvent = dragMoveEventGraph
    self.axis = DateAxisItem(plotItem=self.plot.getPlotItem(), orientation='bottom')
    self.axis.hide()
    

  def setup(self, isTimeAxis = False):
    if isTimeAxis == True:
      self.axis.attachToPlotItem()
    else:
      self.axis.detachFromPlotItem()

  def putGraph(self):
    self.plotItems = []
    isTrace = None
    for item in self.app.treeWidget.selectedItems() :
      self.plotItems.append(str(item.data(0, QtCore.Qt.UserRole)))
      # add pv to the exsisting pvs
      self.app.worker.pvSet.insert(self.plotItems[-1])
      if isTrace == None:
        isTrace = self.app.worker.isTrace(self.plotItems[-1])
      elif isTrace != self.app.worker.isTrace(self.plotItems[-1]):
        logging.warning("You added traces and scalars to a plot.")
        self.app.setStatusBarMsg("You added traces and scalars to a plot. That does not work.!",'error')
        break
    # now call worker
    # @remark If only adding the new pvs from this graph only the corresponding data will be read
    # -> plots/table with other pvs would vanish after worker is finished and calls updateData
    self.app.startDataCollection(self.app.worker.pvSet)

  def dropEvent(self, ev):
    ev.acceptProposedAction()
    ev.accept()
    self.putGraph()
      
  def updatePlot(self, treeData):
    # reset the plot and remove legend and title
    self.plot.clear()
    self.plot.setTitle("")
    if self.legend != None:
      self.plot.scene().removeItem(self.legend)
    # add legend if multiple plot entries are present
    if len(self.plotItems) > 1:
      self.legend = self.plot.addLegend()
    penIndex = 0
    isTrace = False
    isScalar = False
    # loop over plot entries
    for item in self.plotItems :
      self.app.setStatusBarMsg("Updating" + item + " data..." )
      if treeData[item].x.size() != treeData[item].y.size():
        logging.error("Array length not matching-> x: " + str(treeData[item].x.size()) + " y: " + str(treeData[item].y.size()))
        continue
      myPen = pg.mkPen(penIndex,len(self.plotItems))
      penIndex = penIndex + 1
      if len(self.plotItems) == 1:
        self.plot.setTitle(item)
      if treeData[item].x.size() > 1:
        isTrace = True
      else:
        isScalar = True
      if (self.app.chainCombo.currentIndex() == 0 and treeData[item].x.size() > 1):
        # don't use time axis if plotting a trace
        self.setup(False)
      else:
        self.setup(True)
      curve = None
      if (treeData[item].x.size() == 1):
        curve = self.plot.plot(pen=myPen, name=item, symbol='o')
      else :
        curve = self.plot.plot(pen=myPen, name=item)
      curve.setData(list(treeData[item].x), list(treeData[item].y))
      axis = self.plot.getPlotItem().axes['bottom']['item']
      
      if (self.app.worker.isLLRFData and self.app.chainCombo.currentIndex() == 0):
        # add time information if plotting llrf trace
        timestr =  getDateString(self.app.worker.getTimeStamp(self.app.currentEvent))
        axis.setLabel("Time relative to t0=" + timestr + " [s]")
      elif (not self.app.worker.isLLRFData and self.app.chainCombo.currentIndex() == 0):
        axis.setLabel("index")
      else:
        axis.setLabel("date")
      self.app.setStatusBarMsg("")
    if isScalar == True and isTrace == True:
      logging.warning("You added traces and scalars to a plot.")
      self.app.setStatusBarMsg("You added traces and scalars to a plot. This might lead to visualization problems with 'No Chain' option!",'error')

class errorPopup(QtWidgets.QWidget):
    def __init__(self, name):
        super().__init__()

        self.name = name

        self.initUI()

    def initUI(self):
        lblName = QtWidgets.QLabel(self.name, self)

class Trigger():
  '''
  The trigger class is used to implement a trigger that can be used to find a 
  specific data set fullfilling the trigger condition.
  Three inputs are required:
  - Trigger source: The item from the item list to trigger on
  - Trigger operator: Choose a certain trigger condition operator
  - Trigger level: Choose the trigger level
  
  To use the trigger connect on_click_next and on_click_previous.
  The apps slider will be moved to the triggered event. If no event fullfills the 
  trigger condition the slider is reset to the initial position.
  '''
  def __init__(self, app):
    self.app = app
    self.source = self.app.triggerSource
    self.source.dropEvent = self.dropEvent

  def dropEvent(self, ev):
    ev.acceptProposedAction()
    ev.accept()
    print("Dropped event")
    
  def setTrigger(self):
    for item in self.app.treeWidget.selectedItems() :
      self.source.setText(str(item.data(0, QtCore.Qt.UserRole)))
    if self.app.worker.isTrace(self.source.text()) == False:
      self.app.arrayPos.setValue(0)
      self.app.triggerArrayCombo.setEnabled(False)
      self.app.arrayPos.setEnabled(False)
    else:
      self.app.triggerArrayCombo.setEnabled(True)


  def on_click_next(self):
    if self.app.currentEvent != self.app.nEvents:
      self.startSearch(True)
    else:
      logging.error("Can not search for next triggger!")
  def on_click_prev(self):
    if self.app.currentEvent != 0:
      self.startSearch(False)
    else:
      logging.error("Can not search for previous triggger!")    
  def startSearch(self, findNext):
    if not self.source.text():
      self.app.setStatusBarMsg("No trigger source set! \n Please choose a source by adding one from the item list and use right click context menu...", 'error')
    else:
      self.app.setStatusBarMsg("Trigger search in progress...be patient!", 'info')
      currentEvent = self.app.horizontalSlider.value()
      triggeredEvent = -1
      
      pos = 0
      if self.app.triggerArrayCombo.isEnabled():
        pos = self.app.arrayPos.value()
        if self.app.arrayPos.isEnabled() == False:
          pos = -1*self.app.triggerArrayCombo.currentIndex() -1
          logging.debug("Using array property: " + str(pos))
        else:
          logging.debug("Using array position: " + str(pos))
      
      self.app.worker.prepareTriggerSearch(triggerPV=self.source.text(), currentEvent=currentEvent,  
                                           triggerThreshold=self.app.triggerValue.value(), operator=self.app.triggerOperator.currentText(), 
                                           arrayPosition=pos, 
                                           findNext=findNext,
                                           simpleSearch=self.app.simpleSearch.isChecked())
      self.app.worker.start()
      self.app.bStop.setEnabled(True)
      self.app.progressBar.setEnabled(True)
      
  def handleTrigger(self, triggeredEvent):
      if triggeredEvent < self.app.horizontalSlider.minimum() or triggeredEvent > self.app.horizontalSlider.maximum():
        self.app.horizontalSlider.setSliderPosition(self.app.currentEvent)
        self.app.setStatusBarMsg("Triggered on an event that is out of range: " + str(triggeredEvent), 'error')
      elif triggeredEvent >= 0:
        self.app.horizontalSlider.setSliderPosition(triggeredEvent)
      else:
        self.app.horizontalSlider.setSliderPosition(self.app.currentEvent)
      if triggeredEvent == -1:
        self.app.setStatusBarMsg("No trigged event found!")
      else:
        self.app.setStatusBarMsg("Trigged event is: " + str(triggeredEvent))
        self.app.setStatusBarMsg("Found triggered event: " + str(triggeredEvent))
      self.app.bStop.setEnabled(False)
      self.app.progressBar.setEnabled(False)


class RootViewer(QtWidgets.QMainWindow, Ui_MainWindow):
  EXIT_CODE_REBOOT = -123
  def startDataCollection(self, pvSet):
    ''' 
    Start reading data for the given set of process variables.
    The number of events and event selection is done in dependence of the current
    user option.
    The data collection is done by the worker thread. The GUI will be updated by updateData
    if the worker finished.
    '''
    if self.worker.isRunning():
      logging.info("Skipped update since another update is running...")
      return
    if(pvSet.size() != 0):
      self.bStop.setEnabled(True)
      arrayPosition = self.spinArrayPosition.value()
      if(self.spinArrayPosition.isEnabled() == False):
        arrayPosition = -1*self.eventArrayCombo.currentIndex() -1
        logging.debug("Using array property: " + str(arrayPosition))
      else:
        logging.debug("Using array position: " + str(arrayPosition))
      if self.chainCombo.currentIndex() == 0 and pvSet.size() != 0:
        self.worker.prepareWorker(nEvents=1, pvs=pvSet, type=0, currentEvent=self.horizontalSlider.value())
      elif self.chainCombo.currentIndex() == 1 and pvSet.size() != 0:
        self.worker.prepareWorker(nEvents=self.spinChainEvents.value(), pvs=pvSet, currentEvent=self.horizontalSlider.value(), 
                                  type=1, arrayPosition=arrayPosition, decimation=self.spinDecimation.value())
      elif self.chainCombo.currentIndex() == 2 and pvSet.size() != 0:
        self.worker.prepareWorker(nEvents=(self.timeRange[1]-self.timeRange[0]), pvs=pvSet, currentEvent=self.horizontalSlider.value(), 
                                  type=2, arrayPosition=arrayPosition, decimation=self.spinDecimation.value())
      else:
        self.worker.prepareWorker(nEvents=self.nEvents, pvs=pvSet, currentEvent=0, 
                                  type=3, arrayPosition=arrayPosition, decimation=self.spinDecimation.value())
      self.progressBar.setValue(0)
      self.worker.start()
    
  def updateData(self):
    '''
    This is called when the worker is finished and new data is available.
    '''
    self.setStatusBarMsg("Updating plots ...",'info')
    # update all plots
    for i in range(0, self.nPlots):
      self.plotManagers[i].updatePlot(self.worker.data)
    
    self.setStatusBarMsg("Updating tables ...", 'info')
    #update table
    self.tableManager.updateTable(self.worker.data)

    # update status bar
    if self.chainCombo.currentIndex() == 0:
      self.tableWidget.setToolTip("For arrays the mean and standard deviation is shown")
      self.setStatusBarMsg("Event: " + str(self.currentEvent) + "/" +  str(self.nEvents - 1) + "\t" + getDateString(self.worker.getTimeStamp(self.currentEvent)))
    elif self.chainCombo.currentIndex() == 1:
      self.setStatusBarMsg("Event cluster: " + str(self.currentEvent) + "/" +  str(math.ceil(self.nEvents/self.spinChainEvents.value())-1))
    elif self.chainCombo.currentIndex() == 2:
      self.setStatusBarMsg("Events in the selected range are considered.")
    else:
      self.setStatusBarMsg("All events are considered")

    self.bStop.setEnabled(False)
  
  def updateEvent(self, event):
    self.currentEvent = event
    
    # If an event was set using the event spin box setting the setting the sloder position at this point would signal another updateEvent
    # block signals from the slider at this point and just update the position 
    self.horizontalSlider.blockSignals(True)
    self.horizontalSlider.setSliderPosition(self.currentEvent)
    self.horizontalSlider.blockSignals(False)
    
    self.setStatusBarMsg("Reading data...",'info')
    # gather list of active varibales
    pv = set()
    for i in range(0, self.nPlots):
      pv.update(self.plotManagers[i].plotItems)
      
    for i in self.tableManager.tableItems:
      pv.add(i[0])
    
    pvSet = ROOT.set('std::string')()
    for i in pv:
      pvSet.insert(i)
      
    if pvSet.size() == 0:
      self.setStatusBarMsg("",'status')
    else:  
      self.startDataCollection(pvSet)
      
 
  def sliderMoved(self):
    # obtain new event number
    self.spinEvent.setValue(self.horizontalSlider.value())

  def buildVariableTree(self, parentTreeItem, path):
    # iterate over sub-items
    branch_list = self.worker.getBranchList()
    for i in range(branch_list.size()):
      s = branch_list.at(i)                                               #Probe.Calibration.angle
      if s.find('.') < 0:
        continue                                                          # Ignore timeStamp -> contains no '.'
      path = s[0:s.rfind('.')]                                            #Probe.Calibration
      tmp = ""
      dirItem = parentTreeItem                                            #/
      for d in path.split('.'):
        '''Loop over directories in Path'''
        if tmp == "":
          tmp = tmp + d                                                   #Probe
        else: 
          tmp = tmp + "." + d                                             #Probe.Calibration  
        if tmp not in self.dirs:
          '''Check if directory in path exists and if not create it'''
          entry = QtWidgets.QTreeWidgetItem(dirItem)
          entry.setText(0, d)
          entry.setData(0, QtCore.Qt.UserRole, tmp)
          dirItem = entry
          self.dirs.add(tmp)
          self.dirItems[tmp] = entry
        else:
          dirItem = self.dirItems[tmp]
      
      logging.debug("Adding item: " + s.split('.')[-1] + " with path: " + path)
      entry = QtWidgets.QTreeWidgetItem(self.dirItems[path])
      entry.setText(0, s.split('.')[-1])
      entry.setData(0, QtCore.Qt.UserRole, s)
      if self.worker.isTrace(branch_list.at(i)) == True:
        entry.setForeground(0,QtGui.QBrush(QtGui.QColor("#0a3cba"))) #blue
      else:
        entry.setForeground(0,QtGui.QBrush(QtGui.QColor("#48ba0b"))) #green
      
  def openTreeContextMenu(self, position):
    menu = QtWidgets.QMenu()
    for i in range(self.nPlots):
      menu.addAction("Put to plot (" + str(i % 3) + "," + str(int(i / 3)) + ")", lambda: self.plotManagers[i].putGraph()) 
    menu.addAction("Add to table", lambda: self.tableManager.addParameter())
    menu.addAction("Use as trigger", lambda: self.trigger.setTrigger())
    menu.exec_(self.treeWidget.viewport().mapToGlobal(position))
    
  def openTableContextMenu(self, position):
    menu = QtWidgets.QMenu()
    rows = []
    for item in self.tableWidget.selectedItems():
      rows.append(self.tableWidget.row(item))
      
    menu.addAction("Remove selected rows", lambda: self.tableManager.removeRows(rows))
    menu.exec_(self.tableWidget.viewport().mapToGlobal(position))
  
  def updateRange(self):
    #no chain
    if self.chainCombo.currentIndex() == 0:
      self.eventArrayCombo.setEnabled(False)
      self.eventArrayCombo.blockSignals(True)
      self.eventArrayCombo.setCurrentIndex(0)
      self.eventArrayCombo.blockSignals(False)
      self.spinArrayPosition.setEnabled(False)
      self.bNextTrigger.setEnabled(True)
      self.bPreviousTrigger.setEnabled(True)
      self.progressBar.setEnabled(False)
      self.spinDecimation.setEnabled(False)
    else:
      self.eventArrayCombo.setEnabled(True)
      self.progressBar.setEnabled(True)
      self.bNextTrigger.setEnabled(False)
      self.bPreviousTrigger.setEnabled(False)
      self.spinDecimation.setEnabled(True)
    
    # Events are chained
    if self.chainCombo.currentIndex() == 1:
      self.spinChainEvents.setEnabled(True)
      # Changing the Range does not result in a signal, but if the posiiton is out of the new range it is set to the maximium -> This will result in value 
      # change event and updateEvent would be executed.
      # The correct slider position is set later via calling updateEvent
      self.horizontalSlider.blockSignals(True)
      self.horizontalSlider.setRange(0, math.ceil(self.nEvents/self.spinChainEvents.value())-1)
      self.horizontalSlider.blockSignals(False)
      self.tableWidget.setToolTip("The mean over all considered events is shown. In case of arrays only the specified " 
      "index is considered for the mean calculation.")
    else:
      self.spinChainEvents.setEnabled(False)
      self.horizontalSlider.setRange(0, self.nEvents -1)

    if self.chainCombo.currentIndex() == 2:
      self.dateFirst.setEnabled(True)
      self.dateLast.setEnabled(True)
      self.bPlot.setEnabled(True)
    else:
      self.dateFirst.setEnabled(False)
      self.dateLast.setEnabled(False)
      self.bPlot.setEnabled(False)

    # selected events are considered
    if self.chainCombo.currentIndex() == 2 or self.chainCombo.currentIndex() == 3:
      self.horizontalSlider.setEnabled(False)
      self.tableWidget.setToolTip("The mean over all considered events is shown. In case of arrays only the specified " 
      "array position (index) is considered for the mean calculation.")
      self.spinEvent.setEnabled(False)
    else:
      self.horizontalSlider.setEnabled(True)
      self.spinEvent.setEnabled(True)
      
    if self.chainCombo.currentIndex() != 2:
      self.spinEvent.blockSignals(True)
      self.spinEvent.setValue(0)
      self.spinEvent.setMaximum(self.horizontalSlider.maximum())
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
  
  def dateToPlotRange(self):
    '''
    Find the events fitting into the date range set by the user.
    '''
    if self.rangeIsSet == False:
      self.setStatusBarMsg("Updating range ...")
      
      tStart = self.dateFirst.dateTime()
      tEnd = self.dateLast.dateTime()
      if tStart >= tEnd:
        self.setStatusBarMsg("Fix the selected range!", 'error')
        return
      last = 0
      lastQt = None
      found = None
      for event in range(self.nEvents):
        ts,tms = self.worker.getTimeStamp(event)
        tqt = QtCore.QDateTime.fromMSecsSinceEpoch(ts*1000+tms)
        if event == 0:
          lastQt = tqt
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

  # def setPath(self):
    # name = QtWidgets.QFileDialog.getExistingDirectory(self, 'Set directory', '/home', QtWidgets.QFileDialog.ShowDirsOnly | QtWidgets.QFileDialog.DontResolveSymlinks)
    # logging.info("Add directory: " + name)
  @QtCore.pyqtSlot(bool)  
  def on_actionSet_Data_Path_triggered(self, triggered):
    QtWidgets.qApp.exit( Ui_MainWindow.EXIT_CODE_REBOOT )

  def __init__(self, args, parent=None):
    super(RootViewer, self).__init__(parent)
    self.setupUi(self)
    # set of directory names
    self.dirs = set()
    # dictionary -> dictionary: QtWidgets.QTreeWidgetItem
    self.dirItems = {}
    
    self.timeRange = [0,0]
    self.rangeIsSet = False

    # check if path ends with '/'
    if(args.path.endswith('/') == False):
      args.path = args.path + '/'
      logging.debug("Add missing slash to the path string. New string is: " + args.path)

    self.worker = worker(args)      
    # make sure at least one file found
    if self.worker.getNFiles() == 0:
      logging.error("No files found in current directory.")
      sys.exit(1)
      
    if self.worker.getNBranches() == 0:
      logging.error("No tree in file or tree with no branches.")
      sys.exit(1)
    self.nPlots = args.nPlots
    # add  graph widgets
    self.plotManagers = []
    if self.nPlots <= 2 or self.nPlots == 4:
      nMax = 2
    else:
      nMax = 3
    for i in range(self.nPlots):
      self.plotManagers.append(PlotManager(self))
      self.gridLayout.addWidget(self.plotManagers[i].plot, i % nMax, int(i / nMax))
      
    # enable context menu in tree widget
    self.treeWidget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
    self.treeWidget.customContextMenuRequested.connect(self.openTreeContextMenu)

    self.buildVariableTree(self.treeWidget, "")

    # count total number of events and build event list
    self.nEvents = self.worker.maxEvents
    
    self.spinNEvents.setValue(self.nEvents)
    self.spinChainEvents.setValue(10)
    # configure slider
    self.horizontalSlider.setRange(0, self.nEvents - 1)
    self.horizontalSlider.setSingleStep(1)
    self.horizontalSlider.valueChanged.connect(self.sliderMoved)
    
    # enable context menu in tree widget
    self.tableWidget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
    self.tableWidget.customContextMenuRequested.connect(self.openTableContextMenu)
    
    self.tableManager = TableManager(self)
    self.trigger = Trigger(self)
    self.bNextTrigger.clicked.connect(self.trigger.on_click_next)
    self.bPreviousTrigger.clicked.connect(self.trigger.on_click_prev)
    self.chainCombo.currentIndexChanged.connect(self.updateRange)
    self.spinChainEvents.editingFinished.connect(self.updateRange)
    self.spinArrayPosition.editingFinished.connect(self.updateRange)
    self.spinDecimation.editingFinished.connect(self.updateRange)
    
    self.triggerArrayCombo.currentIndexChanged.connect(self.updateTriggerArrayPosition)
    self.eventArrayCombo.currentIndexChanged.connect(self.updateEventArrayPosition)
    
    self.spinEvent.valueChanged.connect(self.updateEvent)
    self.spinEvent.setMaximum(self.horizontalSlider.maximum())
    
    self.dateFirst.setCalendarPopup(True)
    self.dateLast.setCalendarPopup(True)
    
    (ts,tms) = self.worker.getTimeStamp(0)
    t1 = QtCore.QDateTime.fromMSecsSinceEpoch(int(1000.*ts + tms))
    (ts,tms) = self.worker.getTimeStamp(self.nEvents-1)
    t2 = QtCore.QDateTime.fromMSecsSinceEpoch(int(1000.*ts + tms))
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
    self.bStop.clicked.connect(self.worker.stop)
    self.worker.updated.connect(self.updateData)
    self.worker.triggerResult.connect(self.trigger.handleTrigger)
    self.progressBar.setRange(0,100)
    self.worker.percentage.connect(self.progressBar.setValue)
    # call sliderMoved once to update everything
    self.sliderMoved()
        
    self.updateRange()
   
    #connect debug option
    self.actionEnableDebugging.triggered.connect(self.setDebugging)
    