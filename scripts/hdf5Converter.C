// SPDX-FileCopyrightText: Helmholtz-Zentrum Dresden-Rossendorf, FWKE, ChimeraTK Project <chimeratk-support@desy.de>
// SPDX-License-Identifier: LGPL-3.0-or-later
/*
 * hdf5Converter.C
 *
 *  Created on: Oct 16, 2017
 *      Author: Klaus Zenker (HZDR)
 */
#include <iostream>

// boost
#include <boost/program_options.hpp>

#include "TROOT.h"
#include "TFile.h"
#include <boost/log/trivial.hpp>
#include <boost/log/expressions.hpp>
#include <boost/filesystem.hpp>
#include <boost/date_time/posix_time/posix_time.hpp>
#include "boost/date_time/c_local_time_adjustor.hpp"
#include "FileHandler.h"

namespace po = boost::program_options;

using namespace std;
using namespace hdf5converter;

void initLogging(int logLevel){
  if(logLevel == 0)
    boost::log::core::get()->set_filter(boost::log::trivial::severity >= boost::log::trivial::debug);
  else if(logLevel == 1)
    boost::log::core::get()->set_filter(boost::log::trivial::severity >= boost::log::trivial::info);
  else if(logLevel == 2)
    boost::log::core::get()->set_filter(boost::log::trivial::severity >= boost::log::trivial::warning);
  else
    boost::log::core::get()->set_filter(boost::log::trivial::severity >= boost::log::trivial::fatal);

}

