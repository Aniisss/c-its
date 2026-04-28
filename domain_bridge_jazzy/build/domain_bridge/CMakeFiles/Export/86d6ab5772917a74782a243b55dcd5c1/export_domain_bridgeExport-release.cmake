#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "domain_bridge::domain_bridge_lib" for configuration "Release"
set_property(TARGET domain_bridge::domain_bridge_lib APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(domain_bridge::domain_bridge_lib PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/libdomain_bridge.so"
  IMPORTED_SONAME_RELEASE "libdomain_bridge.so"
  )

list(APPEND _cmake_import_check_targets domain_bridge::domain_bridge_lib )
list(APPEND _cmake_import_check_files_for_domain_bridge::domain_bridge_lib "${_IMPORT_PREFIX}/lib/libdomain_bridge.so" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
