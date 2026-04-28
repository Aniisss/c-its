#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "domain_bridge::domain_bridge__rosidl_generator_py" for configuration "Release"
set_property(TARGET domain_bridge::domain_bridge__rosidl_generator_py APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(domain_bridge::domain_bridge__rosidl_generator_py PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "domain_bridge::domain_bridge__rosidl_generator_c;Python3::Python;domain_bridge::domain_bridge__rosidl_typesupport_c"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/libdomain_bridge__rosidl_generator_py.so"
  IMPORTED_SONAME_RELEASE "libdomain_bridge__rosidl_generator_py.so"
  )

list(APPEND _cmake_import_check_targets domain_bridge::domain_bridge__rosidl_generator_py )
list(APPEND _cmake_import_check_files_for_domain_bridge::domain_bridge__rosidl_generator_py "${_IMPORT_PREFIX}/lib/libdomain_bridge__rosidl_generator_py.so" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
