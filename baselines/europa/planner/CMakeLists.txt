cmake_minimum_required(VERSION 3.10)
project(europa_plan CXX)
set(EUROPA_HOME $ENV{HOME}/Programs/europa/dist/europa)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O2 -m64")
set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -Wl,--disable-new-dtags")  # RPATH also serves the libs' own deps
add_definitions(-DEUROPA_FAST=1 -DEUROPA_64_BIT_PLATFORM -DTIXML_USE_STL=1)
file(GLOB children ${EUROPA_HOME}/*)
foreach(child ${children})
  if(IS_DIRECTORY ${child})
    include_directories(${child} ${child}/base ${child}/component)
  endif()
endforeach()
include_directories($ENV{HOME}/Programs/europa-deps/root/usr/include)  # antlr3, for the NDDL error type
link_directories(${EUROPA_HOME})
add_executable(europa_plan europa_plan.cc)
target_link_libraries(europa_plan System_o Resource_o Solvers_o NDDL_o TemporalNetwork_o RulesEngine_o
                      PlanDatabase_o ConstraintEngine_o Utils_o TinyXml_o)
set_target_properties(europa_plan PROPERTIES BUILD_RPATH "${EUROPA_HOME};$ENV{HOME}/Programs/europa-deps/root/usr/lib/x86_64-linux-gnu")
