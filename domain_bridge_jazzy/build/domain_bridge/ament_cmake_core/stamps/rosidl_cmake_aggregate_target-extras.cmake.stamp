# generated from rosidl_cmake/cmake/rosidl_cmake_aggregate_target-extras.cmake.in

# Create a convenience aggregate target domain_bridge::domain_bridge
# that links all generated interface targets, so downstream packages can use
# a single modern CMake target name instead of ${domain_bridge_TARGETS}.
if(domain_bridge_TARGETS AND NOT TARGET domain_bridge::domain_bridge)
  add_library(domain_bridge::domain_bridge INTERFACE IMPORTED)
  set_target_properties(domain_bridge::domain_bridge PROPERTIES
    INTERFACE_LINK_LIBRARIES "${domain_bridge_TARGETS}")
endif()
