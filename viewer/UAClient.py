#!/usr/bin/python3
from chimeratk_daq.MicroDAQviewerUI_live import Ui_MainWindow

from PyQt5 import QtWidgets
from PyQt5.QtCore import pyqtSignal, QSettings, QTimer, QObject
from PyQt5.Qt import QApplication, QMainWindow, Qt, QMenu, QColor, QBrush

import pyqtgraph as pg

from uawidgets.tree_widget import TreeWidget
#from mytree_widget import TreeWidget

found_opcua = True
try:
  from uaclient.uaclient import UaClient
  from opcua import ua
except ImportError:
  found_opcua = False

import numpy

import sys
import argparse
import logging.config
from datetime import datetime

from chimeratk_daq.TimeXAxis import DateAxisItem, getDateString

LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'verbose': {
            'format': '[%(levelname)s UAClient] %(asctime)s %(message)s  in %(pathname)s:%(lineno)d'
        },
        'simple': {
            'format': '[%(levelname)s opcua] %(message)s'
        },
    },
    'handlers': {
        'console_client':{
            'level':'DEBUG',
            'class':'logging.StreamHandler',
            'formatter': 'verbose'
        },
        'console_opcua':{
            'level':'DEBUG',
            'class':'logging.StreamHandler',
            'formatter': 'simple'
        },
    },
    'loggers': {
        'uaclient': {
            'handlers': ['console_opcua'],
            'level': 'INFO',
        },
        'UAclient': {
            'handlers': ['console_client'],
            'level': 'INFO',
        },
        'client': {
            'handlers': ['console_opcua'],
            'level': 'INFO',
        }
    }
}

logger_client = logging.getLogger("UAclient")

def dragEnterEventGraph(ev):
  ev.acceptProposedAction()
  ev.accept()


def dragMoveEventGraph(ev):
  ev.acceptProposedAction()
  ev.accept()


class DataChangeHandler(QObject):
  fire = pyqtSignal(object, object, str)
    
  def __init__(self):
    QObject.__init__(self)

  def datachange_notification(self, node, val, data):
      if data.monitored_item.Value.SourceTimestamp:
          timestamp = data.monitored_item.Value.SourceTimestamp.isoformat()
      elif data.monitored_item.Value.ServerTimestamp:
          timestamp = data.monitored_item.Value.ServerTimestamp.isoformat()
      else:
          timestamp = datetime.now().isoformat()
      self.fire.emit(node, val, timestamp)
      
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
    logger_client.info("Adding paramter to the Table.")
    node = self.app.tree_ui.get_current_node()
    if node == None:
      logger_client.warning("No node selected yet. Connect to server first!")
      return
    if node in self.app.nodes:
      logger_client.info("No subscription added since node is already subscribed.")
    else:
      logger_client.info("Adding subscription for " + node.nodeid.Identifier)
      self._subscription = self.app.uaclient.subscribe_datachange(node, self.app.handler)
    # list holding the node and the row [name, row]
    self.app.tableWidget.insertRow(self.app.tableWidget.rowCount())
    self.tableItems.append([node, self.app.tableWidget.rowCount()-1])
    self.app.nodes.append(node)
    self.updateTable(node, None)
      
  def updateTable(self, node, value):
    #\ToDo: Fix filling table for the new server structure
    for parameter in self.tableItems:
      # find row to update
      if node == parameter[0]:
        # set parameter name
        item = QtWidgets.QTableWidgetItem()
        item.setText(parameter[0].nodeid.Identifier)
        self.app.tableWidget.setItem(parameter[1],0, item)
        item = QtWidgets.QTableWidgetItem()
        item.setText(parameter[0].get_variables()[2].get_value())
        self.app.tableWidget.setItem(parameter[1],2, item)

        if value != None:
          item = QtWidgets.QTableWidgetItem()
          if type(value) == list:
            arr = numpy.asanyarray(value, dtype = numpy.float32)
            item.setForeground(QBrush(QColor("#48ba0b")))
            item.setText("µ="+"%.3f" % arr.mean() + " σ=" + "%.3f" % arr.std())
          else:
            item.setText("%.3f" % value)
          self.app.tableWidget.setItem(parameter[1],1, item)
        
  def removeRows(self, rows):
    # sort and start deleting the last row first to ensure the remaining row numbers are correct!
    rows.sort(reverse=True)
    for row in rows:
      for par in self.tableItems:
        if par[1] == row:
          if self.app.nodes.count(par[0]) > 1:
            # do not remove the subscription because of other observers
            logger_client.info("Not removing subscription for " + par[0].nodeid.Identifier)
            self.app.nodes.remove(par[0])
          elif self.app.nodes.count(par[0]) == 1:
            # remove the subscription because this is the only observer
            logger_client.info("Removing subscription for " + par[0].nodeid.Identifier)
            self.app.uaclient.unsubscribe_datachange(par[0])
            self.app.nodes.remove(par[0])
          else:
            logger_client.error("Tried to handle node from PlotManager that was not registered to the GUI!")          
      self.app.tableWidget.removeRow(row)
      self.tableItems.remove(par)
    



