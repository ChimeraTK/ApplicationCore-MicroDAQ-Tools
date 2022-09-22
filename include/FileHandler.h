/*
 * FileHandler.h
 *
 *  Created on: Oct 16, 2017
 *      Author: Klaus Zenker (HZDR)
 */

#ifndef INCLUDE_FILEHANDLER_H_
#define INCLUDE_FILEHANDLER_H_

#include "data_types.h"
#include "H5Cpp.h"
#include "TArrayF.h"
#include "TFile.h"
#include "TTree.h"

#include <boost/date_time/local_time/local_time.hpp>

#include <memory>
#include <string>

namespace hdf5converter {
  /**
   * Helper struct to read the date string used in the log files:
   * e.g. Mon Jan 19 14:35:25 2015
   * The actual format is set when initializing a dateparser object.
   * The format given above corresponds to  %a %b %d %H:%M:%S %Y.
   */
  struct dateparser {
    dateparser(std::string fmt) : msec(0), time(0) {
      // set format
      using namespace boost::local_time;
      local_time_input_facet* input_facet = new local_time_input_facet();
      input_facet->format(fmt.c_str());
      ss.imbue(std::locale(ss.getloc(), input_facet));
    }

    bool operator()(std::string const& text) {
      boost::posix_time::ptime pt;
      ss.clear();
      ss.str(text);
      ss >> pt;
      try {
        tm tm = to_tm(pt);
        msec = (pt.time_of_day()).fractional_seconds() / 1000;
        time = mktime(&tm); // time conversion in CET
      }
      catch(...) {
        return false;
      }
      return true;
    }

    unsigned msec;
    time_t time;

   private:
    std::stringstream ss;
  };

  class H5FileHandler {
   private:
    H5::H5File _file;
    std::shared_ptr<H5::Group> currentMainGroup;
    llrfData_t* _data;
    void readVector(const H5::DataSet& d, TArrayF& vd);
    void readGroup(const H5::Group& grp);

   public:
    H5FileHandler(const std::string& fileName, llrfData_t* data);
    long GetNEvents();

    /**
     * \remark If a certain value could not be read from the HDF5 file it is set to -9999.
     */
    void readData(const unsigned long& event);
  };

  class RootFileHandler {
   private:
    TFile _file;
    TTree* _tree;
    llrfData_t _data;
    const char* convertPath(std::string str);
    void addEvent();

   public:
    RootFileHandler(const std::string& fileName, const std::string& treeName, const Int_t& compression = 101);
    virtual ~RootFileHandler();
    void handleFile(const std::string& h5file);
  };

} // namespace hdf5converter

#endif /* INCLUDE_FILEHANDLER_H_ */
