PROJECT(ApplicationCore-MicroDAQ-Tools)
cmake_minimum_required(VERSION 3.16)

#______________________________________________________________________________
#                                                                       OPTIONS

option(ENABLE_ROOT "Add support for ROOT based DAQ tools" OFF)
option(ENABLE_HDF5 "Add support for HDF5 based DAQ tools" ON)
option(ENABLE_TESTING "Build tests" ON)

#______________________________________________________________________________
#                                                                       VERSION
set( ${PROJECT_NAME}_MAJOR_VERSION 01 )
set( ${PROJECT_NAME}_MINOR_VERSION 06 )
set( ${PROJECT_NAME}_PATCH_VERSION 04 )
include(${CMAKE_SOURCE_DIR}/cmake/set_version_numbers.cmake)
include(${CMAKE_SOURCE_DIR}/cmake/set_default_flags.cmake)
include(${CMAKE_SOURCE_DIR}/cmake/set_default_build_to_release.cmake)

#______________________________________________________________________________
#                                                                  Dependencies

IF(ENABLE_HDF5)
  FIND_PACKAGE( HDF5 REQUIRED COMPONENTS C CXX HL)
ENDIF(ENABLE_HDF5)

IF(ENABLE_ROOT)
  FIND_PACKAGE(ROOT 6.08 REQUIRED COMPONENTS Core Tree Gui Graf RIO)
  INCLUDE(${ROOT_USE_FILE})
  # first this since it sets -std=c++11
  ADD_DEFINITIONS(${ROOT_CXX_FLAGS})
ENDIF(ENABLE_ROOT)

# now set latest c++ support
include(cmake/enable_latest_cxx_support.cmake)


FIND_PACKAGE( Boost REQUIRED COMPONENTS program_options log filesystem regex)

#______________________________________________________________________________
#                                                                      Includes
include_directories( include ${HDF5_INCLUDE_DIRS})

#______________________________________________________________________________
#                                                                    Dictionary
IF(ENABLE_ROOT)
  set( ROOTDICT ${PROJECT_NAME}Dict )
  ROOT_GENERATE_DICTIONARY( ${ROOTDICT} TypeDefinitions.h
                                        DataHandler.h
                                        LINKDEF include/LinkDef.h)
ENDIF(ENABLE_ROOT)

#______________________________________________________________________________
#                                                                  Build target
IF(ENABLE_ROOT)
  IF(ENABLE_HDF5)
    # binary used to convert hdf5 files to root                                     
    add_executable(hdf5Converter scripts/hdf5Converter.C)
    target_link_libraries( hdf5Converter Boost::program_options
                                         Boost::log
                                         ${PROJECT_NAME})
    set_target_properties(hdf5Converter PROPERTIES INSTALL_RPATH_USE_LINK_PATH TRUE)
    
    # Library used to analyse ROOT files
    add_library( ${PROJECT_NAME} SHARED src/DataHandler.cpp  src/FileHandler.cpp
                                        ${ROOTDICT})
    target_link_libraries( ${PROJECT_NAME} ${HDF5_HL_LIBRARIES} 
                                           ${HDF5_CXX_LIBRARIES} 
                                           ROOT::Core
                                           ROOT::RIO
                                           ROOT::Tree
                                           ROOT::Graf
                                           Boost::filesystem
                                           Boost::log)
  
  ELSE()
    # Library used to analyse ROOT files
    add_library( ${PROJECT_NAME} SHARED src/DataHandler.cpp
                                      ${ROOTDICT})
    target_link_libraries( ${PROJECT_NAME} ROOT::Core
                                           ROOT::RIO
                                           ROOT::Tree
                                           ROOT::Graf
                                           Boost::filesystem
                                           Boost::log)
  
  ENDIF(ENABLE_HDF5)

  set_target_properties(${PROJECT_NAME} PROPERTIES PUBLIC_HEADER "include/TypeDefinitions.h;include/DataHandler.h")
  set_target_properties(${PROJECT_NAME} PROPERTIES VERSION ${${PROJECT_NAME}_FULL_LIBRARY_VERSION} SOVERSION ${${PROJECT_NAME}_SOVERSION})
  set_target_properties(${PROJECT_NAME} PROPERTIES INSTALL_RPATH_USE_LINK_PATH TRUE)
  target_link_libraries( ${PROJECT_NAME} ${HDF5_HL_LIBRARIES} 
                                         ${HDF5_CXX_LIBRARIES} 
                                         ROOT::Core
                                         ROOT::RIO
                                         ROOT::Tree
                                         ROOT::Graf
                                         Boost::filesystem
                                         Boost::log)
  # Analysis example 
  add_executable( plot example/plot.C)
  target_link_libraries( plot ${PROJECT_NAME}
                              ROOT::Gpad
                              ROOT::Tree
                              Boost::program_options)
  set_target_properties( plot PROPERTIES INSTALL_RPATH_USE_LINK_PATH TRUE)                                
  target_include_directories(${PROJECT_NAME} INTERFACE "$<INSTALL_INTERFACE:include>")
