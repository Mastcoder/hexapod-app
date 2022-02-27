#!python
#
# 2021 - PRESENT  Zhengyu Peng
# Website: https://zpeng.me
#
# `                      `
# -:.                  -#:
# -//:.              -###:
# -////:.          -#####:
# -/:.://:.      -###++##:
# ..   `://:-  -###+. :##:
#        `:/+####+.   :##:
# .::::::::/+###.     :##:
# .////-----+##:    `:###:
#  `-//:.   :##:  `:###/.
#    `-//:. :##:`:###/.
#      `-//:+######/.
#        `-/+####/.
#          `+##+.
#           :##:
#           :##:
#           :##:
#           :##:
#           :##:
#            .+:

# Libraries
# https://circuitpython.readthedocs.io/projects/servokit/en/latest/
from audioop import reverse
from adafruit_servokit import ServoKit

from leg import Leg

from queue import Queue, Empty

# python3-numpy
import numpy as np
import time
import json
from path_generator import gen_walk_path
from path_generator import gen_fastwalk_path
from path_generator import gen_turn_path
# from path_generator import gen_shift_path
from path_generator import gen_climb_path
from path_generator import gen_rotatex_path, gen_rotatey_path, gen_rotatez_path
from path_generator import gen_twist_path

from threading import Thread

from tcpserver import TCPServer
from btserver import BluetoothServer


