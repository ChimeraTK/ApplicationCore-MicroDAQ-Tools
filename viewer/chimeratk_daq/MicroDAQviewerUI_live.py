# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'MicroDAQviewerUI_live.ui'
#
# Created by: PyQt5 UI code generator 5.9
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1507, 1057)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.comboBox = QtWidgets.QComboBox(self.centralwidget)
        self.comboBox.setEditable(True)
        self.comboBox.setObjectName("comboBox")
        self.horizontalLayout.addWidget(self.comboBox)
        self.connectButton = QtWidgets.QPushButton(self.centralwidget)
        self.connectButton.setMaximumSize(QtCore.QSize(100, 16777215))
        self.connectButton.setObjectName("connectButton")
        self.horizontalLayout.addWidget(self.connectButton)
        self.disconnectButton = QtWidgets.QPushButton(self.centralwidget)
        self.disconnectButton.setMaximumSize(QtCore.QSize(100, 16777215))
        self.disconnectButton.setObjectName("disconnectButton")
        self.horizontalLayout.addWidget(self.disconnectButton)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.splitter_2 = QtWidgets.QSplitter(self.centralwidget)
        self.splitter_2.setOrientation(QtCore.Qt.Horizontal)
        self.splitter_2.setObjectName("splitter_2")
        self.splitter = QtWidgets.QSplitter(self.splitter_2)
        self.splitter.setOrientation(QtCore.Qt.Vertical)
        self.splitter.setObjectName("splitter")
        self.treeView = QtWidgets.QTreeView(self.splitter)
        self.treeView.setMinimumSize(QtCore.QSize(500, 0))
        self.treeView.setBaseSize(QtCore.QSize(0, 0))
        self.treeView.setDragEnabled(True)
        self.treeView.setObjectName("treeView")
        self.tableWidget = QtWidgets.QTableWidget(self.splitter)
        self.tableWidget.setDragDropMode(QtWidgets.QAbstractItemView.DropOnly)
        self.tableWidget.setObjectName("tableWidget")
        self.tableWidget.setColumnCount(3)
        self.tableWidget.setRowCount(0)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget.setHorizontalHeaderItem(0, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget.setHorizontalHeaderItem(1, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget.setHorizontalHeaderItem(2, item)
        self.tableWidget.horizontalHeader().setDefaultSectionSize(166)
        self.gridLayoutWidget = QtWidgets.QWidget(self.splitter_2)
        self.gridLayoutWidget.setObjectName("gridLayoutWidget")
        self.gridLayout = QtWidgets.QGridLayout(self.gridLayoutWidget)
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.gridLayout.setObjectName("gridLayout")
        self.verticalLayout.addWidget(self.splitter_2)
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 1507, 25))
        self.menubar.setObjectName("menubar")
        self.menuAddGraph = QtWidgets.QMenu(self.menubar)
        self.menuAddGraph.setObjectName("menuAddGraph")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)
        self.actionConnect = QtWidgets.QAction(MainWindow)
        self.actionConnect.setObjectName("actionConnect")
        self.actionDisconnect = QtWidgets.QAction(MainWindow)
        self.actionDisconnect.setObjectName("actionDisconnect")
        self.menuAddGraph.addSeparator()
        self.menuAddGraph.addAction(self.actionConnect)
        self.menuAddGraph.addAction(self.actionDisconnect)
        self.menubar.addAction(self.menuAddGraph.menuAction())

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "MainWindow"))
        self.connectButton.setText(_translate("MainWindow", "Connect"))
        self.disconnectButton.setText(_translate("MainWindow", "Disconnect"))
        item = self.tableWidget.horizontalHeaderItem(0)
        item.setText(_translate("MainWindow", "parameter"))
        item = self.tableWidget.horizontalHeaderItem(1)
        item.setText(_translate("MainWindow", "value"))
        item = self.tableWidget.horizontalHeaderItem(2)
        item.setText(_translate("MainWindow", "unit"))
        self.menuAddGraph.setTitle(_translate("MainWindow", "Actions"))
        self.actionConnect.setText(_translate("MainWindow", "connect"))
        self.actionDisconnect.setText(_translate("MainWindow", "disconnect"))

