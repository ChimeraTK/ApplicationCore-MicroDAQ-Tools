/*
 * testReading.C
 *
 *  Created on: Mar 10, 2020
 *      Author: Klaus Zenker (HZDR)
 */

//#define BOOST_TEST_DYN_LINK
#define BOOST_TEST_MODULE MicroDAQTest

#include <boost/test/unit_test.hpp>
#include <boost/test/included/unit_test.hpp>
#include <boost/fusion/container/map.hpp>
#include <boost/mpl/list.hpp>
#include <boost/filesystem.hpp>

#include "TFile.h"
#include "TArrayF.h"
#include "TArrayS.h"
#include "TArrayL.h"
#include "TArrayD.h"
#include "TArrayI.h"
#include "TArrayC.h"
#include "TTree.h"

#include <map>

#include "DataHandler.h"

// list of user types to be tested. These are the data types used in ChimeraTK
typedef boost::mpl::list<int8_t, uint8_t, int16_t, uint16_t, int32_t, uint32_t, uint64_t, int64_t, float, double, bool>
    test_types;

/**
 *  This is copied from ApplicationCore-MicroDAQ data_types.h
 *  I think this is ok to not create a dependency on the ApplicationCore-MicroDAQ package.
 *  Also this will not end up in the library installed in the ApplicationCore-MicroDAQ-Tools package.
 */
template<typename UserType>
struct TreeDataFields {};
template<>
struct TreeDataFields<float> {
  std::map<std::string, Float_t> parameter;
  std::map<std::string, TArrayF> trace;
};
template<>
struct TreeDataFields<double> {
  std::map<std::string, Double_t> parameter;
  std::map<std::string, TArrayD> trace;
};
template<>
struct TreeDataFields<uint8_t> {
  std::map<std::string, UChar_t> parameter;
  std::map<std::string, TArrayS> trace;
};
template<>
struct TreeDataFields<int8_t> {
  std::map<std::string, Char_t> parameter;
  std::map<std::string, TArrayS> trace;
};
template<>
struct TreeDataFields<uint16_t> {
  std::map<std::string, UShort_t> parameter;
  std::map<std::string, TArrayS> trace;
};
template<>
struct TreeDataFields<int16_t> {
  std::map<std::string, Short_t> parameter;
  std::map<std::string, TArrayS> trace;
};
template<>
struct TreeDataFields<uint32_t> {
  std::map<std::string, UInt_t> parameter;
  std::map<std::string, TArrayI> trace;
};
template<>
struct TreeDataFields<int32_t> {
  std::map<std::string, Int_t> parameter;
  std::map<std::string, TArrayI> trace;
};
template<>
struct TreeDataFields<uint64_t> {
  std::map<std::string, ULong64_t> parameter;
  std::map<std::string, TArrayL> trace;
};
template<>
struct TreeDataFields<int64_t> {
  std::map<std::string, Long64_t> parameter;
  std::map<std::string, TArrayL> trace;
};
template<>
struct TreeDataFields<bool> {
  std::map<std::string, Bool_t> parameter;
  std::map<std::string, TArrayC> trace;
};

template<typename T>
struct DataSet {
  std::shared_ptr<uDAQ::DataHandler> dh;
  DataSet() {
    TFile file("/tmp/test.root", "RECREATE");
    TreeDataFields<T> data;
    data.trace["test"].Set(10);
    data.parameter["test"] = 0;
    hdf5converter::timeInfo_t t;
    TTree tree("test_data", "data");
    tree.Branch("val", &data.parameter["test"]);
    tree.Branch("arr", &data.trace["test"]);
    tree.Branch("timeInfo", &t);
    for(size_t event = 0; event < 10; event++) {
      data.parameter["test"] = event;
      if constexpr(std::is_same<T, bool>::value) {
        data.trace["test"][0] = 0;
        for(size_t i = 1; i < 10; i++) {
          data.trace["test"][i] = !data.trace["test"][i - 1];
        }
      }
      else {
        for(size_t i = 0; i < 10; i++) {
          data.trace["test"][i] = i + event;
        }
      }
      tree.Fill();
    }
    tree.Write();
    file.Close();
    std::vector<std::string> v = {"test.root"};
    dh.reset(new uDAQ::DataHandler("/tmp", false, v));
  }
  ~DataSet() { BOOST_CHECK_EQUAL(boost::filesystem::remove("/tmp/test.root"), true); }
};

BOOST_AUTO_TEST_CASE_TEMPLATE(testReading, T, test_types) {
  DataSet<T> ds;
  std::set<std::string> s = {"arr", "val"};
  ds.dh->prepareReading(s);
  ds.dh->readData(0);
  BOOST_CHECK_EQUAL(ds.dh->timeLines["val"].y.size(), 1);
  BOOST_CHECK_EQUAL(ds.dh->timeLines["val"].y[0], 0);
  BOOST_CHECK_EQUAL(ds.dh->timeLines["arr"].y.size(), 10);
  if constexpr(std::is_same<T, bool>::value) {
    std::vector<bool> v = {false, true, false, true, false, true, false, true, false, true};
    BOOST_CHECK_EQUAL_COLLECTIONS(
        v.begin(), v.end(), ds.dh->timeLines["arr"].y.begin(), ds.dh->timeLines["arr"].y.end());
  }
  else {
    std::vector<T> v = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9};
    BOOST_CHECK_EQUAL_COLLECTIONS(
        v.begin(), v.end(), ds.dh->timeLines["arr"].y.begin(), ds.dh->timeLines["arr"].y.end());
  }
}
