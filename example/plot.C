// SPDX-FileCopyrightText: Helmholtz-Zentrum Dresden-Rossendorf, FWKE, ChimeraTK Project <chimeratk-support@desy.de>
// SPDX-License-Identifier: LGPL-3.0-or-later
/*
 * plot.C
 *
 *  Created on: May 28, 2018
 *      Author: Klaus Zenker (HZDR)
 */

#include "DataHandler.h"
#include "TApplication.h"
#include "TCanvas.h"
#include "TSystem.h"

#include <iostream>

// boost
#include <boost/program_options.hpp>

namespace po = boost::program_options;
using namespace std;

int main(int argc, char* argv[]) {
  std::string dir, var;
  std::vector<std::string> match;
  int logLevel;
  try {
    po::options_description generic("Common options");
    generic.add_options()("help,h", "This program needs the full file name.");
    generic.add_options()("input,d", po::value<string>(&dir), "Directory with input files to be processed.");
    generic.add_options()("var,v", po::value<string>(&var), "ProcessVariable from the TTree to be drawn.");
    generic.add_options()(
        "match,m", po::value<std::vector<string>>()->multitoken(), "Match string to be used for file selection");
    generic.add_options()(
        "logLevel,l", po::value<int>(&logLevel)->default_value(1), "Set log level: 0 (Debug), 1 (Info), 2 (Error).");
    po::options_description visible("Usage: hdf5Convert [options] data.h5 ...\n"
                                    "Allowed program options");
    visible.add(generic);
    po::positional_options_description p;
    p.add("files", -1);
    po::variables_map vm;
    po::store(po::command_line_parser(argc, argv).options(generic).run(), vm);
    po::notify(vm);
    if(vm.count("help")) {
      cout << visible << endl;
      return 0;
    }
    else if(!vm.count("input")) {
      cerr << "No input directory set!" << endl;
      cout << generic << endl;
      return 0;
    }
    else if(!vm.count("var")) {
      cerr << "No variable spcified. Use something like e.g. system.status.cpuTotal!" << endl;
      cout << generic << endl;
      return 0;
    }
    if(vm.count("match")) {
      match = vm["match"].as<vector<string>>();
    }
  }
  catch(const po::error& e) {
    cerr << "error: " << e.what() << endl;
    return 1;
  }
  uDAQ::DataHandler::setLogLevel(logLevel);
  TApplication app("plot", &argc, argv);
  uDAQ::DataHandler dh(dir, true, match);
  std::set<std::string> l;
  l.insert(var);
  int nMax = dh.getEntries();
  dh.prepareReading(l);
  dh.getTimeLine(0, nMax, 1, 0, uDAQ::TimeAxis::TRUE);
  while(!dh.isDone().first) {
    std::this_thread::sleep_for(1s);
  }
  TGraph* g = new TGraph(nMax, &dh.timeLines[var].x[0], &dh.timeLines[var].y[0]);
  TCanvas* c = new TCanvas("test", "test", 1000, 1200);
  c->cd();
  g->Draw("anl");
  app.Run(kTRUE);
  return 0;
}
