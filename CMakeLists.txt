cmake_minimum_required(VERSION 3.16)
project(gr-snac VERSION 0.1.0 LANGUAGES CXX)
if(PYTHON_EXECUTABLE)
  set(Python3_EXECUTABLE "${PYTHON_EXECUTABLE}")
endif()
find_package(Python3 3.10 REQUIRED COMPONENTS Interpreter)
set(_snac_python_dir "${GR_PYTHON_DIR}")
find_package(Gnuradio 3.10 REQUIRED COMPONENTS runtime)
# GNU Radio 3.10.1 overwrites PYTHON_EXECUTABLE and its GrPython path
# calculation can escape a venv prefix. This Python-only module needs no bindings.
set(PYTHON_EXECUTABLE "${Python3_EXECUTABLE}")
if(_snac_python_dir)
  set(GR_PYTHON_DIR "${_snac_python_dir}")
else()
  execute_process(COMMAND "${PYTHON_EXECUTABLE}" -c
    "import sysconfig; print(sysconfig.get_path('platlib', scheme='posix_prefix', vars={'base': '${CMAKE_INSTALL_PREFIX}', 'platbase': '${CMAKE_INSTALL_PREFIX}'}))"
    OUTPUT_VARIABLE GR_PYTHON_DIR OUTPUT_STRIP_TRAILING_WHITESPACE
    RESULT_VARIABLE _snac_python_result)
  if(NOT _snac_python_result EQUAL 0)
    message(FATAL_ERROR "Could not determine Python install directory")
  endif()
endif()
include(CTest)
install(DIRECTORY python/gnuradio/snac/ DESTINATION ${GR_PYTHON_DIR}/gnuradio/snac
        FILES_MATCHING PATTERN "*.py" PATTERN "qa_snac.py" EXCLUDE PATTERN "__pycache__" EXCLUDE)
install(DIRECTORY python/gr_snac_core/ DESTINATION ${GR_PYTHON_DIR}/gr_snac_core
        FILES_MATCHING PATTERN "*.py" PATTERN "__pycache__" EXCLUDE)
install(FILES grc/snac_encoder.block.yml grc/snac_decoder.block.yml grc/snac_token_file.block.yml
        DESTINATION share/gnuradio/grc/blocks)
install(DIRECTORY examples/ DESTINATION share/gr-snac/examples
        FILES_MATCHING PATTERN "*.py" PATTERN "*.grc" PATTERN "__pycache__" EXCLUDE)
install(PROGRAMS tools/snac_token_info.py DESTINATION bin RENAME snac-token-info)
if(BUILD_TESTING)
  add_test(NAME snac-core COMMAND ${PYTHON_EXECUTABLE} -m unittest discover -s tests -v)
  set_tests_properties(snac-core PROPERTIES WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
  add_test(NAME snac-model-and-flowgraph COMMAND ${PYTHON_EXECUTABLE} python/gnuradio/snac/qa_snac.py)
  set_tests_properties(snac-model-and-flowgraph PROPERTIES
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR} SKIP_RETURN_CODE 77 TIMEOUT 300)
endif()
