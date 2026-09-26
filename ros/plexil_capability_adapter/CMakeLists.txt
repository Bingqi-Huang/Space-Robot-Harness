cmake_minimum_required(VERSION 3.16)
project(plexil_capability_adapter)
set(CMAKE_CXX_STANDARD 17)

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_action REQUIRED)
find_package(space_harness_msgs REQUIRED)
find_package(openral_msgs REQUIRED)

# PLEXIL Release 6 install (research repo docs/baselines/plexil.md): headers and libraries under $PLEXIL_HOME
set(PLEXIL_HOME $ENV{PLEXIL_HOME} CACHE PATH "PLEXIL installation")
find_library(PLEXIL_APP PlexilAppFramework PATHS ${PLEXIL_HOME}/lib REQUIRED NO_DEFAULT_PATH)
find_library(PLEXIL_INTFC PlexilIntfc PATHS ${PLEXIL_HOME}/lib REQUIRED NO_DEFAULT_PATH)
find_library(PLEXIL_VALUE PlexilValue PATHS ${PLEXIL_HOME}/lib REQUIRED NO_DEFAULT_PATH)
find_library(PLEXIL_UTILS PlexilUtils PATHS ${PLEXIL_HOME}/lib REQUIRED NO_DEFAULT_PATH)

# The module name is what universalExec's DynamicLoader calls: libCapabilityAdapter.so, initCapabilityAdapter()
add_library(CapabilityAdapter SHARED src/CapabilityAdapter.cc)
# CommandImpl.hh (the issuing node's id, send()) is not an installed header: read from the source tree, same checkout
target_include_directories(CapabilityAdapter PRIVATE ${PLEXIL_HOME}/include ${PLEXIL_HOME}/src/intfc ${PLEXIL_HOME}/src/expr)
target_link_libraries(CapabilityAdapter ${PLEXIL_APP} ${PLEXIL_INTFC} ${PLEXIL_VALUE} ${PLEXIL_UTILS})
ament_target_dependencies(CapabilityAdapter rclcpp rclcpp_action space_harness_msgs openral_msgs)

install(TARGETS CapabilityAdapter LIBRARY DESTINATION lib)
install(DIRECTORY config DESTINATION share/${PROJECT_NAME})
ament_package()
