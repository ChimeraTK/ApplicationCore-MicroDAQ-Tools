#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys
import os
import fnmatch
import argparse
import logging
from PyQt5 import QtWidgets
from PyQt5.QtCore import QSettings

from chimeratk_daq.MicroDAQviewerUI import Ui_MainWindow
from chimeratk_daq.HDF5Viewer import HDF5Viewer
from chimeratk_daq.DataSelectorUI import Ui_PathSelectWindow

found_root = True
try:
  from chimeratk_daq.RootViewer import RootViewer
except ImportError:
  found_root = False

class DiaglogView(QtWidgets.QMainWindow, Ui_PathSelectWindow):
  
  def exit(self, button):
    if self._path == None:
      msg = QtWidgets.QMessageBox()
      msg.setIcon(QtWidgets.QMessageBox.Critical)
      msg.setText("No path set.")
      msg.setInformativeText('Please set a data path!')
      msg.setWindowTitle("Unit Error")
      msg.exec_()
    else:
      QtWidgets.qApp.exit()
  
  def setDirectory(self):
    if self._path == None:
      name = QtWidgets.QFileDialog.getExistingDirectory(self, 'Add directory', '/home', QtWidgets.QFileDialog.ShowDirsOnly | QtWidgets.QFileDialog.DontResolveSymlinks)
    else:
      name = QtWidgets.QFileDialog.getExistingDirectory(self, 'Add directory', self._path, QtWidgets.QFileDialog.ShowDirsOnly | QtWidgets.QFileDialog.DontResolveSymlinks)
    if name != "":
      logging.info("Add directory: " + name)
      self._path = name
      self.dataPath.setText(name)
    
  def setDirectoryManual(self, text):
    self._path = text
    self.dataPath.setText(text)
    self.settings.setValue("dataPath",text)
    self._updateStatusBar()
  
  def _updateStatusBar(self):
    if self._path == None:
      return
    try:
      if self.useHDF5.isChecked():
        filter  = fnmatch.filter(os.listdir(self._path), "*.h5")
      else:
        filter = fnmatch.filter(os.listdir(self._path), "*.root")
    except:
      return
    self.nFiles = len(filter)
    
    if self.nFiles == 0:
      self.setStatusBarMsg("No daq files in the specified directory.",'error')
      return
    sizeOfFirstFile = os.stat(self._path+"/"+filter[0]).st_size/(1024*1024)
    
    if self.nFiles*sizeOfFirstFile > 1000:
      estimateSize = "{} GB".format((int)(self.nFiles*sizeOfFirstFile/1000))
    else:
      estimateSize = "{} MB".format((int)(self.nFiles*sizeOfFirstFile))
    if self.nFiles*sizeOfFirstFile > 2*1000:
      self.setStatusBarMsg("Selected {} files. Estimated size: {}. Try to reduce the dataset using match stings!".format(self.nFiles, estimateSize),'warning')
    else:
      self.setStatusBarMsg("Selected {} files. Estimated size: {}".format(self.nFiles, estimateSize),'info')

  def addMatch(self):
    if self.matchPattern.text() in self._match:
      logging.error("Not going to add {} twice. {} is already in the list of matches".format(self.matchPattern.text(),self.matchPattern.text()))
      return
    
    if self.matchPattern.text() == "":
      logging.error("Not going to add empty match.")
      return
    if self._match == "":
      self._match = []
    self._match.append(self.matchPattern.text())
    item = QtWidgets.QListWidgetItem()
    item.setText(self._match[-1])
    self.matchList.insertItem(len(self._match)-1,item)
  
  def enableHDF5(self, state):
    if state == True:
      self.useSortByName.setEnabled(True)
      self.useTimeStampSorting.setEnabled(False)
    else:
      self.useSortByName.setEnabled(False)
      self.useTimeStampSorting.setEnabled(True)
    self._updateStatusBar()
      
  def setStatusBarMsg(self, msg, level = 'status'):
    '''
    Print message in the status bar.
    @param msg: Message to be shown.
    @param level:  Level to be used. Available are: error (red), status (black), info (green)
    '''
    if level == 'error':
      self.statusBar.setStyleSheet("QStatusBar{padding-left:8px;background:rgba(255,0,0,255);color:black;font-weight:bold;}")
    elif level == 'info':
      self.statusBar.setStyleSheet("QStatusBar{padding-left:8px;background:rgba(0,204,0,255);color:black;font-weight:bold;}")
    elif level == 'warning':
      self.statusBar.setStyleSheet("QStatusBar{padding-left:8px;background:rgba(254,178,76);color:black;font-weight:bold;}")
    else:
      self.statusbar.setStyleSheet("QStatusBar{padding-left:8px;background:rgba(255,0,0,0);color:black;font-weight:normal;}")
    self.statusBar.showMessage(str(msg))

  
  def __init__(self, args, parent=None):
    super(DiaglogView, self).__init__(parent)
    self.setupUi(self)
    
    self._path = args.path
    self.nFiles = 0
    self.dataPath.setText(self._path)
    self._match = args.matchString
    
    self.nPlots.setValue(args.nPlots)
    self.maxFiles.setValue(args.maxFiles)
    
    if args.matchString != "":
      for matchString in self._match:
        item = QtWidgets.QListWidgetItem()
        item.setText(matchString)
        self.matchList.insertItem(len(self._match)-1,item)
    
    self.buttonBox.clicked.connect(self.exit)
    self.setDataPath.clicked.connect(self.setDirectory)
    self.dataPath.textChanged.connect(self.setDirectoryManual)
    self.addMatchPattern.clicked.connect(self.addMatch)
    self.useHDF5.clicked.connect(self.enableHDF5)
    self._updateStatusBar()
    self.settings = QSettings("HZDR", "MicroDAQ Data Viewer")
    self.dataPath.setText(self.settings.value("dataPath", defaultValue="/home/", type=str))