ENDIF(ENABLE_ROOT)

find_package(Boost COMPONENTS unit_test_framework)                            
if(Boost_UNIT_TEST_FRAMEWORK_FOUND AND ENABLE_TESTING)
  enable_testing()

  if(ENABLE_ROOT)
    add_executable(test_Reading test/testReading.C)
    target_link_libraries( test_Reading  ${PROJECT_NAME} ROOT::Tree ROOT::Graf Boost::unit_test_framework)                         
    add_test( test_Reading test_Reading)
  endif(ENABLE_ROOT)                                  
  
else()
  message(STATUS "Boost test framework not found. No boost based tests will be build.")

endif(Boost_UNIT_TEST_FRAMEWORK_FOUND AND ENABLE_TESTING)

#______________________________________________________________________________
#                                                             Install root part
# Install the library and the executables
# this defines architecture-dependent ${CMAKE_INSTALL_LIBDIR}
include(GNUInstallDirs)
if(ENABLE_ROOT)
  INSTALL(FILES ${PROJECT_BINARY_DIR}/lib${ROOTDICT}_rdict.pcm
          DESTINATION ${CMAKE_INSTALL_LIBDIR}
          PERMISSIONS OWNER_READ OWNER_WRITE
                      GROUP_READ
                      WORLD_READ)
          
  INSTALL(TARGETS  ${PROJECT_NAME}
          EXPORT ${PROJECT_NAME}Targets
          LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
          PUBLIC_HEADER DESTINATION ${CMAKE_INSTALL_PREFIX}/include/ChimeraTK/ApplicationCore
          RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}          
          PERMISSIONS OWNER_READ OWNER_WRITE
                      GROUP_READ
                      WORLD_READ)
                         
  
  if(ENABLE_HDF5)
    INSTALL(TARGETS hdf5Converter
            EXPORT ${PROJECT_NAME}LibraryDepends 
            RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR} 
            PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE
                        GROUP_READ GROUP_EXECUTE
                        WORLD_READ WORLD_EXECUTE)
  
  endif(ENABLE_HDF5)
endif(ENABLE_ROOT)         

#______________________________________________________________________________
#                                                           Install python part
find_program(lsb_release lsb_release)
    execute_process(COMMAND ${lsb_release} -is
                OUTPUT_VARIABLE lsb_vendor_name
                OUTPUT_STRIP_TRAILING_WHITESPACE)
                
set(os_vendor ${lsb_vendor_name})


if(${CMAKE_VERSION} VERSION_LESS "3.12.0")
  find_package(PythonLibs REQUIRED) 
  string(REPLACE "." ";" version_list ${PYTHONLIBS_VERSION_STRING})
  list(GET version_list 0 Python3_VERSION_MAJOR)
  list(GET version_list 1 Python3_VERSION_MINOR)
