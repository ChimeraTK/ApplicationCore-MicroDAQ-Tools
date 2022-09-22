/*
 * data_types.h
 *
 *  Created on: Oct 18, 2017
 *      Author: Klaus Zenker (HZDR)
 */

#ifndef INCLUDE_DATA_TYPES_H_
#define INCLUDE_DATA_TYPES_H_

#include "TString.h"
#include "TDatime.h"
#include "TArrayF.h"

#include <map>
namespace hdf5converter {

  struct timeInfo_t {
    TDatime datime;
    TString strTimeStamp;
    time_t timeStamp;
    unsigned msec;
  };

  struct llrfData_t {
    std::map<std::string, Float_t> paramter;
    std::map<std::string, TArrayF> trace;
    timeInfo_t timeInfo;
  };
} // namespace hdf5converter
namespace uDAQ {
  /**
 * Trace is introduced for better readability and because pyroot can not handle
 * std::map<std::string, std::pair<std::vector, std::vector> > >
 */
  struct Trace {
    std::vector<Double_t> x, y;
    Trace(){};
    Trace(size_t length) : x(std::vector<double>(length)), y(std::vector<double>(length)){};
  };
} // namespace uDAQ

#endif /* INCLUDE_DATA_TYPES_H_ */