class PlotManager():

  def __init__(self, app, plotID):
    self.app = app
    self.ID = plotID
    self.plot = pg.PlotWidget()
    self.plot.setAcceptDrops(True)
    self.plot.dropEvent = self.dropEvent
    self.plot.dragEnterEvent = dragEnterEventGraph
    self.plot.dragMoveEvent = dragMoveEventGraph
    self.plotItems = []
    self.axis = DateAxisItem(plotItem=self.plot.getPlotItem(), orientation='bottom')
    self.axis.hide()
    self.timeAxisActive = False
    self.name = "Plot " + str(self.ID)
    self.node = None


  def putGraph(self):
    logger_client.info("Adding plot to PlotManager: " + self.name)
    self.plot.setTitle("Plot is waiting for DataChange events...")
    node = self.app.tree_ui.get_current_node()
    if node == None:
      logger_client.warning("No node selected yet. Connect to server first!")
      return
    if self.node != None:
      if self.app.nodes.count(self.node) > 1:
        # do not remove the subscription because of other observers
        logger_client.info("Not removing subscription for " + node.nodeid.Identifier)
        self.app.nodes.remove(self.node)
      elif self.app.nodes.count(self.node) == 1:
        # remove the subscription because this is the only observer
        logger_client.info("Removing subscription for " + node.nodeid.Identifier)
        self.app.uaclient.unsubscribe_datachange(self.node)
        self.app.nodes.remove(self.node)
      else:
        logger_client.error("Tried to handle node from PlotManager that was not registered to the GUI!")
    if node in self.app.nodes:
      logger_client.info("No subscription added since node is already subscribed.")
    else:
      logger_client.info("Adding subscription for " + node.nodeid.Identifier)
      self._subscription = self.app.uaclient.subscribe_datachange(node, self.app.handler)
    self.node = node
    #append the node to count the observers
    self.app.nodes.append(self.node)
      

  def dropEvent(self, ev):
    ev.acceptProposedAction()
    ev.accept()
    self.putGraph()
      
  def _update_subscription_model(self, node, value, timestamp):
    logger_client.debug("Subscribed value changed: " + str(value) + " TimeStamp: " + str(timestamp))
    self.plot.clear()
    curve = self.plot.plot()
    self.plot.setTitle(node.nodeid.Identifier)
    # @ToDo: Here we know if it is an array or a scalar -> fill to plot or table
    if type(value) == list:
      # try to read timeStamp array
      timeStampNode = node.nodeid.Identifier.replace("Value","_timeStampsValue")
      try:
        timeStamps = self.app.uaclient.get_node(ua.NodeId(timeStampNode,node.nodeid.NamespaceIndex)).get_value()
        logger_client.debug("Found time stamps for array data of node: " + node.nodeid.Identifier)
        if self.timeAxisActive == False:
          self.axis.attachToPlotItem()
          self.timeAxisActive = True
        # only show values for non zero time stamps
        v1 = numpy.array(timeStamps)
        v2 = numpy.array(value)
        curve.setData(v1[v1 != 0], v2[v1 != 0])
      except:
        logger_client.debug("No time stamps found for array data of node: " + node.nodeid.Identifier)
        if self.timeAxisActive == True:
          self.axis.detachFromPlotItem()
          self.timeAxisActive = False
        curve.setData(range(0, len(value)), value)
    else:
      if self.timeAxisActive == True:
        self.axis.detachFromPlotItem()
        self.timeAxisActive = False
      curve.setData(range(0, 2), [value,value])