else()
  find_package (Python3 COMPONENTS Interpreter)
endif()

if(("${os_vendor}" STREQUAL "Ubuntu") AND 
    (("${CMAKE_INSTALL_PREFIX}" STREQUAL "/usr") OR
     ("${CMAKE_INSTALL_PREFIX}" STREQUAL "/usr/local")))
  message(STATUS "Vendor is: ${os_vendor}. Prefix is set to: ${CMAKE_INSTALL_PREFIX}. So python install location is set to: lib/python${Python3_VERSION_MAJOR}/dist-packages") 
  set(PYTHON_INSTALL_LIB lib/python${Python3_VERSION_MAJOR}/dist-packages)
else()
  set(PYTHON_INSTALL_LIB lib/python${Python3_VERSION_MAJOR}.${Python3_VERSION_MINOR}/site-packages)
endif()
if(NOT ENABLE_ROOT)
  INSTALL( DIRECTORY ${PROJECT_SOURCE_DIR}/viewer/chimeratk_daq
           DESTINATION ${CMAKE_INSTALL_PREFIX}/${PYTHON_INSTALL_LIB}
           COMPONENT analysis
           FILES_MATCHING PATTERN "*.py"
                          PATTERN "Root*" EXCLUDE
           PERMISSIONS OWNER_EXECUTE OWNER_READ OWNER_WRITE
                       GROUP_EXECUTE GROUP_READ
                       WORLD_READ)
else()
  configure_file(${PROJECT_SOURCE_DIR}/viewer/chimeratk_daq/RootWorker.py.in ${PROJECT_BINARY_DIR}/RootWorker.py @ONLY)
  INSTALL( FILES ${PROJECT_BINARY_DIR}/RootWorker.py
           DESTINATION ${CMAKE_INSTALL_PREFIX}/${PYTHON_INSTALL_LIB}/chimeratk_daq
           COMPONENT analysis
           PERMISSIONS OWNER_EXECUTE OWNER_READ OWNER_WRITE
                       GROUP_EXECUTE GROUP_READ
                       WORLD_READ)

  INSTALL( DIRECTORY ${PROJECT_SOURCE_DIR}/viewer/chimeratk_daq
           DESTINATION ${CMAKE_INSTALL_PREFIX}/${PYTHON_INSTALL_LIB}
           COMPONENT analysis
           FILES_MATCHING PATTERN "*.py"
           PERMISSIONS OWNER_EXECUTE OWNER_READ OWNER_WRITE
                       GROUP_EXECUTE GROUP_READ
                       WORLD_READ)
endif()

INSTALL( FILES ${PROJECT_SOURCE_DIR}/viewer/UAClient.py
         DESTINATION ${CMAKE_INSTALL_PREFIX}/bin
         RENAME UAClient
         PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE
                     GROUP_READ GROUP_EXECUTE
                     WORLD_READ WORLD_EXECUTE)
INSTALL( FILES ${PROJECT_SOURCE_DIR}/viewer/MicroDAQviewer.py
         DESTINATION ${CMAKE_INSTALL_PREFIX}/bin
         RENAME MicroDAQViewer
         PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE
                     GROUP_READ GROUP_EXECUTE
                     WORLD_READ WORLD_EXECUTE)
                     
# export package
if(ENABLE_ROOT)

  list(APPEND ${PROJECT_NAME}_PUBLIC_DEPENDENCIES "Boost COMPONENTS filesystem log")
  list(APPEND ${PROJECT_NAME}_PUBLIC_DEPENDENCIES "ROOT COMPONENTS Core Tree Gui Graf RIO")
  # we support our cmake EXPORTS as imported targets
  set(PROVIDES_EXPORTED_TARGETS 1)
  include(${CMAKE_SOURCE_DIR}/cmake/create_cmake_config_files.cmake)        
endif(ENABLE_ROOT)

