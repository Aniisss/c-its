#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "domain_bridge::domain_bridge__rosidl_typesupport_fastrtps_cpp" for configuration "Release"
set_property(TARGET domain_bridge::domain_bridge__rosidl_typesupport_fastrtps_cpp APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(domain_bridge::domain_bridge__rosidl_typesupport_fastrtps_cpp PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/libdomain_bridge__rosidl_typesupport_fastrtps_cpp.so"
  IMPORTED_SONAME_RELEASE "libdomain_bridge__rosidl_typesupport_fastrtps_cpp.so"
  )

list(APPEND _cmake_import_check_targets domain_bridge::domain_bridge__rosidl_typesupport_fastrtps_cpp )
list(APPEND _cmake_import_check_files_for_domain_bridge::domain_bridge__rosidl_typesupport_fastrtps_cpp "${_IMPORT_PREFIX}/lib/libdomain_bridge__rosidl_typesupport_fastrtps_cpp.so" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
