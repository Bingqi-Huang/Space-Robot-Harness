#!/usr/bin/env bash
# Reproducible native build of NASA EUROPA (execution_plan §1.6, §11.2) on Ubuntu 22.04 without sudo, plus the
# upstream Light/Rover examples and this baseline's planner and PLEXIL link adapter. See docs/baselines/europa.md.
set -euo pipefail
EUROPA_COMMIT=ac5c332d01bc429e4fb543475891b1905f61475c
SRC=$HOME/Programs/europa                 # nasa/europa checkout; build in $SRC/build, install in $SRC/dist/europa
DEPS=$HOME/Programs/europa-deps           # swig 4.0, libantlr3c 3.4, cppunit 1.15 unpacked from the jammy .debs
HERE=$(cd "$(dirname "$0")" && pwd)
D=$DEPS/root/usr
export SWIG_LIB=$D/share/swig4.0

[ -d $SRC ] || git clone https://github.com/nasa/europa.git $SRC
git -C $SRC checkout -q $EUROPA_COMMIT

# the three build dependencies apt would install, extracted into a prefix (no root needed)
if [ ! -x $D/bin/swig4.0 ]; then
  mkdir -p $DEPS/debs && cd $DEPS/debs
  apt-get download swig4.0 libantlr3c-dev libantlr3c-3.4-0 libcppunit-dev libcppunit-1.15-0
  for f in *.deb; do dpkg -x $f $DEPS/root; done
fi

mkdir -p $SRC/build && cd $SRC/build
cmake .. -DOPTIMIZE=ON -DCMAKE_PREFIX_PATH=$D -DSWIG_EXECUTABLE=$D/bin/swig4.0
make -j"$(nproc)" && make install
export EUROPA_HOME=$SRC/dist/europa

# upstream examples: the interpreted-NDDL planner executables (not the SWIG/Java UI targets)
for ex in Light Rover; do
  mkdir -p $HOME/Programs/europa-examples-build/$ex && cd $HOME/Programs/europa-examples-build/$ex
  cmake $SRC/examples/$ex -DOPTIMIZE=ON -DSWIG_EXECUTABLE=$D/bin/swig4.0 -DCMAKE_PREFIX_PATH=$D
  make -j8 $ex-planner_o_rt
done

# this baseline: the EUROPA planner the host calls, and the PLEXIL adapter that links the host to the exec
mkdir -p $HERE/planner/build && cd $HERE/planner/build && cmake .. && make
mkdir -p $HERE/plexil/build && cd $HERE/plexil/build && cmake .. && make