def main(args):
  currentExitCode = None
  while currentExitCode == Ui_MainWindow.EXIT_CODE_REBOOT or currentExitCode == None:
    if args.path == None or currentExitCode == Ui_MainWindow.EXIT_CODE_REBOOT:
      # run data dialog
      app = QtWidgets.QApplication(sys.argv)
      form = DiaglogView(args)
      form.show()
      app.exec_()
      args.path = form._path
      args.matchString = form._match
      args.maxFiles = form.maxFiles.value()
      args.nPlots = form.nPlots.value()
      args.sortByName = form.useSortByName.isChecked()
      args.sortByTimeStamp = form.useTimeStampSorting.isChecked()
      args.useHDF5 = form.useHDF5.isChecked()
    if args.path == None:
      logging.error("Failed to get path name.")
      sys.exit(-1)
    if form.nFiles == 0:
      logging.error("No DAQ files found..")
      sys.exit(-1)
    app = None # delete the QApplication object
    
    # run main GUI
    app = QtWidgets.QApplication(sys.argv)
    if found_root and args.useHDF5 == False:
      form = RootViewer(args)
    else:
      form = HDF5Viewer(args)
    form.show()
    currentExitCode = app.exec_()
    app = None # delete the QApplication object



if __name__ == '__main__':
  # Create command line argument parser
  parser = argparse.ArgumentParser(description='Analyse MicroDAQ data',
      formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  parser.add_argument('-p' ,'--path', type=str, default=None,
                      help='path were the MicroDAQ files are located')
  parser.add_argument('-m','--matchString', type=str, nargs='+', default='',
                      help='Only files including the given string in their name will be considered.')
  parser.add_argument('--sortByTimeStamp', action='store_true', 
                      help='Use this switch to enable sorting of the inputfiles by time stamps stored the input files.')
  parser.add_argument('--sortByName', action='store_true', 
                      help='Use this switch to enable sorting of the inputfiles by input file names. Only applies to HDF5 files.')
  parser.add_argument('--debug', action='store_true',
                      help='enable debug output')
  parser.add_argument('--maxFiles', type=int, default = 0,
                      help='Give the maximum number of file to be opened. If n files are opened these are the last n files in history.  Only applies to HDF5 files.')
  parser.add_argument('--nPlots', type=int, default = 9,
                      help='Set number of available plot slots')
  if found_root:
    parser.add_argument('--useHDF5', action='store_true',
                        help='Set true if working on hdf5 files.')
    parser.add_argument('--averaging', type=int, default = 36,
                        help='Only applies if llrf_server_data is analysed. Specify the IQ detection length used in the LLRF firmware when averaging (e.g. 6 for fast firmware or 36 for slow firmware).')  
  
  args = parser.parse_args()
  # Set logging options
  logLevel = logging.DEBUG if args.debug else logging.INFO
  logging.basicConfig(format='[%(levelname)s]: %(message)s', level=logLevel)
  if args.matchString != '':
    logging.info("Using match string {}".format(args.matchString))
    
  main(args)

