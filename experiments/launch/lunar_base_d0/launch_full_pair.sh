#!/bin/bash
# Mission B on GPU 0 (domain 77) and Mission A on GPU 1 (domain 78), each from scratch with 1080p video and a bag of the motion
# topics the mini-map needs. Usage: launch_full_pair.sh <tag-for-B> <tag-for-A>   (run dirs under artifacts/runs; '-' skips one)
# Never open a run's bag while its recorder is alive: a reader's SQLite lock crashes the recorder and the bag ends there.
cd "$(dirname "$0")/../../.."
B=$PWD/artifacts/runs
launch() { NAME=$1; DOM=$2; GPU=$3; MISSION=$4; SCENE=$5; VID=$6; RUN=$B/$NAME; mkdir -p $RUN; cp $B/gb2/record_qos.yaml $RUN/
  ( export D0_DOMAIN=$DOM D0_CAPABILITY_SERVER=1 D0_HOLD=1 D0_CHECK=ours_mission_check.py OURS_MISSION=$MISSION D0_VIDEO=$RUN/$VID D0_VIDEO_RES=1920,1080 D0_VIDEO_STRIDE=2 D0_VIDEO_SPEEDUP=1
    [ -n "$GPU" ] && export D0_GPU=$GPU; [ -n "$SCENE" ] && export D0_SCENE=$SCENE
    setsid nohup experiments/launch/lunar_base_d0/run_d0.sh $RUN > $RUN/runner.out 2>&1 & )
  sleep 3
  ( export ROS_DOMAIN_ID=$DOM ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST FASTRTPS_DEFAULT_PROFILES_FILE=$PWD/experiments/launch/lunar_base_d0/fastdds_large_shm.xml; source /opt/ros/humble/setup.bash
    setsid nohup ros2 bag record -o $RUN/robot_motion --qos-profile-overrides-path $RUN/record_qos.yaml /tf /tf_static /clock /srb/env0/robot/joint_states /srb/env0/robot/robot/binary_joint_position /srb/env0/mission_state /srb/env0/space_context /srb/env0/robot/robot/switchable_arm > $RUN/recorder.log 2>&1 & )
  sleep 4; ps -eo pid,cmd | grep "ros2 bag record -o $RUN" | grep -v grep | awk '{print $1}' > $RUN/recorder.pid; echo "$NAME launched (domain $DOM, video $VID); recorder $(cat $RUN/recorder.pid)"; }
[ "$1" != "-" ] && launch "$1" 77 "" b "" mission_b.mp4
[ "$2" != "-" ] && launch "$2" 78 1 a scenes/deploy/srb_lunar_base_mission_a.yaml mission_a.mp4