class MicroDAQviewer_live(QMainWindow, Ui_MainWindow):
  def _uri_changed(self, uri):
    self.uaclient.load_security_settings(uri)

  def show_error(self, msg):
    self.statusbar.show()
    self.statusbar.setStyleSheet("QStatusBar { background-color : red; color : black; }")
    self.statusbar.showMessage(str(msg))
    QTimer.singleShot(1500, self.statusbar.hide)

  def connect(self):
    uri = self.comboBox.currentText()
    try:
        self.uaclient.connect(uri)
    except Exception as ex:
        self.show_error(ex)
        raise

    self._update_address_list(uri)
    self.tree_ui.set_root_node(self.uaclient.client.get_root_node())
    self.load_current_node()

  def _update_address_list(self, uri):
    if uri == self._address_list[0]:
      return
    if uri in self._address_list:
        self._address_list.remove(uri)
    self._address_list.insert(0, uri)
    if len(self._address_list) > self._address_list_max_count:
        self._address_list.pop(-1)

  def disconnect(self):
    # remove table nodes
    l = []
    for r in self.tableManager.tableItems:
      l.append(r[1])
    self.tableManager.removeRows(l)
    #remove remaining nodes
    for i in set(self.nodes):
      try:
        self.uaclient.unsubscribe_datachange(i)
      except Exception as e:
        logging.warning("Failed to unsubscribe variable: " + i.nodeid.Identifier)
        self.show_error(e)
    self.nodes.clear()

    for p in self.plotManagers:
      p.node = None

    try:
        self.uaclient.disconnect()
    except Exception as ex:
        self.show_error(ex)
        raise
    finally:
        self.save_current_node()
        self.tree_ui.clear()
        #reset handler and uaclient
        self.handler = DataChangeHandler()
        self.uaclient = UaClient()
        self.handler.fire.connect(self.updateNode, type=Qt.QueuedConnection)
          
        
  def save_current_node(self):
    current_node = self.tree_ui.get_current_node()
    if current_node:
      mysettings = self.settings.value("current_node", None)
      if mysettings is None:
          mysettings = {}
      uri = self.comboBox.currentText()
      mysettings[uri] = current_node.nodeid.to_string()
      self.settings.setValue("current_node", mysettings)
      
  def load_current_node(self):
    mysettings = self.settings.value("current_node", None)
    if mysettings is None:
      return
    uri = self.comboBox.currentText()
    if uri in mysettings:
      nodeid = ua.NodeId.from_string(mysettings[uri])
      node = self.uaclient.client.get_node(nodeid)
      self.tree_ui.expand_current_node()
    
  def openTreeContextMenu(self, position):
    menu = QMenu()
    menu.addAction("Put to plot (1,1)", lambda: self.plotManagers[0].putGraph())
    menu.addAction("Put to plot (1,2)", lambda: self.plotManagers[1].putGraph())
    menu.addAction("Put to plot (1,3)", lambda: self.plotManagers[2].putGraph())
    menu.addAction("Put to plot (2,1)", lambda: self.plotManagers[3].putGraph())
    menu.addAction("Put to plot (2,2)", lambda: self.plotManagers[4].putGraph())
    menu.addAction("Put to plot (2,3)", lambda: self.plotManagers[5].putGraph())
    menu.addAction("Put to plot (3,1)", lambda: self.plotManagers[6].putGraph())
    menu.addAction("Put to plot (3,2)", lambda: self.plotManagers[7].putGraph())
    menu.addAction("Put to plot (3,3)", lambda: self.plotManagers[8].putGraph())
    menu.addAction("Add to table", lambda: self.tableManager.addParameter())
    menu.exec_(self.treeView.viewport().mapToGlobal(position))

  def openTableContextMenu(self, position):
    menu = QMenu()
    rows = []
    for item in self.tableWidget.selectedItems():
      rows.append(self.tableWidget.row(item))
      
    menu.addAction("Remove selected rows", lambda: self.tableManager.removeRows(rows))
    menu.exec_(self.tableWidget.viewport().mapToGlobal(position))
        
  def updateNode(self, node, value, timestamp):
    for p in self.plotManagers:
      if node == p.node:
        p._update_subscription_model(node, value, timestamp)
        
    for p in self.tableManager.tableItems:
      if node == p[0]:
        self.tableManager.updateTable(node, value)

  def __init__(self, args, parent=None):
    super(MicroDAQviewer_live, self).__init__(parent)
    self.setupUi(self)

    self.handler = DataChangeHandler()
    self.handler.fire.connect(self.updateNode, type=Qt.QueuedConnection)
    self.nodes = []
    
    self.plotManagers = []
    global signal_counter
    
    self.nPlots = args.nPlots
    # add  graph widgets
    if self.nPlots <= 2 or self.nPlots == 4:
      nMax = 2
    else:
      nMax = 3
    if self.nPlots == 1:
      signal_counter = 0
      self.plotManagers.append(PlotManager(self,0))
      self.gridLayout.addWidget(self.plotManagers[0].plot)
    else:
      for i in range(self.nPlots):
        signal_counter = i
        self.plotManagers.append(PlotManager(self, i))
        self.gridLayout.addWidget(self.plotManagers[i].plot, i % nMax, i / nMax)
        self.plotManagers[i].plot.setTitle("Plot #" + str(i))
    
    self.settings = QSettings()

    self._address_list = self.settings.value("address_list", ["opc.tcp://149.220.224.32:12000", "opc.tcp://149.220.63.187:12000", "opc.tcp://localhost:11000"])
    self._address_list_max_count = int(self.settings.value("address_list_max_count", 10))

    # init widgets
    for addr in self._address_list:
      self.comboBox.insertItem(-1, addr)

    self.uaclient = UaClient()

    
    self.tree_ui = TreeWidget(self.treeView)
    self.comboBox.currentTextChanged.connect(self._uri_changed)
    
    self.connectButton.clicked.connect(self.connect)
    self.disconnectButton.clicked.connect(self.disconnect)
    
    # enable context menu in tree widget
    self.treeView.setContextMenuPolicy(Qt.CustomContextMenu)
    self.treeView.customContextMenuRequested.connect(self.openTreeContextMenu)
    
    # enable context menu in table widget
    self.tableWidget.setContextMenuPolicy(Qt.CustomContextMenu)
    self.tableWidget.customContextMenuRequested.connect(self.openTableContextMenu)
    
    self.actionConnect.triggered.connect(self.connect)
    self.actionDisconnect.triggered.connect(self.disconnect)
    
    self.subscribed_nodes = []
    
    self.tableManager = TableManager(self)


def main(args):
  app = QApplication(sys.argv)
  form = MicroDAQviewer_live(args)
  form.show()
  app.aboutToQuit.connect(form.disconnect)
  app.exec_()


if __name__ == '__main__':
  # Create command line argument parser
  parser = argparse.ArgumentParser(description='Analyse MicroDAQ data',
      formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  parser.add_argument('--debug', action='store_true',
                      help='enable debug output')
  parser.add_argument('--nPlots', type=int, default = 1,
                    help='Set number of available plot slots')
  
  args = parser.parse_args()

  logging.config.dictConfig(LOGGING)
  logger_client.setLevel(logging.DEBUG) if args.debug else logger_client.setLevel(logging.INFO)
  if found_opcua == False:
    sys.exit("OPC UA module is not available on your system. Please install opcua-client via pip3!")
  main(args)