int main(int argc, char * argv[]){
  ROOT::EnableImplicitMT();
  vector<string> inputFiles;
  bool override, withTime, rename;
  int logLevel, mergeFiles;
  std::string treeName, oldTree, outputDir;
  try{
      po::options_description generic("Common options");
      generic.add_options()
          ("help,h",
              "Print help.")
      ;
      generic.add_options()
          ("treeName", po::value(&treeName),
              "Set the tree name to be used (e.g. llrf_server_data).")
            ;
      generic.add_options()
          ("logLevel,l", po::value(&logLevel)->default_value(1),
              "LogLevel: debug(0), info(1), warning(2), silent(3)")
            ;
      generic.add_options()
          ("outputDir", po::value(&outputDir)->default_value(""),
              "Set an output directory. If not set files are produced in the directory where the input file is located.")
            ;
      po::options_description convert_options("Convert options");
      convert_options.add_options()
          ("overwrite,o", po::bool_switch(&override)->default_value(false),
              "If true existing converted files are overwritten and converted again. Else they are skipped.");
      convert_options.add_options()
          ("withTime,t", po::bool_switch(&withTime)->default_value(false),
              "If true the root file name will include the time stamp.");
      convert_options.add_options()
          ("merge", po::value(&mergeFiles)->default_value(0),
              "Set the number of input files that will be merged into one root file. Keep in mind to sort the files on your own!");

      po::options_description rename_options("Renaming options");
      rename_options.add_options()
          ("rename", po::bool_switch(&rename)->default_value(false),
          "Use this option to rename trees in root files.");

      rename_options.add_options()
          ("oldTree", po::value(&oldTree),
          "The name of the tree to be renamed.");
      po::options_description hidden("Hidden options");
      hidden.add_options()
          ("files,f", po::value<vector<string> >()->multitoken(),
              "Give a list of filenames to be processed.")
      ;
      po::options_description cmdline_options;
      cmdline_options.add(generic).add(convert_options).add(rename_options).add(hidden);

      po::options_description visible("Usage: hdf5Convert [options] data.h5 ...\n"
          "Use cases: \n 1. hdf5Convert -t --treeName llrf_server_data data1.h5 data2.h5"
          "\n 2. hdf5Convert --rename --oldTree llrf_server_data_old --treeName llrf_server_data data1.root data2.root"
              "Allowed program options");
      visible.add(generic).add(convert_options).add(rename_options);
      po::positional_options_description p;
      p.add("files", -1);
      po::variables_map vm;
      po::store(po::command_line_parser(argc, argv).options(cmdline_options).positional(p).run(), vm);
      po::notify(vm);
      if(vm.count("help")){
        cout << visible << endl;
        return 0;
      }
      if(vm.count("files")){
        vector<string> tmp_files = vm["files"].as<vector<string> >();
        vector<string>::iterator it = tmp_files.begin();
        while(it != tmp_files.end()){
          inputFiles.push_back(*it);
          it++;
        }

      } else {
        cerr << "No input file given!" << endl;
        cout << visible << endl;
        return 0;
      }
      if(!vm.count("treeName")){
        BOOST_LOG_TRIVIAL(error) << "You have to specify the tree name to be used in the root file. Pay attention some analysis"
            " will use the treeName to assume finding certain variables." << std::endl;
        cout << visible << endl;
        return 0;
      }
      if(rename && !vm.count("oldTree")){
        BOOST_LOG_TRIVIAL(error) << "When renaming trees you have to specify the old tree name" << std::endl;
        cout << visible << endl;
        return 0;
      }
  }
  catch(const po::error &e){
    cerr << "error: " << e.what() << endl;
    return 1;
  }
  initLogging(logLevel);
  std::unique_ptr<RootFileHandler> prfh(nullptr);
  int mergedFiles = 0;
  for(auto &inputFile : inputFiles){
    auto binputfile = boost::filesystem::path(inputFile);
    if(!boost::filesystem::exists(binputfile)){
      BOOST_LOG_TRIVIAL(info) << "Input file " << inputFile << " does not exist and is skipped." << std::endl;
      continue;
    }
    if(rename){
      if(binputfile.extension().compare(".root")){
        BOOST_LOG_TRIVIAL(info) << "Skipped non root file: " << inputFile << std::endl;
        continue;
      }
      TFile f(inputFile.c_str(), "update");
      TTree* t = (TTree*)f.Get(treeName.c_str());
      if(t != nullptr){
        BOOST_LOG_TRIVIAL(info) << "The tree " << treeName << " already exists in file: " << inputFile << std::endl;
        continue;
      }
      t = (TTree*)f.Get(oldTree.c_str());
      if(t == nullptr){
        BOOST_LOG_TRIVIAL(info) << "Could not find " << oldTree << " in file: " << inputFile << std::endl;
        continue;
      }

      t->Write(treeName.c_str());
      f.Close();
      BOOST_LOG_TRIVIAL(info) << "Renamed tree (" << oldTree << "->" << treeName <<  ") in file: " << inputFile << std::endl;
    } else {
      boost::filesystem::path boutputfile;
      if(binputfile.extension().compare(".h5")){
        BOOST_LOG_TRIVIAL(info) << "Skipped file with wrong extension: " << inputFile << std::endl;
        continue;
      }
      if(outputDir.empty())
        boutputfile = binputfile.parent_path();
      else
        boutputfile = boost::filesystem::path(outputDir);
      if(withTime){
        auto path = binputfile.parent_path();
        const boost::posix_time::ptime time =
          boost::posix_time::from_time_t(boost::filesystem::last_write_time(inputFile));

        typedef boost::date_time::c_local_adjustor<boost::posix_time::ptime> local_adj;
        const boost::posix_time::ptime local_time =  local_adj::utc_to_local(time);
        boost::posix_time::time_facet * facet =
            new boost::posix_time::time_facet("%Y-%m-%d_%H-%M-%S");
        std::ostringstream stream;
        stream.imbue(std::locale(std::locale::classic(), facet));
        stream << local_time <<  "_";
        boutputfile /= stream.str();
        boutputfile += binputfile.filename();
        BOOST_LOG_TRIVIAL(debug) << "Last file write time: " << to_simple_string(local_time) << std::endl;
      } else {
        boutputfile /= binputfile.filename();
      }
      boutputfile.replace_extension(".root");
      if(boost::filesystem::exists(boutputfile) && !override){
        BOOST_LOG_TRIVIAL(info) << "Skipped file: " << inputFile << " (file " << boutputfile << " exists -> use -o to overwrite)"<< std::endl;
        continue;
      }
      try{
        if(prfh == nullptr || mergeFiles == 0 || (mergeFiles > 0 && mergedFiles == mergeFiles)){
          /**
           * Reset with nullptr in order to keep destructor/constructor call sequence.
           * Without this step:
           * - constructor new object
           * - destructor old object
           *
           * With this step:
           * - destructor old object
           * -constructor new object
           *
           * Without this order root files might miss some events!!
           */
          prfh.reset(nullptr);
          prfh.reset(new RootFileHandler(boutputfile.c_str(), treeName));
          mergedFiles = 0;
          BOOST_LOG_TRIVIAL(info) << "Outputfile is: " << boutputfile << std::endl;
        }
        prfh->handleFile(inputFile);
        mergedFiles++;
        BOOST_LOG_TRIVIAL(info) << "Converted file: " << inputFile << std::endl;
      } catch (H5::FileIException &e){
        BOOST_LOG_TRIVIAL(error) << "Failed to convert file: " << inputFile << std::endl;
        BOOST_LOG_TRIVIAL(error) << "Message: " << e.getCDetailMsg() << std::endl;
        if (boost::filesystem::exists(boutputfile))
          boost::filesystem::remove(boutputfile);
      } catch (...) {
        BOOST_LOG_TRIVIAL(error) << "Failed to convert file: " << inputFile << std::endl;
        if (boost::filesystem::exists(boutputfile))
          boost::filesystem::remove(boutputfile);
      }
    }
  }
}