class Hexapod(Thread):
    CMD_STANDBY = 'standby'
    CMD_LAYDOWN = 'laydown'

    CMD_WALK_0 = 'walk0'
    CMD_WALK_180 = 'walk180'

    CMD_WALK_R45 = 'walkr45'
    CMD_WALK_R90 = 'walkr90'
    CMD_WALK_R135 = 'walkr135'

    CMD_WALK_L45 = 'walkl45'
    CMD_WALK_L90 = 'walkl90'
    CMD_WALK_L135 = 'walkl135'

    CMD_FASTFORWARD = 'fastforward'
    CMD_FASTBACKWARD = 'fastbackward'

    CMD_TURNLEFT = 'turnleft'
    CMD_TURNRIGHT = 'turnright'

    CMD_CLIMBFORWARD = 'climbforward'
    CMD_CLIMBBACKWARD = 'climbbackward'

    CMD_ROTATEX = 'rotatex'
    CMD_ROTATEY = 'rotatey'
    CMD_ROTATEZ = 'rotatez'

    CMD_TWIST = 'twist'

    def __init__(self, in_cmd_queue):
        Thread.__init__(self)

        self.cmd_queue = in_cmd_queue
        self.interval = 0.005

        with open('/home/pi/hexapod/software/raspberry pi/config.json', 'r') as read_file:
            self.config = json.load(read_file)

        # legs' coordinates
        # x -> right
        # y -> front
        # z -> up
        # origin is the center of the body
        # roots are the positions of the bottom screws
        # length units are in mm
        # time units are in ms
        self.mount_x = np.array(self.config['legMountX'])
        self.mount_y = np.array(self.config['legMountY'])
        self.root_j1 = self.config['legRootToJoint1']
        self.j1_j2 = self.config['legJoint1ToJoint2']
        self.j2_j3 = self.config['legJoint2ToJoint3']
        self.j3_tip = self.config['legJoint3ToTip']
        self.mount_angle = np.array(self.config['legMountAngle'])/180*np.pi
        self.mount_position = np.zeros((6, 3))
        self.mount_position[:, 0] = self.mount_x
        self.mount_position[:, 1] = self.mount_y

        # Objects
        self.pca_right = ServoKit(channels=16, address=0x40, frequency=120)
        self.pca_left = ServoKit(channels=16, address=0x41, frequency=120)

        # front right
        self.leg_0 = Leg(0,
                         [self.pca_left.servo[15], self.pca_left.servo[14],
                             self.pca_left.servo[13]],
                         correction=[4, 6, 2])
        # center right
        self.leg_1 = Leg(1,
                         [self.pca_left.servo[8], self.pca_left.servo[4],
                             self.pca_left.servo[11]],
                         correction=[0, 8, -6])
        # rear right
        self.leg_2 = Leg(2,
                         [self.pca_left.servo[0], self.pca_left.servo[1],
                             self.pca_left.servo[2]],
                         correction=[2, 8, -1])
        # rear left
        self.leg_3 = Leg(3,
                         [self.pca_right.servo[15], self.pca_right.servo[14],
                             self.pca_right.servo[13]],
                         correction=[-3, 10, -8])
        # center left
        self.leg_4 = Leg(4, 
                         [self.pca_right.servo[7], self.pca_right.servo[11],
                             self.pca_right.servo[6]],
                         correction=[-6, 2, -4])
        # front left
        self.leg_5 = Leg(5,
                         [self.pca_right.servo[0], self.pca_right.servo[4],
                             self.pca_right.servo[5]],
                         correction=[0, 0, -10])

        # self.leg_0.reset(True)
        # self.leg_1.reset(True)
        # self.leg_2.reset(True)
        # self.leg_3.reset(True)
        # self.leg_4.reset(True)
        # self.leg_5.reset(True)

        self.standby_posture = self.gen_posture(60, 75)

        self.current_motion = self.standby_posture

        self.cmd_dict = {
            self.CMD_STANDBY: self.standby_posture,
            self.CMD_LAYDOWN: self.gen_posture(0, 15),
            self.CMD_WALK_0: gen_walk_path(
                self.standby_posture['coord'], direction=0),
            self.CMD_WALK_180: gen_walk_path(
                self.standby_posture['coord'], direction=180),
            self.CMD_WALK_R45: gen_walk_path(
                self.standby_posture['coord'], direction=315),
            self.CMD_WALK_R90: gen_walk_path(
                self.standby_posture['coord'], direction=270),
            self.CMD_WALK_R135: gen_walk_path(
                self.standby_posture['coord'], direction=225),
            self.CMD_WALK_L45: gen_walk_path(
                self.standby_posture['coord'], direction=45),
            self.CMD_WALK_L90: gen_walk_path(
                self.standby_posture['coord'], direction=90),
            self.CMD_WALK_L135: gen_walk_path(
                self.standby_posture['coord'], direction=135),
            self.CMD_FASTFORWARD: gen_fastwalk_path(
                self.standby_posture['coord']),
            self.CMD_FASTBACKWARD: gen_fastwalk_path(
                self.standby_posture['coord'], reverse=True),
            self.CMD_TURNLEFT: gen_turn_path(
                self.standby_posture['coord'], direction='left'),
            self.CMD_TURNRIGHT: gen_turn_path(
                self.standby_posture['coord'], direction='right'),
            self.CMD_CLIMBFORWARD: gen_climb_path(
                self.standby_posture['coord'], reverse=False),
            self.CMD_CLIMBBACKWARD: gen_climb_path(
                self.standby_posture['coord'], reverse=True),
            self.CMD_ROTATEX: gen_rotatex_path(self.standby_posture['coord']),
            self.CMD_ROTATEY: gen_rotatey_path(self.standby_posture['coord']),
            self.CMD_ROTATEZ: gen_rotatez_path(self.standby_posture['coord']),
            self.CMD_TWIST: gen_twist_path(self.standby_posture['coord'])
        }

        self.posture(self.standby_posture['coord'])
        time.sleep(1)

    def gen_posture(self, j2_angle, j3_angle):
        j2_rad = j2_angle/180*np.pi
        j3_rad = j3_angle/180*np.pi
        posture = np.zeros((6, 3))

        posture[:, 0] = self.mount_x+(self.root_j1+self.j1_j2+(
            self.j2_j3*np.sin(j2_rad))+self.j3_tip*np.cos(j3_rad)) *\
            np.cos(self.mount_angle)
        posture[:, 1] = self.mount_y + (self.root_j1+self.j1_j2+(
            self.j2_j3*np.sin(j2_rad))+self.j3_tip*np.cos(j3_rad)) *\
            np.sin(self.mount_angle)
        posture[:, 2] = self.j2_j3 * \
            np.cos(j2_rad) - self.j3_tip * \
            np.sin(j3_rad)
        return {'coord': posture,
                'type': 'posture'}

    def posture(self, coordinate):
        angles = self.inverse_kinematics(coordinate)

        self.leg_0.move_junctions(angles[0, :])
        self.leg_5.move_junctions(angles[5, :])

        self.leg_1.move_junctions(angles[1, :])
        self.leg_4.move_junctions(angles[4, :])

        self.leg_2.move_junctions(angles[2, :])
        self.leg_3.move_junctions(angles[3, :])

    def move(self, path):
        for p_idx in range(0, np.shape(path)[0]):
            dest = path[p_idx, :, :]
            angles = self.inverse_kinematics(dest)

            self.leg_0.move_junctions(angles[0, :])
            self.leg_5.move_junctions(angles[5, :])

            self.leg_1.move_junctions(angles[1, :])
            self.leg_4.move_junctions(angles[4, :])

            self.leg_2.move_junctions(angles[2, :])
            self.leg_3.move_junctions(angles[3, :])

            time.sleep(self.interval)

    def motion(self, path):
        for p_idx in range(0, np.shape(path)[0]):
            dest = path[p_idx, :, :]
            angles = self.inverse_kinematics(dest)

            self.leg_0.move_junctions(angles[0, :])
            

            self.leg_1.move_junctions(angles[1, :])
            self.leg_4.move_junctions(angles[4, :])

            self.leg_2.move_junctions(angles[2, :])
            self.leg_3.move_junctions(angles[3, :])

            self.leg_5.move_junctions(angles[5, :])

            try:
                cmd_string = self.cmd_queue.get(block=False)
                print('interrput')
            except Empty:
                time.sleep(self.interval)
                pass
            else:
                self.cmd_handler(cmd_string)
                break

    def inverse_kinematics(self, dest):
        temp_dest = dest-self.mount_position
        local_dest = np.zeros_like(dest)
        local_dest[:, 0] = temp_dest[:, 0] * \
            np.cos(self.mount_angle) + \
            temp_dest[:, 1] * np.sin(self.mount_angle)
        local_dest[:, 1] = temp_dest[:, 0] * \
            np.sin(self.mount_angle) - \
            temp_dest[:, 1] * np.cos(self.mount_angle)
        local_dest[:, 2] = temp_dest[:, 2]

        angles = np.zeros((6, 3))
        x = local_dest[:, 0] - self.root_j1
        y = local_dest[:, 1]

        angles[:, 0] = -(np.arctan2(y, x) * 180 / np.pi)+90

        x = np.sqrt(x*x + y*y) - self.j1_j2
        y = local_dest[:, 2]
        ar = np.arctan2(y, x)
        lr2 = x*x + y*y
        lr = np.sqrt(lr2)
        a1 = np.arccos((lr2 + self.j2_j3*self.j2_j3 -
                        self.j3_tip*self.j3_tip)/(2*self.j2_j3*lr))
        a2 = np.arccos((lr2 - self.j2_j3*self.j2_j3 +
                        self.j3_tip*self.j3_tip)/(2*self.j3_tip*lr))

        angles[:, 1] = 90-((ar + a1) * 180 / np.pi)
        angles[:, 2] = (90 - ((a1 + a2) * 180 / np.pi))+90

        return angles

    def cmd_handler(self, cmd_string):
        data = cmd_string.split(':')[-2]
        self.current_motion = self.cmd_dict.get(data, self.standby_posture)

        self.cmd_queue.task_done()

    def run(self):
        while True:
            # if self.current_motion is None:
            try:
                cmd_string = self.cmd_queue.get(block=False)
            except Empty:
                time.sleep(self.interval)
                pass
            else:
                self.cmd_handler(cmd_string)

            if self.current_motion['type'] == 'motion':
                self.motion(self.current_motion['coord'])
            elif self.current_motion['type'] == 'posture':
                self.posture(self.current_motion['coord'])


def main():
    q = Queue()
    tcp_server = TCPServer(q)
    tcp_server.start()

    bt_server = BluetoothServer(q)
    bt_server.start()

    hexapod = Hexapod(q)
    hexapod.start()


if __name__ == '__main__':
    main()
