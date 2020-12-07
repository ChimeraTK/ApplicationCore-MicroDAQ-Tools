#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys
import argparse
import logging
from PyQt5 import QtGui

from chimeratk_daq.MicroDAQviewerUI import Ui_MainWindow
from chimeratk_daq.HDF5Viewer import HDF5Viewer

found_root = True
try:
  from chimeratk_daq.RootViewer import RootViewer
except ImportError:
  found_root = False

def main(args):
  app = QtGui.QApplication(sys.argv)
  if found_root and args.useHDF5 == False:
    form = RootViewer(args)
  else:
    form = HDF5Viewer(args)
  form.show()
  app.exec_()


if __name__ == '__main__':
  # Create command line argument parser
  parser = argparse.ArgumentParser(description='Analyse MicroDAQ data',
      formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  parser.add_argument('path', type=str, nargs=1,
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

